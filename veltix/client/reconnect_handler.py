from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Callable, Optional, Protocol, runtime_checkable

from ..internal.events import ReconnectEvent
from .disconnect import DisconnectReason, DisconnectState

if TYPE_CHECKING:
    from veltix.handler.request_handler import RequestHandler
    from veltix.internal.bus import VeltixBus
    from veltix.socket_core.base_socket import BaseSocket

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
    def context_get_socket(self) -> Optional[BaseSocket]: ...


class ReconnectHandler:
    def __init__(self, context: ClientContext, bus: VeltixBus = None) -> None:  # type: ignore[assignment]
        self.bus = bus
        self._context = context
        self._fail_count = 0
        self._stop_retry_flag = False
        self._stop_event = threading.Event()
        self._reconnect_lock = threading.Lock()

    def init_connect(self) -> None:
        self._fail_count = 0
        self._stop_retry_flag = False
        self._stop_event.clear()

    def fire_on_disconnect(self, permanent: bool, reason: DisconnectReason) -> None:
        state = DisconnectState(
            permanent=permanent,
            attempt=self._fail_count,
            retry_max=self._context.config.retry,
            reason=reason,
        )
        try:
            self._context.context_on_disconnect(state)
        except Exception as e:
            if self.bus:
                self.bus.error(f"Error in on_disconnect callback: {type(e).__name__}: {e}")

    def reconnect_loop(
        self,
        reason: DisconnectReason = DisconnectReason.SERVER_CLOSED,
        retry_max: Optional[int] = None,
    ) -> bool:
        max_retry = retry_max if retry_max is not None else self._context.config.retry
        while not self._stop_retry_flag and self._fail_count < max_retry:
            self._fail_count += 1
            if self.bus:
                self.bus.info(f"Reconnection attempt {self._fail_count}/{max_retry}...")
                self.bus.emit(ReconnectEvent.ATTEMPT, {
                    "attempt": self._fail_count,
                    "max_retry": max_retry,
                })

            self.reset()
            if self._context.context_connect():
                if self._stop_retry_flag:
                    if self.bus:
                        self.bus.info("Reconnection cancelled during connect")
                        self.bus.emit(ReconnectEvent.CANCELLED, {
                            "attempt": self._fail_count,
                        })
                    sock = self._context.context_get_socket()
                    if sock:
                        sock.close()
                    self._context.context_set_connected(False)
                    return False
                if self.bus:
                    self.bus.emit(ReconnectEvent.SUCCESS, {
                        "attempt": self._fail_count,
                    })
                return True

            if self.bus:
                self.bus.emit(ReconnectEvent.FAIL, {
                    "attempt": self._fail_count,
                })
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
        if self.bus:
            self.bus.info("stop_retry() called — cancelling reconnection attempts")
        self._stop_retry_flag = True
        self._stop_event.set()

    def retry(self, max_: Optional[int] = None) -> None:
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
        if self.bus:
            self.bus.debug("Resetting client state for reconnection")
        old_handler = self._context.context_get_request_handler()
        old_routes = old_handler.copy_routes() if old_handler else {}

        self._context.context_set_connected(False)
        self._context.context_set_running(True)
        self._context.context_init()

        on_recv = self._context.context_get_on_recv()
        request_handler = self._context.context_get_request_handler()
        if request_handler:
            if on_recv:
                request_handler.set_on_recv(on_recv)
            for type_, func in old_routes.items():
                request_handler.register_route(type_, func)

    @property
    def stop_retry_flag(self) -> bool:
        return self._stop_retry_flag
