"""TCP server implementation for Veltix."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..handler.request_handler import validate_callback_signature
from ..internal.bus import VeltixBus
from ..internal.events import ServerEvent
from .core import ServerCore
from .lifecycle import ServerLifecycle
from .messaging import ServerMessaging

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..handler.request_handler import RequestHandler
    from ..network.request import Request
    from ..network.response import Response
    from ..network.sender import Sender
    from ..network.types import MessageType
    from ..socket_core.base_socket import BaseSocket
    from .client_info import ClientInfo
    from .config import ServerConfig


class Server:
    """
    TCP server for the Veltix protocol.

    Accepts incoming client connections, drives the JSON raw-socket handshake,
    and dispatches received messages through the request handler.

    Each client runs in a dedicated thread. Slow callbacks never block
    message reception : all user-defined handlers execute in a thread pool
    managed by the underlying RequestHandler.

    Usage::

        config = ServerConfig(host="0.0.0.0", port=8080)
        server = Server(config)

        def on_message(client: ClientInfo, response: Response) -> None:
            server.sender.send(Request(CHAT, b"Hello"), client=client.conn)

        server.on_recv(on_message)
        server.start()
    """

    __slots__ = ("_core", "_lifecycle", "_messaging")

    def __init__(self, config: ServerConfig) -> None:
        """
        Initialize the TCP server.

        Args:
            config: Server configuration.
        """
        self._core = ServerCore(config, VeltixBus())
        self._lifecycle = ServerLifecycle(self._core)
        self._messaging = ServerMessaging(self._core)

        self._init_components()

        self.bus.info(f"Server initialized on {self.config.host}:{self.config.port}")
        self.bus.debug(
            f"Server config: buffer_size={self.config.buffer_size}, "
            f"max_connections={self.config.max_connection}"
        )

    def _init_components(self) -> None:
        """(Re)create internal components (handler, sender, socket)."""
        self._core.init_components()

    @property
    def config(self) -> ServerConfig:
        """Return the server configuration."""
        return self._core.config

    @property
    def bus(self) -> VeltixBus:
        """Return the event bus for this server."""
        return self._core.bus

    @property
    def request_handler(self) -> RequestHandler:
        """Return the underlying request handler."""
        return self._core.request_handler

    @property
    def socket(self) -> BaseSocket:
        """Return the active socket backend."""
        return self._core.socket

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    @property
    def is_full(self) -> bool:
        """Check if the server has reached its maximum connection limit.

        Returns:
            True if max_connection is set and all slots are taken,
            False otherwise.
        """
        if self.config.max_connection < 0:
            return False
        return self.socket.client_manager.count() >= self.config.max_connection

    @property
    def clients(self) -> list[ClientInfo]:
        return self._core.clients

    def on_recv(self, func: Callable) -> None:
        """Register a callback for all received messages (before routing).

        Args:
            func: func(client: ClientInfo, response: Response)
        """
        self.request_handler.set_on_recv(func)

    def on_connect(self, func: Callable) -> None:
        """Register a callback for client connections.

        Args:
            func: func(client: ClientInfo)
        """
        validate_callback_signature(
            func,
            label="on_connect callback",
            expected=1,
            dispatched="client",
            fix_sig="client: ClientInfo",
        )
        self.bus.subscribe(ServerEvent.ON_CONNECT, lambda e, p: func(p))

    def on_disconnect(self, func: Callable) -> None:
        """Register a callback for client disconnections.

        Args:
            func: func(client: ClientInfo)
        """
        validate_callback_signature(
            func,
            label="on_disconnect callback",
            expected=1,
            dispatched="client",
            fix_sig="client: ClientInfo",
        )
        self.bus.subscribe(ServerEvent.ON_DISCONNECT, lambda e, p: func(p))

    def route(self, type_: MessageType) -> Callable:
        """
        Decorator to register a route callback for a specific message type.

        Usage:
            @server.route(MY_TYPE)
            def on_my_type(client: ClientInfo, response: Response) -> None:
                ...

        Args:
            type_: Message type to intercept.

        Returns:
            Decorator function.
        """

        def decorator(func: Callable) -> Callable:
            self.request_handler.register_route(type_, func)
            return func

        return decorator

    @property
    def sender(self) -> Sender:
        """Return the sender instance for this server."""
        return self._core.sender

    def send(self, request: Request, client: ClientInfo | BaseSocket) -> bool:
        """Send a request to a client. Accepts ClientInfo or BaseSocket.

        Args:
            request: Request to send.
            client: ClientInfo or BaseSocket to send to.

        Returns:
            True if the send succeeded.
        """
        return self._messaging.send(request, client)

    def broadcast(
        self,
        request: Request,
        except_clients: list[ClientInfo | BaseSocket] | None = None,
    ) -> bool:
        """Broadcast a request to all connected clients.

        Args:
            request: Request to broadcast.
            except_clients: Clients to exclude (ClientInfo or BaseSocket).

        Returns:
            True if all sends succeeded.
        """
        return self._messaging.broadcast(request, except_clients=except_clients)

    def send_and_wait(
        self, request: Request, client: ClientInfo, timeout: float = 5.0
    ) -> Response | None:
        """
        Send a request to a client and block until the matching response is received.

        Args:
            request: Request to send.
            client:  Target client.
            timeout: Maximum time to wait for a response in seconds (default: 5.0).

        Returns:
            Matching Response, or None on timeout or send failure.
        """
        return self._messaging.send_and_wait(request, client, timeout=timeout)

    def ping_client(self, client: ClientInfo, timeout: float = 5.0) -> float | None:
        """
        Ping a client and measure round-trip latency.

        Args:
            client:  Client to ping.
            timeout: Timeout in seconds (default: 5.0).

        Returns:
            Latency in milliseconds, or None on timeout.
        """
        return self._messaging.ping_client(client, timeout=timeout)

    def ping_client_async(
        self,
        client: ClientInfo,
        callback: Callable[[float | None], None],
        timeout: float = 5.0,
    ) -> None:
        """
        Ping a client asynchronously and call callback with the result.

        Args:
            client:   Client to ping.
            callback: Called with latency in ms, or None on timeout.
            timeout:  Timeout in seconds (default: 5.0).
        """
        self._messaging.ping_client_async(client, callback, timeout=timeout)

    def close_client(self, client: ClientInfo, id_: int | None = None) -> bool:
        """Forcefully close a specific client connection."""
        if id_ is not None:
            return self.socket.close_client(id_)

        if not client:
            self.bus.warning(
                "close_client() got no client. Fix: pass a ClientInfo from "
                "server.clients or from the on_connect callback."
            )
            return False

        entry = next(
            (e for e in self.socket.client_manager.get_all_clients() if e.info == client), None
        )
        if not entry:
            self.bus.warning(
                f"close_client() could not find {client.addr} in the client list. "
                "Fix: pass a ClientInfo currently present in server.clients."
            )
            return False
        return self.socket.close_client(entry)

    def get_clients_by_tag(self, tag: str, value: Any = None) -> list[ClientInfo]:
        """Get all clients that have a specific tag, optionally matching a value.

        Args:
            tag: Tag name to filter by.
            value: Optional value to match. If None, matches any value.

        Returns:
            List of matching ClientInfo objects.
        """
        entries = self.socket.client_manager.get_clients_by_tag(tag, value)
        return [e.info for e in entries]

    # -------------------------------------------------------------------------
    # Server lifecycle
    # -------------------------------------------------------------------------

    def start(self) -> None:
        """
        Start the server and begin accepting connections.

        Non-blocking - starts a background thread and returns immediately.
        """
        self._lifecycle.start()

    def close_all(self) -> None:
        """Stop the server and close all client connections."""
        self._lifecycle.close_all()

    def wait_until_closed(self) -> None:
        """Block until the server is shut down via close_all() or Ctrl+C."""
        self._lifecycle.wait_until_closed()

    def restart(self) -> None:
        """Stop the server and start it again, preserving routes and callbacks."""
        self._lifecycle.restart()
