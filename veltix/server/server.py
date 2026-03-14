"""TCP server implementation for Veltix."""

import threading
import time
from collections.abc import Callable
from threading import Lock
from typing import Optional, Union

from ..handler.request_handler import RequestHandler
from ..internal.events import Events, events
from ..internal.network import recv
from ..internal.performance_mode import get_settings
from ..logger.core import Logger
from ..network.message_buffer import MessageBuffer
from ..network.request import Request, Response
from ..network.sender import Mode, Sender
from ..network.system_types import PING
from ..network.types import MessageType
from ..socket.base_socket import BaseSocket
from .client_info import ClientInfo
from .config import ServerConfig


class Server:
    """
    TCP server for the Veltix protocol.

    Accepts incoming client connections, drives the HELLO/HELLO_ACK handshake,
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
        "_perf",
        "_client_buffers",
        "_buffers_lock",
        "clients",
        "_clients_lock",
        "threads",
        "_threads_lock",
        "config",
        "start_th",
        "on_recv",
        "on_connect",
        "on_disconnect",
        "running",
        "n_th",
        "_n_th_lock",
        "ping_result",
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
        self._perf = get_settings(config.performance_mode)

        self._client_buffers: dict[BaseSocket, MessageBuffer] = {}
        self._buffers_lock = Lock()

        self.clients: list[ClientInfo] = []
        self._clients_lock = Lock()

        self.threads: list[tuple[int, threading.Thread]] = []
        self._threads_lock = Lock()

        self.config: ServerConfig = config
        self.start_th: Optional[threading.Thread] = None
        self.on_recv: Optional[Callable] = None
        self.on_connect: Optional[Callable] = None
        self.on_disconnect: Optional[Callable] = None
        self.running: bool = True
        self.n_th = 0
        self._n_th_lock = Lock()
        self.ping_result: Optional[Response] = None

        self.sender = Sender(mode=Mode.SERVER)
        self.request_handler = RequestHandler(
            self.sender, mode=Mode.SERVER, max_workers=config.max_workers
        )

        self.socket: BaseSocket = self.config.socket_core.value()
        self.socket.bind((self.config.host, self.config.port))

        self._logger.info(f"Server initialized on {self.config.host}:{self.config.port}")
        self._logger.debug(
            f"Server config: buffer_size={self.config.buffer_size}, "
            f"max_connections={self.config.max_connection}, "
            f"performance_mode={config.performance_mode.name}"
        )

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

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

                self._logger.debug(f"Bound callback to event: {event_.value}")
                return

        self._logger.warning(f"Unknown event type for binding: {event}")

    def route(self, type_: MessageType) -> Callable:
        """
        Decorator to register a route callback for a specific message type.

        Usage:
            @server.route(MY_TYPE)
            def on_my_type(response: Response, client: ClientInfo) -> None:
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

    def get_all_clients_sockets(self) -> list[BaseSocket]:
        """Return a list of all connected client sockets."""
        with self._clients_lock:
            return [client.conn for client in self.clients]

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
        self._logger.debug(f"send_and_wait: {request_id[:8]}... → {client.addr}")

        self.request_handler.register(request_id)

        if not self.sender.send(request, client=client.conn):
            self._logger.error(f"Failed to send request {request_id[:8]}... to {client.addr}")
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
        response = self.send_and_wait(Request(PING, b""), client, timeout=timeout)

        if response:
            self._logger.info(f"Ping {client.addr}: {response.latency:.2f}ms")
            return response.latency

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
        if not _on_th:
            self._logger.info(f"Starting server on {self.config.host}:{self.config.port}")
            self.start_th = threading.Thread(target=self.start, args=(True,), daemon=True)
            self.start_th.start()
            return

        self.socket.listen()
        self._logger.info(f"Server listening on {self.config.host}:{self.config.port}")

        while self.running:
            try:
                with self._clients_lock:
                    current_count = len(self.clients)

                if 0 < self.config.max_connection <= current_count:
                    time.sleep(0.1)
                    continue

                conn, addr = self.socket.accept()

                with self._n_th_lock:
                    self.n_th += 1
                    thread_id = self.n_th

                client = ClientInfo(conn=conn, addr=addr, thread_id=thread_id, handshake_done=False)

                with self._clients_lock:
                    self.clients.append(client)
                    total = len(self.clients)

                self._logger.info(
                    f"New client connected: {addr} (total: {total}/{self.config.max_connection})"
                )

                thread = threading.Thread(target=self._handle_client, args=(client,), daemon=True)
                thread.start()

                with self._threads_lock:
                    self.threads.append((thread_id, thread))

            except TimeoutError:
                continue
            except OSError:
                return
            except Exception as e:
                if self.running:
                    self._logger.error(f"Error accepting connections: {type(e).__name__}: {e}")
                return

    def close_all(self) -> None:
        """Stop the server and close all client connections."""
        self._logger.info("Shutting down server")
        self.running = False

        try:
            self.socket.close()
            self._logger.info("Server socket closed")
        except Exception as e:
            self._logger.error(f"Error closing server socket: {e}")

        if self.start_th and self.start_th.is_alive():
            self._logger.debug("Waiting for accept thread to finish...")
            self.start_th.join(timeout=2.0)
            if self.start_th.is_alive():
                self._logger.warning("Accept thread did not finish in time")
            else:
                self._logger.debug("Accept thread finished")

        with self._clients_lock:
            clients_to_close = list(self.clients)
            client_count = len(clients_to_close)

        for client in clients_to_close:
            try:
                self.close_client(client)
            except Exception as e:
                self._logger.error(f"Error closing client {client.addr}: {e}")

        with self._threads_lock:
            threads_to_join = list(self.threads)
            thread_count = len(threads_to_join)

        for _, thread in threads_to_join:
            try:
                thread.join(timeout=self._perf.socket_timeout + 0.1)
                self._logger.debug(f"Thread {thread.name} joined")
            except Exception as e:
                self._logger.error(f"Error joining thread {thread.name}: {e}")

        self._logger.info(
            f"Server shutdown complete. Closed {client_count} clients and {thread_count} threads"
        )

    # -------------------------------------------------------------------------
    # Client handler
    # -------------------------------------------------------------------------

    def _handle_client(self, client: ClientInfo) -> None:
        """
        Receive and dispatch messages from a connected client.

        Runs in a dedicated thread per client. The handshake is driven
        inside the recv loop — HELLO is sent before entering the loop,
        and HELLO_ACK arrives naturally as the first message.

        Args:
            client: The connected client to handle.
        """
        self._logger.debug(f"Starting to handle client {client.addr}")

        client.conn.settimeout(self._perf.socket_timeout)

        with self._buffers_lock:
            self._client_buffers[client.conn] = MessageBuffer(
                max_message_size=self.config.max_message_size
            )
            self._logger.debug(f"Created message buffer for client {client.addr}")

        handshake_request_id, hello = self.request_handler.handshake_handler.prepare_hello()
        self.request_handler.register(handshake_request_id)
        self.request_handler.handshake_handler.send_hello(hello, client.conn)

        while True:
            result = recv(client.conn, self.config.buffer_size)

            if result.timed_out:
                continue

            if result.disconnected:
                self._logger.info(f"Client {client.addr} disconnected")
                with self._buffers_lock:
                    self._client_buffers.pop(client.conn, None)
                self.close_client(client)
                break

            try:
                with self._buffers_lock:
                    buffer = self._client_buffers.get(client.conn)

                if buffer is None:
                    self._logger.warning(f"No buffer found for client {client.addr}")
                    continue

                buffer.add_data(result.data)

                for response in buffer.extract_messages():
                    self._logger.debug(
                        f"Received message from client {client.addr}: "
                        f"{response.type.name} (code={response.type.code})"
                    )

                    handler_result = self.request_handler.handle(response, client)
                    if isinstance(handler_result, Exception):
                        self._logger.error(f"Handler error for {client.addr}: {handler_result}")

                    if not client.handshake_done:
                        with self.request_handler.pending_requests_lock:
                            queue = self.request_handler.pending_requests.get(handshake_request_id)
                            is_resolved = queue is not None and not queue.empty()
                            if is_resolved:
                                self.request_handler.pending_requests.pop(
                                    handshake_request_id, None
                                )

                        if is_resolved:
                            client.handshake_done = True
                            self._logger.debug(f"[Handshake] Complete for {client.addr}")

                            if self.on_connect:
                                try:
                                    self.on_connect(client)
                                    self._logger.debug(f"Called on_connect for {client.addr}")
                                except Exception as e:
                                    self._logger.error(
                                        f"Error in on_connect for {client.addr}: "
                                        f"{type(e).__name__}: {e}"
                                    )

            except Exception as e:
                self._logger.error(
                    f"Error processing messages from client {client.addr}: {type(e).__name__}: {e}"
                )

    def close_client(self, client: ClientInfo) -> bool:
        """
        Close a client connection and remove it from the list.

        Args:
            client: The client to disconnect.

        Returns:
            True if the client was found and removed, False otherwise.
        """
        if self.on_disconnect:
            try:
                self.on_disconnect(client)
            except Exception as e:
                self._logger.error(
                    f"Error in on_disconnect for {client.addr}: {type(e).__name__}: {e}"
                )

        with self._buffers_lock:
            if client.conn in self._client_buffers:
                del self._client_buffers[client.conn]
                self._logger.debug(f"Cleaned up buffer for client {client.addr}")

        try:
            client.conn.close()
            self._logger.debug(f"Closed connection for client {client.addr}")
        except Exception as e:
            self._logger.warning(f"Error closing socket for {client.addr}: {type(e).__name__}: {e}")

        with self._clients_lock:
            if client not in self.clients:
                self._logger.warning(f"Client {client.addr} not found in client list")
                return False
            self.clients.remove(client)
            remaining = len(self.clients)

        try:
            with self._threads_lock:
                current = threading.current_thread()
                for id_th, thread in self.threads:
                    if id_th == client.thread_id and thread != current:
                        thread.join(timeout=self._perf.socket_timeout + 0.1)
        except Exception as e:
            self._logger.error(f"Error joining thread for {client.addr}: {type(e).__name__}: {e}")
            return False

        self._logger.info(f"Removed client {client.addr} from list (remaining: {remaining})")
        return True
