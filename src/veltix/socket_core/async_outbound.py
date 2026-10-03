"""Non-blocking outbound send queue for the async socket backend."""

from __future__ import annotations

from collections import deque
from threading import Lock
from typing import TYPE_CHECKING

from ..internal.events import ErrorEvent

if TYPE_CHECKING:
    import socket
    from collections.abc import Callable

    from ..internal.bus import VeltixBus


class AsyncOutbound:
    """Outbound send queue for one non-blocking socket.

    When the kernel send buffer is full, the unsent tail is buffered here
    and flushed by the selector loop once the socket becomes writable, so
    messages larger than the buffer are delivered instead of being dropped.

    Attributes:
        queue: The pending chunks, oldest first.
    """

    __slots__ = ("_get_sock", "_bus", "_queue", "_lock", "_on_queued")

    def __init__(
        self,
        get_sock: Callable[[], socket.socket],
        bus: VeltixBus,
        on_queued: Callable[[], None],
    ) -> None:
        """Initialise the queue.

        Args:
            get_sock: Resolves the raw socket to write to. Read at call time
                so the owning socket stays the single source of truth for it.
            bus: Event bus for structured observability.
            on_queued: Called after each enqueue, so the owner selector can
                register the socket for writing and wake up.
        """
        self._get_sock = get_sock
        self._bus = bus
        self._queue: deque[bytes] = deque()
        self._lock = Lock()
        self._on_queued = on_queued

    @property
    def queue(self) -> deque[bytes]:
        """Return the pending chunks, for inspection."""
        return self._queue

    def send(self, data: bytes) -> bool:
        """Send raw bytes, queueing any remainder past the kernel buffer.

        Non-blocking by design: the selector thread never blocks on a slow
        peer. When the kernel send buffer is full, the unsent tail is queued
        and flushed by the selector loop as soon as the socket becomes
        writable again, so messages larger than the buffer are delivered
        instead of being dropped.

        Args:
            data: The bytes to send.

        Returns:
            True when the data was sent or queued for delivery, False on a
            hard connection error.
        """
        try:
            sent = self._get_sock().send(data)
        except BlockingIOError as e:
            self.enqueue(data[getattr(e, "characters_written", 0) :])
            return True
        except OSError as e:
            self._bus.emit(ErrorEvent.SEND, {"error": str(e)})
            self._bus.error(f"send failed: {e}")
            return False

        if sent < len(data):
            remainder = self._send_rest(data, sent)
            if remainder is None:
                return False
            if remainder:
                self.enqueue(remainder)
        return True

    def _send_rest(self, data: bytes, start: int) -> bytes | None:
        """Send ``data[start:]`` until the kernel buffer blocks.

        Args:
            data: The bytes being sent.
            start: Offset of the first unsent byte.

        Returns:
            The unsent remainder (``b""`` when everything was sent), or
            ``None`` on a hard connection error.
        """
        view = memoryview(data)
        sock = self._get_sock()
        total = start
        while total < len(view):
            try:
                n = sock.send(view[total:])
            except BlockingIOError:
                break
            except OSError as e:
                self._bus.emit(ErrorEvent.SEND, {"error": str(e)})
                self._bus.error(f"send failed: {e}")
                return None
            if n <= 0:
                break
            total += n

        return bytes(view[total:])

    def enqueue(self, data: bytes) -> None:
        """Queue an unsent tail and notify the owner selector.

        Args:
            data: The bytes that did not fit the kernel send buffer.
        """
        with self._lock:
            self._queue.append(data)
        self._on_queued()

    def has_data(self) -> bool:
        """Return True when bytes are waiting to be flushed."""
        with self._lock:
            return bool(self._queue)

    def drop(self) -> None:
        """Discard every queued chunk."""
        with self._lock:
            self._queue.clear()

    def flush(self) -> None:
        """Push queued bytes on a writable socket (selector thread)."""
        sock = self._get_sock()
        while True:
            with self._lock:
                if not self._queue:
                    return
                chunk = self._queue.popleft()
            try:
                sent = sock.send(chunk)
            except BlockingIOError as e:
                with self._lock:
                    self._queue.appendleft(chunk[getattr(e, "characters_written", 0) :])
                return
            except OSError as e:
                self._bus.emit(ErrorEvent.SEND, {"error": str(e)})
                self._bus.error(f"send failed: {e}")
                with self._lock:
                    self._queue.clear()
                return
            if sent < len(chunk):
                remainder = self._send_rest(chunk, sent)
                if remainder is None:
                    with self._lock:
                        self._queue.clear()
                    return
                # Keep the unsent tail in front: it is the current head of
                # the byte stream and must go out before later chunks.
                with self._lock:
                    self._queue.appendleft(remainder)
                return
