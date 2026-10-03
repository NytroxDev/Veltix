"""Per-connection socket returned by the accept loops."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .async_outbound import AsyncOutbound
from .base_socket import BaseSocket

if TYPE_CHECKING:
    import socket
    from collections.abc import Callable

    from ..internal.bus import VeltixBus


class AcceptedSocket(BaseSocket):
    """One connection accepted by a backend, as seen by the server layer.

    A backend plays three roles at once: the listener, the client peer, and
    every connection it accepts. Only the first two need a lifecycle, so an
    accepted connection gets this leaf instead of a full backend: it carries
    the raw socket, the bus and the outbound queue, and nothing else. The
    owning backend keeps doing the reading and the teardown bookkeeping.

    Attributes:
        handshake_timeout: Timeout in seconds for the handshake phase.
        bus: Event bus for structured observability.
    """

    def __init__(
        self,
        sock: socket.socket,
        bus: VeltixBus,
        handshake_timeout: float = 5.0,
    ) -> None:
        """Wrap an accepted raw socket.

        Args:
            sock: The raw socket returned by ``accept()``.
            bus: Event bus for structured observability.
            handshake_timeout: Timeout in seconds for the handshake phase.
        """
        self._sock = sock
        self.bus = bus
        self.handshake_timeout = handshake_timeout

    def close(self) -> bool:
        """Shut the connection down and close it.

        Called by the owning backend when tearing the client down. Unlike a
        backend's own close, this never touches the registry, the selector
        or any sibling connection.

        Returns:
            True if the socket was closed successfully, False otherwise.
        """
        self._shutdown_socket()
        try:
            self._sock.close()
            return True
        except OSError:
            return False

    def _drop_outbound(self) -> None:
        """Discard pending outbound data. No-op without an outbound queue."""


class AsyncAcceptedSocket(AcceptedSocket):
    """One connection accepted by the async backend.

    Same leaf as :class:`AcceptedSocket`, except the backend hands the
    socket over non-blocking once the handshake is done. Sends therefore go
    through an :class:`AsyncOutbound` queue instead of the blocking
    ``sendall`` of :class:`BaseSocket`, so a slow peer can never stall the
    selector loop.

    Attributes:
        handshake_timeout: Timeout in seconds for the handshake phase.
        bus: Event bus for structured observability.
    """

    def __init__(
        self,
        sock: socket.socket,
        bus: VeltixBus,
        on_queued: Callable[[AsyncAcceptedSocket], None],
        handshake_timeout: float = 5.0,
    ) -> None:
        """Wrap an accepted raw socket and prepare its outbound queue.

        Args:
            sock: The raw socket returned by ``accept()``. The owning
                backend switches it to non-blocking once the handshake is
                done; until then it must stay blocking, the handshake
                relies on it.
            bus: Event bus for structured observability.
            on_queued: Called with this socket after each enqueue, so the
                owning selector can register it for writing and wake up.
            handshake_timeout: Timeout in seconds for the handshake phase.
        """
        super().__init__(sock, bus, handshake_timeout)
        self._outbound = AsyncOutbound(lambda: self._sock, bus, lambda: on_queued(self))

    def send(self, data: bytes) -> bool:
        """Send raw bytes, queueing any remainder past the kernel buffer.

        Args:
            data: The bytes to send.

        Returns:
            True when the data was sent or queued for delivery, False on a
            hard connection error.
        """
        return self._outbound.send(data)

    def _has_outbound(self) -> bool:
        """Return True when bytes are waiting to be flushed."""
        return self._outbound.has_data()

    def _drop_outbound(self) -> None:
        """Discard every queued chunk."""
        self._outbound.drop()

    def close(self) -> bool:
        """Drop the outbound queue, then shut the connection down.

        A closed connection must not keep undelivered bytes referenced, so
        the queue goes first.

        Returns:
            True if the socket was closed successfully, False otherwise.
        """
        self._drop_outbound()
        return super().close()

    def _flush_outbound(self) -> None:
        """Push queued bytes on a writable socket (selector thread)."""
        self._outbound.flush()
