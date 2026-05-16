from __future__ import annotations

import dataclasses
import threading
from typing import TYPE_CHECKING, Callable, Optional, Protocol, runtime_checkable

from ..logger import Logger
from .disconnect import DisconnectReason, DisconnectState

if TYPE_CHECKING:
    from veltix.handler.request_handler import RequestHandler

    from .config import ClientConfig


@runtime_checkable
class ClientContext(Protocol):
    config: ClientConfig

    def context_connect(self) -> bool: ...
    def context_on_disconnect(self, state: DisconnectState) -> None: ...
    def context_init(self) -> None: ...
    def context_set_running(self, value: bool) -> None: ...
    def context_set_connected(self, value: bool) -> None: ...
    def context_get_request_handler(self) -> Optional[RequestHandler]: ...
    def context_get_on_recv(self) -> Optional[Callable]: ...


class ReconnectHandler:
    def __init__(self, context: ClientContext):
        self._logger = Logger.get_instance()
        self._context = context
        self._fail_count = 0
        self._stop_retry_flag = False
        self._stop_event = threading.Event()

    def init_connect(self) -> None:
        """Reset retry state after a successful connection."""
        self._fail_count = 0
        self._stop_retry_flag = False
        self._stop_event.clear()

    def fire_on_disconnect(self, permanent: bool, reason: DisconnectReason) -> None:
        """Fire the on_disconnect callback with the current retry state."""
        state = DisconnectState(
            permanent=permanent,
            attempt=self._fail_count,
            retry_max=self._context.config.retry,
            reason=reason,
        )
        try:
            self._context.context_on_disconnect(state)
        except Exception as e:
            self._logger.error(f"Error in on_disconnect callback: {type(e).__name__}: {e}")

    def reconnect_loop(self, reason: DisconnectReason = DisconnectReason.SERVER_CLOSED) -> bool:
        """
        Attempt reconnection up to config.retry times.

        Each attempt is made immediately. On failure, waits retry_delay
        before the next attempt. The wait is interruptible via stop_retry().

        Fires on_disconnect at each failed attempt with permanent=False,
        and a final time with permanent=True if all attempts are exhausted
        or stop_retry() was called.

        Returns:
            True if reconnection succeeded, False otherwise.
        """
        while not self._stop_retry_flag and self._fail_count < self._context.config.retry:
            self._fail_count += 1
            self._logger.info(
                f"Reconnection attempt {self._fail_count}/{self._context.config.retry}..."
            )

            self.reset()
            if self._context.context_connect():
                return True

            self.fire_on_disconnect(permanent=False, reason=reason)

            if self._fail_count >= self._context.config.retry:
                break

            self._logger.info(f"Next attempt in {self._context.config.retry_delay}s...")
            if self._stop_event.wait(timeout=self._context.config.retry_delay):
                break

        self.fire_on_disconnect(permanent=True, reason=reason)
        return False

    def try_reconnect(self, reason: DisconnectReason) -> bool:
        """
        Start the reconnect loop if retry is enabled.

        When ``config.retry == 0``, fires ``on_disconnect`` with
        ``permanent=True`` immediately without attempting a connection.

        Returns:
            True if reconnection eventually succeeded, False otherwise.
        """
        if self._context.config.retry == 0:
            self.fire_on_disconnect(permanent=True, reason=reason)
            return False

        return self.reconnect_loop(reason)

    def stop_retry(self) -> None:
        """
        Cancel all pending reconnection attempts.

        If a retry loop is running, it will stop after the current attempt
        and fire on_disconnect with permanent=True.
        """
        self._logger.info("stop_retry() called — cancelling reconnection attempts")
        self._stop_retry_flag = True
        self._stop_event.set()

    def retry(self, max_: Optional[int] = None) -> None:
        """
        Force an immediate reconnection attempt, even if retry_max was reached.

        Args:
            max_: Override retry_max for this session (optional).
        """
        if max_ is not None:
            self._context.config = dataclasses.replace(self._context.config, retry=max_)
            self._logger.info(f"retry() called — new retry_max={max_}")
        else:
            self._logger.info("retry() called — forcing reconnection attempt")

        self._stop_retry_flag = False
        self._stop_event.clear()
        self._fail_count = 0
        self.reset()
        threading.Thread(target=self.reconnect_loop, daemon=True).start()

    def reset(self) -> None:
        """
        Reset the client state for a reconnection attempt.

        Sets the connection state to disconnected, ensures the client is
        marked as running, re-initialises the context, and re-attaches
        the on_recv callback to the request handler.
        """
        self._logger.debug("Resetting client state for reconnection")
        self._context.context_set_connected(False)
        self._context.context_set_running(True)
        self._context.context_init()

        on_recv = self._context.context_get_on_recv()
        request_handler = self._context.context_get_request_handler()
        if on_recv and request_handler:
            request_handler.set_on_recv(on_recv)

    @property
    def stop_retry_flag(self) -> bool:
        """Whether reconnection attempts have been cancelled."""
        return self._stop_retry_flag
