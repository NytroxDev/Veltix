"""Inbound routing and callback registration for the Veltix server."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..handler.request_handler import validate_callback_signature
from ..internal.events import ServerEvent

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..network.types import MessageType
    from .core import ServerCore


class ServerRouting:
    """Registers inbound callbacks and per-type routes on a server."""

    __slots__ = ("_core",)

    def __init__(self, core: ServerCore) -> None:
        self._core = core

    def on_recv(self, func: Callable) -> None:
        """Register a callback for all received messages (before routing)."""
        self._core.request_handler.set_on_recv(func)

    def on_connect(self, func: Callable) -> None:
        """Register a callback for client connections."""
        validate_callback_signature(
            func,
            label="on_connect callback",
            expected=1,
            dispatched="client",
            fix_sig="client: ClientInfo",
        )
        self._core.bus.subscribe(ServerEvent.ON_CONNECT, lambda e, p: func(p))

    def on_disconnect(self, func: Callable) -> None:
        """Register a callback for client disconnections."""
        validate_callback_signature(
            func,
            label="on_disconnect callback",
            expected=1,
            dispatched="client",
            fix_sig="client: ClientInfo",
        )
        self._core.bus.subscribe(ServerEvent.ON_DISCONNECT, lambda e, p: func(p))

    def route(self, type_: MessageType) -> Callable:
        """Return a decorator registering a route callback for a message type."""

        def decorator(func: Callable) -> Callable:
            self._core.request_handler.register_route(type_, func)
            return func

        return decorator
