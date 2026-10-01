"""Shared component wiring for the Veltix client."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..handler.request_handler import RequestHandler
from ..network import _rust
from ..network.constants import REQUEST_ID_HALF
from ..network.id_allocator import IDAllocator
from ..network.sender import Mode, Sender

if TYPE_CHECKING:
    from ..internal.bus import VeltixBus
    from ..socket_core.base_socket import BaseSocket
    from .config import ClientConfig


class ClientCore:
    """Shared, reconnect-mutable components for a :class:`~veltix.client.client.Client`.

    Holds the components rebuilt by :meth:`init_components` on every
    (re)connect: socket backend, request handler, sender and request-ID
    allocator. The public ``Client`` facade forwards its historical
    attributes (``config``, ``bus``, ``socket``, ``request_handler``,
    ``sender``) here.
    """

    __slots__ = ("config", "bus", "socket", "request_handler", "sender", "id_allocator")

    def __init__(self, config: ClientConfig, bus: VeltixBus) -> None:
        self.config = config
        self.bus = bus
        # All set by init_components(); declared here for the type checker.
        self.socket: BaseSocket
        self.request_handler: RequestHandler
        self.sender: Sender
        self.id_allocator: IDAllocator

    def init_components(self, socket_owner: Any) -> None:
        """(Re)initialise all internal components (socket, sender, handler).

        Args:
            socket_owner: Object assigned to ``socket.client`` so the backend
                can flag connect/disconnect state (exposes ``_state_lock``,
                ``is_connected`` and ``_connecting``).
        """
        use_rust = _rust.rust_enabled()

        old_handler = getattr(self, "request_handler", None)
        old_socket = getattr(self, "socket", None)

        if old_handler:
            old_handler.shutdown(wait=False)
        if old_socket:
            old_socket.close()

        self.socket = self.config.socket_core.value(
            request_handler=None,
            max_message_size=self.config.max_message_size,
            bus=self.bus,
            use_rust=use_rust,
        )
        self.socket.client = socket_owner
        self.socket.settimeout(self.config.handshake_timeout)

        self.request_handler = RequestHandler(
            mode=Mode.CLIENT,
            bus=self.bus,
            max_workers=self.config.max_workers,
        )

        # Clients allocate from the lower half of the request-ID space so
        # their auto-assigned IDs never collide with a server pending (see
        # docs/design/request-id-correlation.md).
        self.id_allocator = IDAllocator(
            max_ids=REQUEST_ID_HALF,
            is_pending=lambda rid: rid in self.request_handler.pending_requests,
        )

        self.sender = Sender(
            mode=Mode.CLIENT,
            conn=self.socket,
            bus=self.bus,
            id_allocator=self.id_allocator,
            use_rust=use_rust,
        )
        self.request_handler.sender = self.sender

        self.socket.request_handler = self.request_handler
