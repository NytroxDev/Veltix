from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Callable, Optional, Protocol, runtime_checkable

from ..internal.events import ReconnectEvent
from .disconnect import DisconnectReason, DisconnectState

if TYPE_CHECKING:
    from ..handler.request_handler import RequestHandler
    from ..internal.bus import VeltixBus
    from ..socket_core.base_socket import BaseSocket
    from .config import ClientConfig


@runtime_checkable
class ClientContext(Protocol):
    """Structural protocol that the Client must satisfy for the reconnect handler.

    This avoids a circular import between ``client.py`` and ``reconnect_handler.py``.
    """

    config: ClientConfig

    def _context_connect(self) -> bool: ...
    def _context_on_disconnect(self, state: DisconnectState) -> None: ...
    def _context_init(self) -> None: ...
    def _context_set_running(self, value: bool) -> None: ...
    def _context_set_connected(self, value: bool) -> None: ...
    def _context_get_request_handler(self) -> Optional[RequestHandler]: ...
    def _context_get_on_recv(self) -> Optional[Callable]: ...
    def _context_get_socket(self) -> Optional[BaseSocket]: ...


class ReconnectHandler:
    """Manages automatic reconnection for a client.

    Coordinates retry loops, backoff delays, and disconnect callbacks.
    Only one reconnection loop can be active at a time (enforced by
    ``_reconnect_lock``).

    Attributes:
        bus: Event bus for logging and reconnection events.
    """

    def __init__(self, context: ClientContext, bus: Optional[VeltixBus] = None) -> None:  # type: ignore[assignment]
        """Initialise the reconnect handler.

        Args:
            context: The owning client context (satisfies :class:`ClientContext`).
            bus: Optional event bus for structured logging.
        """
        self.bus = bus
        self._context = context
        self._fail_count = 0
        self._stop_retry_flag = False
        self._stop_event = threading.Event()
        self._reconnect_lock = threading.Lock()

    def init_connect(self) -> None:
        """Reset the internal state before a fresh connection attempt."""
        self._fail_count = 0
        self._stop_retry_flag = False
        self._stop_event.clear()

    def fire_on_disconnect(self, permanent: bool, reason: DisconnectReason) -> None:
        """Build a :class:`DisconnectState` and invoke the client's on_disconnect callback.

        Args:
            permanent: True if this disconnect is final (no more retries).
            reason: The reason for the disconnection.
        """
        state = DisconnectState(
            permanent=permanent,
            attempt=self._fail_count,
            retry_max=self._context.config.retry,
            reason=reason,
        )
        try:
            self._context._context_on_disconnect(state)
        except Exception as e:
            if self.bus:
                self.bus.error(f"Error in on_disconnect callback: {type(e).__name__}: {e}")

    def reconnect_loop(
        self,
        reason: DisconnectReason = DisconnectReason.SERVER_CLOSED,
        retry_max: Optional[int] = None,
    ) -> bool:
        """Run the retry loop until success, cancellation, or max retries.

        Args:
            reason: The disconnect reason to report on each failed attempt.
            retry_max: Override for the maximum number of retries. Falls back
                to ``config.retry`` if ``None``.

        Returns:
            True if reconnection succeeded, False otherwise.
        """
        max_retry = retry_max if retry_max is not None else self._context.config.retry
        while not self._stop_retry_flag and self._fail_count < max_retry:
            self._fail_count += 1
            if self.bus:
                self.bus.info(f"Reconnection attempt {self._fail_count}/{max_retry}...")
                self.bus.emit(
                    ReconnectEvent.ATTEMPT,
                    {
                        "attempt": self._fail_count,
                        "max_retry": max_retry,
                    },
                )

            self.reset()
            if self._context._context_connect():
                if self._stop_retry_flag:
                    if self.bus:
                        self.bus.info("Reconnection cancelled during connect")
                        self.bus.emit(
                            ReconnectEvent.CANCELLED,
                            {
                                "attempt": self._fail_count,
                            },
                        )
                    sock = self._context._context_get_socket()
                    if sock:
                        sock.close()
                    self._context._context_set_connected(False)
                    return False
                if self.bus:
                    self.bus.emit(
                        ReconnectEvent.SUCCESS,
                        {
                            "attempt": self._fail_count,
                        },
                    )
                return True

            if self.bus:
                self.bus.emit(
                    ReconnectEvent.FAIL,
                    {
                        "attempt": self._fail_count,
                    },
                )
            self.fire_on_disconnect(permanent=False, reason=reason)

            if self._fail_count >= max_retry:
                break

            if self.bus:
                self.bus.info(f"Next attempt in {self._context.config.retry_delay}s...")
            if self._stop_event.wait(timeout=self._context.config.retry_delay):
                break

        self.fire_on_disconnect(permanent=True, reason=reason)
        return False

    def try_reconnect(self, reason: DisconnectReason) -> bool:
        """Attempt reconnection if retries are configured and no loop is running.

        Args:
            reason: The reason for the disconnection that triggered this call.

        Returns:
            True if reconnection succeeded, False otherwise (including when
            retries are disabled or a loop is already active).
        """
        if self._context.config.retry == 0:
            self.fire_on_disconnect(permanent=True, reason=reason)
            return False

        self.fire_on_disconnect(permanent=False, reason=reason)

        if not self._reconnect_lock.acquire(blocking=False):
            if self.bus:
                self.bus.warning("try_reconnect ignored — reconnect loop already active")
            return False

        try:
            return self.reconnect_loop(reason)
        finally:
            self._reconnect_lock.release()

    def stop_retry(self) -> None:
        """Cancel any active reconnection loop and prevent further attempts."""
        if self.bus:
            self.bus.info("stop_retry() called — cancelling reconnection attempts")
        self._stop_retry_flag = True
        self._stop_event.set()

    def retry(self, max_: Optional[int] = None) -> None:
        """Force a new reconnection attempt in a background thread.

        Args:
            max_: Optional override for the maximum number of retries.
        """
        if self.bus:
            self.bus.info("retry() called — forcing reconnection attempt")
        thread = threading.Thread(target=self._retry_in_thread, kwargs={"max_": max_}, daemon=True)
        thread.start()

    def _retry_in_thread(self, max_: Optional[int] = None) -> None:
        if not self._reconnect_lock.acquire(blocking=False):
            if self.bus:
                self.bus.warning("retry() ignored — reconnect loop already active")
            return

        try:
            self._stop_retry_flag = False
            self._stop_event.clear()
            self._fail_count = 0
            self.reset()
            self.reconnect_loop(retry_max=max_)
        finally:
            self._reconnect_lock.release()

    def reset(self) -> None:
        """Reset the client's internal state for a new connection attempt.

        Preserves registered routes and the on_recv callback across reconnections.
        """
        if self.bus:
            self.bus.debug("Resetting client state for reconnection")
        old_handler = self._context._context_get_request_handler()
        old_routes = old_handler.copy_routes() if old_handler else {}

        self._context._context_set_connected(False)
        self._context._context_set_running(True)
        self._context._context_init()

        on_recv = self._context._context_get_on_recv()
        request_handler = self._context._context_get_request_handler()
        if request_handler:
            if on_recv:
                request_handler.set_on_recv(on_recv)
            for type_, func in old_routes.items():
                request_handler.register_route(type_, func)

    @property
    def stop_retry_flag(self) -> bool:
        """Whether ``stop_retry()`` has been called.

        Returns:
            True if reconnection has been cancelled.
        """
        return self._stop_retry_flag
