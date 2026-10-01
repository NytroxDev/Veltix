"""Inbound routing and callback registration for the Veltix client."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..handler.request_handler import validate_callback_signature
from ..internal.events import ClientEvent

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..network.types import MessageType
    from .core import ClientCore


class ClientRouting:
    """Registers inbound callbacks and per-type routes on a client."""

    __slots__ = ("_core",)

    def __init__(self, core: ClientCore) -> None:
        self._core = core

    def on_recv(self, func: Callable) -> None:
        """Register a callback for all received messages (before routing)."""
        self._core.request_handler.set_on_recv(func)

    def on_connect(self, func: Callable) -> None:
        """Register a callback for successful connection."""
        validate_callback_signature(
            func,
            label="on_connect callback",
            expected=0,
            dispatched="",
            fix_sig="",
        )
        self._core.bus.subscribe(ClientEvent.ON_CONNECT, lambda e, p: func())

    def on_disconnect(self, func: Callable) -> None:
        """Register a callback for disconnection."""
        validate_callback_signature(
            func,
            label="on_disconnect callback",
            expected=1,
            dispatched="state",
            fix_sig="state: DisconnectState",
        )
        self._core.bus.subscribe(ClientEvent.ON_DISCONNECT, lambda e, p: func(p))

    def route(self, type_: MessageType) -> Callable:
        """Return a decorator registering a route callback for a message type."""

        def decorator(func: Callable) -> Callable:
            self._core.request_handler.register_route(type_, func)
            return func

        return decorator
