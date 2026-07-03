"""TCP server implementation for Veltix."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Callable, Optional, Union

from ..handler.request_handler import RequestHandler
from ..internal.events import Events, events
from ..logger.core import Logger
from ..network.request import Request, Response
from ..network.sender import Mode, Sender
from ..network.system_types import PING
from ..socket_core.base_socket import BaseSocket, SocketEvents

if TYPE_CHECKING:
    from ..network.types import MessageType
    from .client_info import ClientInfo
    from .config import ServerConfig


class Server:
    """
    TCP server for the Veltix protocol.

    Accepts incoming client connections, drives the JSON raw-socket handshake,
    and dispatches received messages through the request handler.

    Each client runs in a dedicated thread. Slow callbacks never block
    message reception — all user-defined handlers execute in a thread pool
    managed by the underlying RequestHandler.

    Usage::

        config = ServerConfig(host="0.0.0.0", port=8080)
        server = Server(config)

        def on_message(client: ClientInfo, response: Response) -> None:
            server.get_sender().send(Request(CHAT, b"Hello"), client=client.conn)

        server.set_callback(Events.ON_RECV, on_message)
        server.start()
    """

    __slots__ = (
        "_logger",
        "config",
        "on_recv",
        "on_connect",
        "on_disconnect",
        "sender",
        "request_handler",
        "socket",
    )

    def __init__(self, config: ServerConfig) -> None:
        """
        Initialize the TCP server.

        Args:
            config: Server configuration.
        """
        self._logger = Logger.get_instance()

        self.config: ServerConfig = config

        self.sender = Sender(mode=Mode.SERVER)
        self.request_handler = RequestHandler(
            sender=self.sender, mode=Mode.SERVER, max_workers=config.max_workers
        )

        self.socket: BaseSocket = self.config.socket_core.value(
            request_handler=self.request_handler, max_message_size=self.config.max_message_size
        )
        self.socket.handshake_timeout = self.config.handshake_timeout
        self.socket.set_callback(SocketEvents.RECV, self.request_handler.handle)

        self._logger.info(f"Server initialized on {self.config.host}:{self.config.port}")
        self._logger.debug(
            f"Server config: buffer_size={self.config.buffer_size}, "
            f"max_connections={self.config.max_connection}"
        )

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    @property
    def clients(self) -> list[ClientInfo]:
        return [e.info for e in self.socket.client_manager.get_all_clients()]

    def get_all_clients_sockets(self) -> list:
        return [entry.info.conn for entry in self.socket.client_manager.get_all_clients()]

    def set_callback(self, event: Union[str, Events], func: Callable) -> None:
        """
        Bind a callback function to a server event.

        Args:
            event: Event type (Events enum or string).
            func: Callback function:
                - ON_RECV:       func(client: ClientInfo, response: Response)
                - ON_CONNECT:    func(client: ClientInfo)
                - ON_DISCONNECT: func(client: ClientInfo)
        """
        for event_ in events:
            if event == event_ or event == event_.value:
                setattr(self, event_.value, func)

                if event_ == Events.ON_RECV:
                    self.request_handler.set_on_recv(func)
                else:
                    if event_ == Events.ON_CONNECT:
                        self.socket.set_callback(SocketEvents.CONNECT, func)
                    elif event_ == Events.ON_DISCONNECT:
                        self.socket.set_callback(SocketEvents.DISCONNECT, func)

                self._logger.debug(f"Bound callback to event: {event_.value}")
                return

        self._logger.warning(f"Unknown event type for binding: {event}")

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

    def get_sender(self) -> Sender:
        """Return the sender instance for sending data to clients."""
        return self.sender

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
        self._logger.debug(f"send_and_wait: {request_id.hex()}... → {client.addr}")

        self.request_handler.register(request_id)

        if not self.sender.send(request, client=client.conn):
            self._logger.error(f"Failed to send request {request_id.hex()}... to {client.addr}")
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
        self._logger.debug(f"Pinging client {client.addr}")
        request = Request(PING, b"")
        t_send = time.perf_counter()
        response = self.send_and_wait(request, client, timeout=timeout)
        t_recv = time.perf_counter()

        if response:
            rtt = (t_recv - t_send) * 1000
            self._logger.info(f"Ping {client.addr}: {rtt:.2f}ms")
            return rtt

        self._logger.warning(f"Ping timeout for client {client.addr}")
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

        def _ping():
            try:
                callback(self.ping_client(client, timeout=timeout))
            except Exception as e:
                self._logger.error(f"Error in async ping: {e}")
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

    def get_clients_sockets_by_tag(self, tag: str, value=None) -> list[BaseSocket]:
        """Get all clients that have a specific tag, optionally matching a value."""
        entries = self.socket.client_manager.get_clients_by_tag(tag, value)
        return self.socket.client_manager.to_sockets(entries)

    # -------------------------------------------------------------------------
    # Server lifecycle
    # -------------------------------------------------------------------------

    def start(self, _on_th: bool = False) -> None:
        """
        Start the server and begin accepting connections.

        Non-blocking — starts a background thread and returns immediately.

        Args:
            _on_th: Internal parameter, do not use.
        """
        self.socket.bind(
            host=self.config.host,
            port=self.config.port,
            max_client=self.config.max_connection,
            buffer_size=self.config.buffer_size,
            timeout=0.5,
        )

    def close_all(self) -> None:
        """Stop the server and close all client connections."""
        self._logger.info("Shutting down server")

        try:
            self.request_handler.shutdown(wait=False)
            self.socket.close()
            self._logger.info("Server socket closed")
        except Exception as e:
            self._logger.error(f"Error closing server socket: {e}")
