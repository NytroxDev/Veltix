"""TCP client implementation for Veltix."""

import dataclasses
import socket
import threading
from collections.abc import Callable
from typing import Optional, Union

from ..handler.request_handler import RequestHandler
from ..logger.core import Logger
from ..network.message_buffer import MessageBuffer
from ..network.request import Request, Response
from ..network.sender import Mode, Sender
from ..network.system_types import PING
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
        max_message_size: Maximum allowed message size in bytes (default: 10MB)
    """

    server_addr: str = "127.0.0.1"
    port: int = 8080
    buffer_size: int = 1024
    max_message_size: int = 10 * 1024 * 1024  # 10 MB


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

        self._message_buffer = MessageBuffer(max_message_size=config.max_message_size)

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

        self.request_handler = RequestHandler(sender=self.sender, mode=Mode.CLIENT)

        self._logger.debug(
            f"Client initialized for server {self.config.server_addr}:{self.config.port}"
        )

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
            self.request_handler.set_on_recv(func)
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
            self._logger.info(
                f"Successfully connected to server {self.config.server_addr}:{self.config.port}"
            )

            # Start message handler thread
            self.thread_handler = threading.Thread(target=self.handle_client, daemon=True)
            self.thread_handler.start()

            self._logger.debug("Started client message handler thread")

            return True

        except (TimeoutError, ConnectionRefusedError) as e:
            self._logger.error(
                f"Connection failed to {self.config.server_addr}:{self.config.port}: {type(e).__name__}"
            )
            return False
        except Exception as e:
            self._logger.error(f"Unexpected error during connection: {type(e).__name__}: {e}")
            return False

    def get_sender(self) -> Sender:
        """Get the sender instance."""
        return self.sender

    def send_and_wait(self, request: Request, timeout: float = 5.0) -> Optional[Response]:
        """
        Send a request and block until the matching response is received.

        Registers the request queue before sending to avoid race conditions
        where the response could arrive before wait() is called.

        Args:
            request: Request to send
            timeout: Maximum time to wait for response in seconds (default: 5.0)

        Returns:
            Response object if received within timeout, None if timeout or send failure
        """
        request_id = request.request_id

        self._logger.debug(f"Sending request {request_id} and waiting for response")

        # 1. Register before sending to avoid race condition
        self.request_handler.register(request_id)

        # 2. Send the request
        if not self.sender.send(request):
            self._logger.error(f"Failed to send request {request_id}")
            self.request_handler.unregister(request_id)
            return None

        # 3. Wait for the response
        return self.request_handler.wait(request_id, timeout)

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
                # Add data to buffer
                self._message_buffer.add_data(msg)

                # Extract all complete messages
                messages = self._message_buffer.extract_messages()

                # Process each message
                for response in messages:
                    self._logger.debug(f"Received message from server: {response.type.code}")
                    self.request_handler.handle(response)

            except Exception as e:
                self._logger.error(
                    f"Error processing messages from server: {type(e).__name__}: {e}"
                )

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
            if self.thread_handler and threading.current_thread() != self.thread_handler:
                self.thread_handler.join(timeout=0.1)
                self._logger.debug("Message handler thread joined")

            self._logger.info("Successfully disconnected from server")
            return True

        except Exception as e:
            self._logger.error(f"Error during disconnection: {type(e).__name__}: {e}")
            return False
