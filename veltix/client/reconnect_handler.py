import dataclasses
import threading
import time
from typing import Callable, Optional

from veltix.handler.request_handler import RequestHandler

from ..logger import Logger
from .config import ClientConfig
from .disconnect import DisconnectReason, DisconnectState


class ReconnectHandler:
    def __init__(
        self,
        config: ClientConfig,
        on_disconnect: Callable[[DisconnectState], None],
        connect: Callable,
        on_recv: Optional[Callable],
        on_init: Callable,
        set_running: Callable,
        set_connected: Callable,
        request_handler: Optional[RequestHandler] = None,
    ):
        self._logger = Logger.get_instance()
        self.request_handler = request_handler
        self.set_running = set_running
        self.set_connected = set_connected
        self.on_recv = on_recv
        self._fail_count = 0
        self._stop_retry_flag = False
        self.config = config
        self._on_disconnect = on_disconnect
        self._connect = connect
        self.init_components = on_init

    def refresh(
        self,
        config: ClientConfig,
        connect: Callable,
        on_recv: Optional[Callable],
        on_init: Callable,
        set_running: Callable,
        set_connected: Callable,
        request_handler: Optional[RequestHandler],
    ) -> None:
        """Refresh internal references after client components are rebuilt."""
        self.config = config
        self._connect = connect
        self.on_recv = on_recv
        self.init_components = on_init
        self.set_running = set_running
        self.set_connected = set_connected
        self.request_handler = request_handler

    def init_connect(self):
        self._fail_count = 0
        self._stop_retry_flag = False

    def fire_on_disconnect(self, permanent: bool, reason: DisconnectReason) -> None:
        """Fire the on_disconnect callback with the current retry state."""
        if self._on_disconnect:
            state = DisconnectState(
                permanent=permanent,
                attempt=self._fail_count,
                retry_max=self.config.retry,
                reason=reason,
            )
            try:
                self._on_disconnect(state)
            except Exception as e:
                self._logger.error(f"Error in on_disconnect callback: {type(e).__name__}: {e}")

    def reconnect_loop(self, reason: DisconnectReason = DisconnectReason.SERVER_CLOSED) -> bool:
        """
        Attempt reconnection up to config.retry times.

        Fires on_disconnect at each failed attempt with permanent=False,
        and a final time with permanent=True if all attempts are exhausted
        or stop_retry() was called.

        Returns:
            True if reconnection succeeded, False otherwise.
        """
        while not self._stop_retry_flag and self._fail_count < self.config.retry:
            self._fail_count += 1
            self._logger.info(
                f"Reconnection attempt {self._fail_count}/{self.config.retry} "
                f"in {self.config.retry_delay}s..."
            )
            time.sleep(self.config.retry_delay)

            self.reset()
            if self._connect():
                return True

            self.fire_on_disconnect(permanent=False, reason=reason)

        self.fire_on_disconnect(permanent=True, reason=reason)
        return False

    def try_reconnect(self, reason: DisconnectReason) -> bool:
        """
        Start the reconnect loop if retry is enabled.

        Returns:
            True if reconnection eventually succeeded, False otherwise.
        """
        if self.config.retry == 0:
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

    def retry(self, max_: Optional[int] = None) -> None:
        """
        Force an immediate reconnection attempt, even if retry_max was reached.

        Args:
            max_: Override retry_max for this session (optional).
        """
        if max_ is not None:
            self.config = dataclasses.replace(self.config, retry=max_)
            self._logger.info(f"retry() called — new retry_max={max_}")
        else:
            self._logger.info("retry() called — forcing reconnection attempt")

        self._stop_retry_flag = False
        self._fail_count = 0
        self.reset()
        threading.Thread(target=self.reconnect_loop, daemon=True).start()

    def reset(self) -> None:
        """
        Reset all internal state for a fresh reconnection attempt.

        Called automatically when a mid-session disconnection is detected
        and retry is enabled.
        """
        self._logger.debug("Resetting client state for reconnection")
        self.set_connected(False)
        self.set_running(True)
        self.init_components()

        if self.on_recv:
            self.request_handler.set_on_recv(self.on_recv)

    @property
    def stop_retry_flag(self):
        return self._stop_retry_flag
