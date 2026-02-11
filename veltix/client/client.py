"""TCP client implementation for Veltix."""

import dataclasses
import socket
import threading
from queue import Empty, Queue
from typing import Callable, Optional, Union

from ..logger.core import Logger
from ..network.request import Request, Response
from ..network.sender import Mode, Sender
from ..network.system_types import PING, PONG
from ..utils.events import Events
from ..utils.network import recv


@dataclasses.dataclass
class ClientConfig:
    """
    TCP client configuration.

    Attributes:
        server_addr: Server address to connect to
        port: Server port to connect to
        buffer_size: Buffer size for receiving data in bytes
    """

    server_addr: str = "127.0.0.1"
    port: int = 8080
    buffer_size: int = 1024


class Client:
    """
    TCP client for Veltix protocol.

    Connects to a Veltix server and handles bidirectional communication.
    """

    def __init__(self, config: ClientConfig) -> None:
        """
        Initialize the TCP client.

        Args:
            config: Client configuration
        """
        # Logger setup
        self._logger = Logger.get_instance()
        
        # Pending request/response tracking
        self._pending_requests: dict[str, Queue] = {}

        # Configuration
        self.config: ClientConfig = config

        # Socket
        self.socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Event callback
        self.on_recv: Optional[Callable[[Response], None]] = None

        # Connection state
        self.is_connected: bool = False
        self.running: bool = True
        self.thread_handler: Optional[threading.Thread] = None

        # Sender
        self.sender = Sender(mode=Mode.CLIENT, conn=self.socket)
        
        self._logger.debug(f"Client initialized for server {self.config.server_addr}:{self.config.port}")

    def set_callback(self, event: Union[str, Events], func: Callable) -> None:
        """
        Set a callback function to a client event.

        Args:
            event: Event type (Events enum or string)
            func: Callback function
                - ON_RECV: func(msg: Response)
        """
        if event == Events.ON_RECV or event == Events.ON_RECV.value:
            self.on_recv = func
            self._logger.debug("Bound callback to ON_RECV event")
        else:
            self._logger.warning(f"Unknown event type for callback: {event}")

    def connect(self) -> bool:
        """
        Connect to the server and start listening.

        Returns:
            True if connection succeeded, False otherwise
        """
        try:
            self._logger.info(f"Connecting to server {self.config.server_addr}:{self.config.port}")
            self.socket.connect((self.config.server_addr, self.config.port))
            self.is_connected = True
            self._logger.info(f"Successfully connected to server {self.config.server_addr}:{self.config.port}")

            # Start message handler thread
            self.thread_handler = threading.Thread(
                target=self.handle_client, daemon=True
            )
            self.thread_handler.start()
            self._logger.debug("Started client message handler thread")

            return True

        except (ConnectionRefusedError, socket.timeout) as e:
            self._logger.error(f"Connection failed to {self.config.server_addr}:{self.config.port}: {type(e).__name__}")
            return False
        except Exception as e:
            self._logger.error(f"Unexpected error during connection: {type(e).__name__}: {e}")
            return False

    def get_sender(self) -> Sender:
        """Get the sender instance."""
        return self.sender

    def send_and_wait(
        self, request: Request, timeout: float = 5.0
    ) -> Optional[Response]:
        """
        Send a request and wait for matching response.

        Args:
            request: Request to send
            timeout: Wait timeout in seconds

        Returns:
            Response or None if timeout/error
        """
        response_queue: Queue = Queue(maxsize=1)
        self._pending_requests[request.request_id] = response_queue

        self._logger.debug(f"Sending request {request.request_id} to server")

        # Send request
        if not self.sender.send(request):
            del self._pending_requests[request.request_id]
            self._logger.error(f"Failed to send request {request.request_id}")
            return None

        # Wait for response
        try:
            response = response_queue.get(timeout=timeout)
            self._logger.debug(f"Received response {request.request_id} from server")
            return response
        except Empty:
            self._logger.warning(f"Timeout waiting for response {request.request_id}")
            return None
        finally:
            # Cleanup
            self._pending_requests.pop(request.request_id, None)

    def ping_server(self, timeout: float = 5.0) -> Optional[float]:
        """
        Ping server and measure latency.

        Args:
            timeout: Timeout in seconds

        Returns:
            Latency in milliseconds, or None if timeout
        """
        self._logger.debug("Pinging server")
        ping_request = Request(PING, b"")
        response = self.send_and_wait(ping_request, timeout=timeout)

        if response:
            latency = response.latency
            self._logger.info(f"Ping response from server: {latency:.2f}ms")
            return latency
        else:
            self._logger.warning("Ping timeout for server")
            return None

    def handle_client(self) -> None:
        """
        Handle communication with the server.

        Runs in a separate thread.
        """
        self._logger.debug("Starting client message handler")
        
        while self.running:
            msg = recv(self.socket, self.config.buffer_size)

            if msg is None:
                self._logger.info("Server disconnected")
                self.disconnect()
                break

            try:
                response: Response = Request.parse(msg)
                self._logger.debug(f"Received message from server: {response.type.code}")

                # Auto-respond to PING
                if response.type.code == PING.code:
                    pong_request = Request(PONG, b"", request_id=response.request_id)
                    self.sender.send(pong_request)
                    self._logger.debug("Auto-responded with PONG to server")
                    continue

                # Check for pending request
                if response.request_id in self._pending_requests:
                    self._pending_requests[response.request_id].put(response)
                    self._logger.debug(f"Delivered response {response.request_id} to waiting request")
                else:
                    # Normal callback
                    if self.on_recv:
                        try:
                            self.on_recv(response)
                            self._logger.debug("Called on_recv callback")
                        except Exception as e:
                            self._logger.error(f"Error in on_recv callback: {type(e).__name__}: {e}")

            except Exception as e:
                self._logger.error(f"Error parsing message from server: {type(e).__name__}: {e}")

    def disconnect(self) -> bool:
        """
        Disconnect from the server.

        Returns:
            True if disconnection succeeded, False otherwise
        """
        try:
            self._logger.info("Disconnecting from server")
            self.running = False
            self.socket.close()
            self.is_connected = False
            self._logger.debug("Socket closed, connection state updated")

            # Wait for handler thread if not current thread
            if (
                self.thread_handler
                and threading.current_thread() != self.thread_handler
            ):
                self.thread_handler.join(timeout=1.0)
                self._logger.debug("Message handler thread joined")

            self._logger.info("Successfully disconnected from server")
            return True

        except Exception as e:
            self._logger.error(f"Error during disconnection: {type(e).__name__}: {e}")
            return False
