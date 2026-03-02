import dataclasses
import socket
import threading
from collections.abc import Callable
from threading import Lock
from typing import Optional, Union

from veltix.handler.request_handler import RequestHandler

from ..logger.core import Logger
from ..network.message_buffer import MessageBuffer
from ..network.request import Request, Response
from ..network.sender import Mode, Sender
from ..network.system_types import PING
from ..utils.events import Events
from ..utils.network import recv


@dataclasses.dataclass
class ServerConfig:
    """
    TCP server configuration.

    Attributes:
        host (str): Server listening address (default: '0.0.0.0')
        port (int): Server listening port (default: 8080)
        buffer_size (int): Buffer size for receiving data (default: 1024)
        max_connection (int): Maximum number of simultaneous connections (default: 2)
        max_message_size (int): Maximum allowed message size in bytes (default: 10MB)
    """

    host: str = "0.0.0.0"
    port: int = 8080

    buffer_size: int = 1024
    max_connection: int = 2
    max_message_size: int = 10 * 1024 * 1024  # 10 MB


@dataclasses.dataclass
class ClientInfo:
    """
    Information about a connected client.

    Attributes:
        conn (socket.socket): Socket connection to the client
        addr (socket._RetAddress): Client address (host, port)
    """

    __slots__ = ("conn", "addr", "thread_id")

    conn: socket.socket
    addr: socket._RetAddress

    thread_id: int


class Server:
    __slots__ = (
        "_logger",
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
            config: Server configuration (host, port, buffer_size, max_connection)
        """
        # Logger setup
        self._logger = Logger.get_instance()

        self._client_buffers: dict[socket.socket, MessageBuffer] = {}
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

        self.request_handler = RequestHandler(self.sender, mode=Mode.SERVER)

        self.socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.settimeout(0.5)
        self.socket.bind((self.config.host, self.config.port))

        self._logger.info(f"Server initialized on {self.config.host}:{self.config.port}")
        self._logger.debug(
            f"Server config: buffer_size={self.config.buffer_size}, max_connections={self.config.max_connection}"
        )

    def set_callback(self, event: Union[str, Events], func: Callable) -> None:
        """Set a callback function to a server event."""
        events = [Events.ON_RECV, Events.ON_CONNECT, Events.ON_DISCONNECT]

        for event_ in events:
            if event == event_ or event == event_.value:
                # Set sur Server
                setattr(self, event_.value, func)

                if event_ == Events.ON_RECV:
                    self.request_handler.set_on_recv(func)

                self._logger.debug(f"Bound callback to event: {event_.value}")
                return

        self._logger.warning(f"Unknown event type for binding: {event}")

    def send_and_wait(
        self, request: Request, client: ClientInfo, timeout: float = 5.0
    ) -> Optional[Response]:
        """
        Send a request to a client and block until the matching response is received.

        Registers the request queue before sending to avoid race conditions
        where the response could arrive before wait() is called.

        Args:
            request: Request to send
            client: Target client to send the request to
            timeout: Maximum time to wait for response in seconds (default: 5.0)

        Returns:
            Response object if received within timeout, None if timeout or send failure
        """
        request_id = request.request_id

        self._logger.debug(f"Sending request {request_id} to client {client.addr}")

        # 1. Register BEFORE sending to avoid race condition
        self.request_handler.register(request_id)

        # 2. Send the request
        if not self.sender.send(request, client=client.conn):
            self._logger.error(f"Failed to send request {request_id} to client {client.addr}")
            self.request_handler.unregister(request_id)
            return None

        # 3. Wait for the response
        return self.request_handler.wait(request_id, timeout)

    def get_sender(self) -> Sender:
        """
        Get the sender instance for sending data to clients.

        Returns:
            Sender: The sender instance configured in server mode
        """
        return self.sender

    def get_all_clients_sockets(self) -> list[socket.socket]:
        """
        Get all client sockets.

        Returns:
            list[socket.socket]: List of all connected client sockets
        """
        with self._clients_lock:
            if self.clients is None:
                return []
            return [client.conn for client in self.clients]

    def start(self, _on_th: bool = False) -> None:
        """
        Start the server and begin listening for connections.

        Automatically runs in a separate thread to avoid blocking the program.
        Accepts clients until max_connection is reached.

        Args:
            _on_th: Internal parameter, do not use (indicates if already in a thread)
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
                    current_client_count = len(self.clients)

                if current_client_count >= self.config.max_connection:
                    continue

                conn, addr = self.socket.accept()

                with self._n_th_lock:
                    self.n_th += 1
                    thread_id = self.n_th

                client = ClientInfo(conn=conn, addr=addr, thread_id=thread_id)

                with self._clients_lock:
                    self.clients.append(client)
                    total_clients = len(self.clients)

                self._logger.info(
                    f"New client connected: {addr} (total: {total_clients}/{self.config.max_connection})"
                )
                thread = threading.Thread(target=self.handle_client, args=(client,))
                thread.start()

                with self._threads_lock:
                    self.threads.append((thread_id, thread))
            except TimeoutError:
                continue
            except Exception as e:
                self._logger.error(f"Error accepting connections: {type(e).__name__}: {e}")
                return

    def handle_client(self, client: ClientInfo) -> None:
        """
        Handle communication with a connected client.

        Executed in a separate thread for each client.
        Calls on_connect at the beginning, then on_recv for each received message.
        Automatically closes the connection when the client disconnects.

        Args:
            client: Client information to handle
        """
        self._logger.debug(f"Starting to handle client {client.addr}")

        # Create message buffer for this client
        with self._buffers_lock:
            self._client_buffers[client.conn] = MessageBuffer(
                max_message_size=self.config.max_message_size
            )
            self._logger.debug(f"Created message buffer for client {client.addr}")

        if self.on_connect:
            try:
                self.on_connect(client)
                self._logger.debug(f"Called on_connect callback for client {client.addr}")
            except Exception as e:
                import traceback

                traceback.print_exc()
                self._logger.error(
                    f"Error in on_connect callback for client {client.addr}: {type(e).__name__}: {e}"
                )

        while True:
            msg = recv(client.conn, self.config.buffer_size)

            self._logger.trace(f"Received message: {msg}")

            if msg is None:
                self._logger.info(f"Client {client.addr} disconnected")

                # Clean up buffer
                with self._buffers_lock:
                    if client.conn in self._client_buffers:
                        del self._client_buffers[client.conn]
                        self._logger.debug(f"Cleaned up buffer for client {client.addr}")

                self.close_client(client)
                break

            try:
                # Get buffer for this client
                with self._buffers_lock:
                    buffer = self._client_buffers.get(client.conn)

                if buffer is None:
                    self._logger.warning(f"No buffer found for client {client.addr}")
                    continue

                # Add received data to buffer
                buffer.add_data(msg)

                # Extract all complete messages
                messages = buffer.extract_messages()

                # Process each message
                for response in messages:
                    self._logger.debug(
                        f"Received message from client {client.addr}: {response.type.code}"
                    )

                    result = self.request_handler.handle(response, client)
                    if isinstance(result, Exception):
                        self._logger.error(f"Handler error for {client.addr}: {result}")

            except Exception as e:
                self._logger.error(
                    f"Error processing messages from client {client.addr}: {type(e).__name__}: {e}"
                )

    def close_client(self, client: ClientInfo) -> bool:
        """
        Close a client connection and remove it from the list.

        Args:
            client: The client to disconnect

        Returns:
            True if the client was in the list and was removed, False otherwise
        """

        try:
            if self.on_disconnect:
                self.on_disconnect(client)
        except Exception as e:
            self._logger.error(
                f"Error calling on_disconnect for client {client.addr}: {type(e).__name__}: {e}"
            )

        # Clean up buffer (redundant safety)
        with self._buffers_lock:
            if client.conn in self._client_buffers:
                del self._client_buffers[client.conn]
                self._logger.debug(f"Cleaned up buffer for client {client.addr} in close_client")

        try:
            client.conn.close()
            self._logger.debug(f"Closed connection for client {client.addr}")
        except Exception as e:
            self._logger.warning(
                f"Error closing connection for client {client.addr}: {type(e).__name__}: {e}"
            )

        with self._clients_lock:
            if client in self.clients:
                self.clients.remove(client)
                remaining_clients = len(self.clients)
            else:
                self._logger.warning(f"Client {client.addr} not found in client list")
                return False

        try:
            with self._threads_lock:
                for id_th, thread in self.threads:
                    if thread.is_alive() and id_th == client.thread_id:
                        thread.join(0.01)
        except Exception as e:
            self._logger.error(f"Error closing client {client.addr}: {type(e).__name__}: {e}")
            return False

        self._logger.info(
            f"Removed client {client.addr} from list (remaining: {remaining_clients})"
        )
        return True

    def ping_client_async(
        self, client: ClientInfo, callback: Callable[[Optional[float]], None], timeout: float = 5.0
    ) -> None:
        """
        Ping a client asynchronously and call callback with result.

        This method is safe to call from within client handler threads.

        Args:
            client: Client to ping
            callback: Function to call with latency result (float or None)
            timeout: Timeout in seconds
        """
        import threading

        def ping_thread():
            try:
                latency = self.ping_client(client, timeout=timeout)
                callback(latency)
            except Exception as e:
                self._logger.error(f"Error in async ping: {e}")
                callback(None)

        thread = threading.Thread(target=ping_thread)
        thread.start()

    def ping_client(self, client: ClientInfo, timeout: float = 5.0) -> float | None:
        """
        Ping a client and measure latency.

        Args:
            client: Client to ping
            timeout: Timeout in seconds

        Returns:
            Latency in milliseconds, or None if timeout
        """

        self._logger.debug(f"Pinging client {client.addr}")
        ping_request = Request(PING, b"")
        response = self.send_and_wait(ping_request, client, timeout=timeout)

        if response:
            latency = response.latency
            self._logger.info(f"Ping response from client {client.addr}: {latency:.2f}ms")
            return latency
        else:
            self._logger.warning(f"Ping timeout for client {client.addr}")
            return None

    def close_all(self) -> None:
        """Stop the server and close all connections."""
        self._logger.info("Shutting down server")

        # Stop the main loop
        self.running = False
        self._logger.debug("Stopping server main loop")

        # Close server socket FIRST (force accept() to fail)
        try:
            self.socket.close()
            self._logger.info("Server socket closed")
        except Exception as e:
            self._logger.error(f"Error closing server socket: {e}")

        # Wait for main thread to finish
        if self.start_th and self.start_th.is_alive():
            self._logger.debug("Waiting for main thread to finish...")
            self.start_th.join(timeout=2.0)  # ← AJOUTE ÇA !
            if self.start_th.is_alive():
                self._logger.warning("Main thread did not finish in time")
            else:
                self._logger.debug("Main thread finished")

        # Close all clients
        with self._clients_lock:
            clients_to_close = list(self.clients)
            client_count = len(clients_to_close)

        for client in clients_to_close:
            try:
                self.close_client(client)
            except Exception as e:
                self._logger.error(f"Error closing client {client.addr}: {e}")

        # Wait for client threads
        with self._threads_lock:
            threads_to_join = list(self.threads)
            thread_count = len(threads_to_join)

        for _, thread in threads_to_join:
            try:
                thread.join(0.1)  # Augmente le timeout si nécessaire
                self._logger.debug(f"Thread {thread.name} joined")
            except Exception as e:
                self._logger.error(f"Error joining thread {thread.name}: {e}")

        self._logger.info(
            f"Server shutdown complete. Closed {client_count} clients and {thread_count} threads"
        )
