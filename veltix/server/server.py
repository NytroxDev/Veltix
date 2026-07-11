"""TCP server implementation for Veltix."""

from __future__ import annotations

import threading
import time
import warnings
from typing import TYPE_CHECKING, Any, Callable, Optional, Union

from ..handler.request_handler import RequestHandler
from ..internal.bus import VeltixBus
from ..internal.events import ServerEvent
from ..network.request import Request, Response
from ..network.sender import Mode, Sender
from ..network.system_types import PING

if TYPE_CHECKING:
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

    __slots__ = (
        "config",
        "bus",
        "_sender",
        "request_handler",
        "socket",
        "_shutdown_event",
        "_started",
        "_closed",
    )

    def __init__(self, config: ServerConfig) -> None:
        """
        Initialize the TCP server.

        Args:
            config: Server configuration.
        """
        self.bus = VeltixBus()

        self.config: ServerConfig = config
        self._shutdown_event = threading.Event()
        self._started = False
        self._closed = False

        self._init_components()

        self.bus.info(f"Server initialized on {self.config.host}:{self.config.port}")
        self.bus.debug(
            f"Server config: buffer_size={self.config.buffer_size}, "
            f"max_connections={self.config.max_connection}"
        )

    def _init_components(self) -> None:
        """(Re)create internal components (sender, handler, socket)."""
        self._sender = Sender(
            mode=Mode.SERVER,
            bus=self.bus,
            get_all_clients=self.get_all_clients_sockets,
        )
        self.request_handler = RequestHandler(
            sender=self.sender, mode=Mode.SERVER, max_workers=self.config.max_workers, bus=self.bus
        )
        self.socket: BaseSocket = self.config.socket_core.value(
            request_handler=self.request_handler,
            max_message_size=self.config.max_message_size,
            bus=self.bus,
        )
        self.socket.handshake_timeout = self.config.handshake_timeout

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    @property
    def clients(self) -> list[ClientInfo]:
        return [e.info for e in self.socket.client_manager.get_all_clients()]

    def get_all_clients_sockets(self) -> list[BaseSocket]:
        return [entry.info.conn for entry in self.socket.client_manager.get_all_clients()]

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
        self.bus.subscribe(ServerEvent.ON_CONNECT, lambda e, p: func(p))

    def on_disconnect(self, func: Callable) -> None:
        """Register a callback for client disconnections.

        Args:
            func: func(client: ClientInfo)
        """
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
        return self._sender

    def get_sender(self) -> Sender:
        """
        Deprecated: use server.sender instead.
        """
        warnings.warn(
            "Server.get_sender() is deprecated and will be removed in a future version. "
            "Use Server.sender instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.sender

    def send(self, request: Request, client: Union[ClientInfo, BaseSocket]) -> bool:
        """Send a request to a client. Accepts ClientInfo or BaseSocket.

        Args:
            request: Request to send.
            target: ClientInfo or BaseSocket to send to.

        Returns:
            True if the send succeeded.
        """
        from .client_info import ClientInfo

        socket = client.conn if isinstance(client, ClientInfo) else client
        return self.sender.send(request, client=socket)

    def broadcast(
        self,
        request: Request,
        except_clients: Optional[list[Union[ClientInfo, BaseSocket]]] = None,
    ) -> bool:
        """Broadcast a request to all connected clients.

        Args:
            request: Request to broadcast.
            except_clients: Clients to exclude (ClientInfo or BaseSocket).

        Returns:
            True if all sends succeeded.
        """
        return self.sender.broadcast(request, except_clients=except_clients)

    def send_and_wait(
        self, request: Request, client: ClientInfo, timeout: float = 5.0
    ) -> Optional[Response]:
        """
        Send a request to a client and block until the matching response is received.

        Args:
            request: Request to send.
            client:  Target client.
            timeout: Maximum time to wait for a response in seconds (default: 5.0).

        Returns:
            Matching Response, or None on timeout or send failure.
        """
        request_id = request.request_id
        self.bus.debug(f"send_and_wait: {request_id.hex()}... → {client.addr}")

        self.request_handler.register(request_id)

        if not self.sender.send(request, client=client.conn):
            self.bus.error(f"Failed to send request {request_id.hex()}... to {client.addr}")
            self.request_handler.unregister(request_id)
            return None

        return self.request_handler.wait(request_id, timeout)

    def ping_client(self, client: ClientInfo, timeout: float = 5.0) -> Optional[float]:
        """
        Ping a client and measure round-trip latency.

        Args:
            client:  Client to ping.
            timeout: Timeout in seconds (default: 5.0).

        Returns:
            Latency in milliseconds, or None on timeout.
        """
        self.bus.debug(f"Pinging client {client.addr}")
        request = Request(PING, b"")
        t_send = time.perf_counter()
        response = self.send_and_wait(request, client, timeout=timeout)
        t_recv = time.perf_counter()

        if response:
            rtt = (t_recv - t_send) * 1000
            self.bus.info(f"Ping {client.addr}: {rtt:.2f}ms")
            return rtt

        self.bus.warning(f"Ping timeout for client {client.addr}")
        return None

    def ping_client_async(
        self,
        client: ClientInfo,
        callback: Callable[[Optional[float]], None],
        timeout: float = 5.0,
    ) -> None:
        """
        Ping a client asynchronously and call callback with the result.

        Args:
            client:   Client to ping.
            callback: Called with latency in ms, or None on timeout.
            timeout:  Timeout in seconds (default: 5.0).
        """

        def _ping() -> None:
            try:
                callback(self.ping_client(client, timeout=timeout))
            except Exception as e:
                self.bus.error(f"Error in async ping: {e}")
                callback(None)

        threading.Thread(target=_ping, daemon=True).start()

    def close_client(self, client: ClientInfo, id_: Optional[int] = None) -> bool:
        """Forcefully close a specific client connection."""
        if id_ is not None:
            return self.socket.close_client(id_)

        if not client:
            return False

        entry = next(
            (e for e in self.socket.client_manager.get_all_clients() if e.info == client), None
        )
        if not entry:
            return False
        return self.socket.close_client(entry)

    def get_clients_sockets_by_tag(self, tag: str, value: Any = None) -> list[BaseSocket]:
        """Get all clients that have a specific tag, optionally matching a value."""
        entries = self.socket.client_manager.get_clients_by_tag(tag, value)
        return self.socket.client_manager.to_sockets(entries)

    # -------------------------------------------------------------------------
    # Server lifecycle
    # -------------------------------------------------------------------------

    def start(self) -> None:
        """
        Start the server and begin accepting connections.

        Non-blocking — starts a background thread and returns immediately.
        """
        if self._started:
            self.bus.warning("Server is already started")
            return

        self._started = True
        self._shutdown_event.clear()
        if self._closed:
            self._closed = False
            old_routes = self.request_handler.copy_routes()
            old_on_recv = self.request_handler.on_recv
            self._init_components()
            for type_, func in old_routes.items():
                self.request_handler.register_route(type_, func)
            if old_on_recv:
                self.request_handler.set_on_recv(old_on_recv)
        self.socket.bind(
            host=self.config.host,
            port=self.config.port,
            max_client=self.config.max_connection,
            buffer_size=self.config.buffer_size,
            timeout=0.5,
        )
        self.bus.emit(
            ServerEvent.STARTED,
            {
                "host": self.config.host,
                "port": self.config.port,
            },
        )
        self.bus.info(f"Server started on {self.config.host}:{self.config.port}")

    def close_all(self) -> None:
        """Stop the server and close all client connections."""
        if self._closed:
            self.bus.warning("Server is already closed")
            return

        self.bus.info("Shutting down server")

        try:
            self.request_handler.shutdown(wait=False)
            self.socket.close()
            self.bus.info("Server socket closed")
        except Exception as e:
            self.bus.error(f"Error closing server socket: {e}")

        self._started = False
        self._closed = True
        self._shutdown_event.set()

        self.bus.emit(
            ServerEvent.STOPPED,
            {
                "host": self.config.host,
                "port": self.config.port,
            },
        )

    def wait_until_closed(self) -> None:
        """Block until the server is shut down via close_all() or Ctrl+C."""
        try:
            self._shutdown_event.wait()
        except KeyboardInterrupt:
            self.close_all()

    def restart(self) -> None:
        """Stop the server and start it again, preserving routes and callbacks."""
        self.close_all()
        self.start()
