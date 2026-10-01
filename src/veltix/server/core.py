"""Shared, restart-mutable state for the Veltix server."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..handler.request_handler import RequestHandler
from ..network import _rust
from ..network.constants import REQUEST_ID_HALF
from ..network.id_allocator import IDAllocator
from ..network.sender import Mode, Sender

if TYPE_CHECKING:
    from ..internal.bus import VeltixBus
    from ..socket_core.base_socket import BaseSocket
    from .client_info import ClientInfo
    from .config import ServerConfig


class ServerCore:
    """Shared state for a :class:`~veltix.server.server.Server`.

    Holds the components that are rebuilt on every (re)start by
    :meth:`init_components`: request handler, sender, socket backend and
    request-ID allocator. The public ``Server`` facade forwards its
    historical attributes (``config``, ``bus``, ``socket``,
    ``request_handler``, ``sender``) here.
    """

    __slots__ = ("config", "bus", "request_handler", "sender", "socket", "id_allocator")

    def __init__(self, config: ServerConfig, bus: VeltixBus) -> None:
        self.config = config
        self.bus = bus
        # All set by init_components(); declared here for the type checker.
        self.request_handler: RequestHandler
        self.sender: Sender
        self.socket: BaseSocket
        self.id_allocator: IDAllocator

    @property
    def clients(self) -> list[ClientInfo]:
        return [e.info for e in self.socket.client_manager.get_all_clients()]

    def init_components(self) -> None:
        """(Re)create the internal components (handler, sender, socket)."""
        use_rust = _rust.rust_enabled()

        self.request_handler = RequestHandler(
            mode=Mode.SERVER,
            bus=self.bus,
            max_workers=self.config.max_workers,
        )

        # Servers reserve the upper half of the request-ID space so their
        # auto-assigned IDs never collide with client pendings (see
        # docs/design/request-id-correlation.md).
        server_pool = min(self.config.id_window, REQUEST_ID_HALF)
        if server_pool < self.config.id_window:
            self.bus.warning(
                f"id_window capped to {server_pool} "
                f"(upper half of the ID space is reserved for the server)"
            )

        self.id_allocator = IDAllocator(
            max_ids=server_pool,
            offset=REQUEST_ID_HALF,
            is_pending=lambda rid: rid in self.request_handler.pending_requests,
        )

        self.sender = Sender(
            mode=Mode.SERVER,
            bus=self.bus,
            get_all_clients=lambda: self.clients,
            id_allocator=self.id_allocator,
            use_rust=use_rust,
        )

        self.request_handler.sender = self.sender

        self.socket = self.config.socket_core.value(
            request_handler=self.request_handler,
            max_message_size=self.config.max_message_size,
            bus=self.bus,
            use_rust=use_rust,
        )
        self.socket.handshake_timeout = self.config.handshake_timeout
