# ruff: noqa: UP035
import dataclasses
import socket
import threading
from queue import Empty, Queue
from typing import Callable, Optional, Union  # noqa: UP035

from ..logger.core import Logger
from ..network.request import Request, Response
from ..network.sender import Mode, Sender
from ..network.system_types import PING, PONG
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
    """

    host: str = "0.0.0.0"
    port: int = 8080

    buffer_size: int = 1024
    max_connection: int = 2


@dataclasses.dataclass
class ClientInfo:
    """
    Information about a connected client.

    Attributes:
        conn (socket.socket): Socket connection to the client
        addr (socket._RetAddress): Client address (host, port)
    """

    conn: socket.socket
    addr: socket._RetAddress


class Server:
    def __init__(self, config: ServerConfig) -> None:
        """
        Initialize the TCP server.

        Args:
            config: Server configuration (host, port, buffer_size, max_connection)
        """
        # Logger setup
        self._logger = Logger.get_instance()

        self._pending_requests: dict[str, Queue] = {}
        self.clients: list[ClientInfo] = []
        self.threads: list[threading.Thread] = []
        self.config: ServerConfig = config
        self.start_th: Optional[threading.Thread] = None
        self.on_recv: Optional[Callable] = None
        self.on_connect: Optional[Callable] = None
        self.running: bool = True

        self.wait_for_ping = False
        self.ping_result: Optional[Response] = None

        self.sender = Sender(mode=Mode.SERVER)

        self.socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.settimeout(0.5)
        self.socket.bind((self.config.host, self.config.port))

        self._logger.info(f"Server initialized on {self.config.host}:{self.config.port}")
        self._logger.debug(
            f"Server config: buffer_size={self.config.buffer_size}, max_connections={self.config.max_connection}"
        )

    def set_callback(self, event: Union[str, Events], func: Callable) -> None:
        """
        Set a callback function to a server event.

        Args:
            event: Event type (Events.ON_RECV, Events.ON_CONNECT or string)
            func: Callback function to execute
                - on_recv: func(client: ClientInfo, msg: Response)
                - on_connect: func(client: ClientInfo)
        """
        events = [Events.ON_RECV, Events.ON_CONNECT]

        for event_ in events:
            if event == event_ or event == event_.value:
                setattr(self, event_.value, func)
                self._logger.debug(f"Bound callback to event: {event_.value}")
                return

        self._logger.warning(f"Unknown event type for binding: {event}")

    def send_and_wait(
        self, request: Request, client: ClientInfo, timeout: float = 5.0
    ) -> Optional[Response]:
        """
        Send a request to client and wait for response.

        Args:
            request: Request to send
            client: Target client
            timeout: Timeout in seconds

        Returns:
            Response object or None if timeout/error
        """
        response_queue = Queue(maxsize=1)
        self._pending_requests[request.request_id] = response_queue

        self._logger.debug(f"Sending request {request.request_id} to client {client.addr}")

        # Send request
        if not self.sender.send(request, client=client.conn):
            del self._pending_requests[request.request_id]
            self._logger.error(
                f"Failed to send request {request.request_id} to client {client.addr}"
            )
            return None

        # Wait for response
        try:
            response = response_queue.get(timeout=timeout)
            self._logger.debug(f"Received response {request.request_id} from client {client.addr}")
            return response
        except Empty:
            self._logger.warning(
                f"Timeout waiting for response {request.request_id} from client {client.addr}"
            )
            return None  # Timeout
        finally:
            # Cleanup
            if request.request_id in self._pending_requests:
                del self._pending_requests[request.request_id]

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
            self.start_th = threading.Thread(target=self.start, args=(True,))
            self.start_th.start()
            return

        self.socket.listen()
        self._logger.info(f"Server listening on {self.config.host}:{self.config.port}")

        while self.running:
            try:
                if len(self.clients) >= self.config.max_connection:
                    continue
                conn, addr = self.socket.accept()
                client = ClientInfo(conn=conn, addr=addr)
                self.clients.append(client)
                self._logger.info(
                    f"New client connected: {addr} (total: {len(self.clients)}/{self.config.max_connection})"
                )
                thread = threading.Thread(target=self.handle_client, args=(client,))
                thread.start()
                self.threads.append(thread)
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

            if msg is None:
                self._logger.info(f"Client {client.addr} disconnected")
                self.close_client(client)
                break

            try:
                response: Response = Request.parse(msg)
                self._logger.debug(
                    f"Received message from client {client.addr}: {response.type.code}"
                )

                # Auto-respond to PING
                if response.type.code == PING.code:
                    pong_request = Request(PONG, b"", request_id=response.request_id)
                    self.sender.send(pong_request, client=client.conn)
                    self._logger.debug(f"Auto-responded with PONG to client {client.addr}")
                    continue

                # Check if someone is waiting for this response
                if response.request_id in self._pending_requests:
                    self._pending_requests[response.request_id].put(response)
                    self._logger.debug(
                        f"Delivered response {response.request_id} to waiting request"
                    )
                else:
                    # Normal callback
                    if self.on_recv:
                        try:
                            self.on_recv(client, response)
                            self._logger.debug(f"Called on_recv callback for client {client.addr}")
                        except Exception as e:
                            self._logger.error(
                                f"Error in on_recv callback for client {client.addr}: {type(e).__name__}: {e}"
                            )

            except Exception as e:
                self._logger.error(
                    f"Error parsing message from client {client.addr}: {type(e).__name__}: {e}"
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
            client.conn.close()
            self._logger.debug(f"Closed connection for client {client.addr}")
        except Exception as e:
            self._logger.warning(
                f"Error closing connection for client {client.addr}: {type(e).__name__}: {e}"
            )

        if client in self.clients:
            self.clients.remove(client)
            self._logger.info(
                f"Removed client {client.addr} from list (remaining: {len(self.clients)})"
            )
            return True
        else:
            self._logger.warning(f"Client {client.addr} not found in client list")
            return False

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
        from ..network.system_types import PING

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
        """
        Stop the server and close all connections.

        - Stops the client acceptance loop
        - Disconnects all clients
        - Waits for threads to finish (timeout 0.1s)
        - Closes the server socket
        """
        self._logger.info("Shutting down server")

        if self.start_th:
            self.running = False
            self._logger.debug("Stopping server main loop")

        # Close all clients
        client_count = len(self.clients)
        for client in self.clients:
            try:
                self.close_client(client)
            except Exception as e:
                self._logger.error(f"Error closing client {client.addr}: {type(e).__name__}: {e}")

        # Wait for threads to finish
        thread_count = len(self.threads)
        for thread in self.threads:
            try:
                thread.join(0.1)
                self._logger.debug(f"Thread {thread.name} joined")
            except Exception as e:
                self._logger.error(f"Error joining thread {thread.name}: {type(e).__name__}: {e}")

        # Close server socket
        try:
            self.socket.close()
            self._logger.info("Server socket closed")
        except Exception as e:
            self._logger.error(f"Error closing server socket: {type(e).__name__}: {e}")

        self._logger.info(
            f"Server shutdown complete. Closed {client_count} clients and {thread_count} threads"
        )
