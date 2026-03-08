"""TCP client implementation for Veltix."""

import dataclasses
import socket
import threading
import time
from collections.abc import Callable
from enum import Enum, auto
from threading import Event
from typing import Optional, Union

from ..handler.request_handler import RequestHandler
from ..logger.core import Logger
from ..network.message_buffer import MessageBuffer
from ..network.request import Request, Response
from ..network.sender import Mode, Sender
from ..network.system_types import HELLO, PING
from ..network.types import MessageType
from ..utils.buffer_size import BufferSize
from ..utils.events import Events, events
from ..utils.network import recv
from ..utils.performance_mode import PerformanceMode, get_settings

# ============================================================================
# DISCONNECT STATE
# ============================================================================


class DisconnectReason(Enum):
    """
    Reason for a disconnection.

    Attributes:
        SERVER_CLOSED: Server closed the connection cleanly.
        ERROR:         Fatal network error (reset, aborted, etc.).
        MANUAL:        disconnect() was called manually by the user.
    """

    SERVER_CLOSED = auto()
    ERROR = auto()
    MANUAL = auto()


@dataclasses.dataclass
class DisconnectState:
    """
    State passed to the on_disconnect callback.

    Attributes:
        permanent:   True if the client has given up reconnecting.
                     False if a reconnection attempt will follow.
        attempt:     Current retry attempt number (0 = first disconnection,
                     before any retry has been attempted).
        retry_max:   Maximum number of retry attempts configured.
        reason:      Why the disconnection occurred.
    """

    permanent: bool
    attempt: int
    retry_max: int
    reason: DisconnectReason


# ============================================================================
# CONFIGURATION
# ============================================================================


@dataclasses.dataclass
class ClientConfig:
    """
    TCP client configuration.

    Attributes:
        server_addr:      Server address to connect to.
        port:             Server port to connect to.
        buffer_size:      Buffer size for receiving data in bytes.
                          Use BufferSize enum for common presets (default: BufferSize.SMALL).
                          Can also be set to any custom integer value.
        max_message_size: Maximum allowed message size in bytes (default: 10MB).
        handshake_timeout: Maximum time to wait for handshake completion (default: 5.0s).
        max_workers:      Number of worker threads for callback execution (default: 4).
                          Increase if your on_recv callback is slow or blocking.
        retry:            Number of reconnection attempts on failure (default: 0 = disabled).
                          Applies both to the initial connect() and to mid-session disconnections.
        retry_delay:      Seconds to wait between reconnection attempts (default: 1.0).
        performance_mode: Controls internal timing parameters (default: BALANCED).
    """

    server_addr: str = "127.0.0.1"
    port: int = 8080
    buffer_size: int = BufferSize.SMALL
    max_message_size: int = 10 * 1024 * 1024  # 10 MB
    handshake_timeout: float = 5.0
    max_workers: int = 4
    retry: int = 0
    retry_delay: float = 1.0
    performance_mode: PerformanceMode = PerformanceMode.BALANCED


# ============================================================================
# CLIENT
# ============================================================================


class Client:
    """
    TCP client for Veltix protocol.

    Connects to a Veltix server and handles bidirectional communication.
    connect() blocks until the handshake is complete before returning,
    so it is always safe to send messages immediately after connect() returns True.

    If retry > 0, the client automatically attempts to reconnect both on
    initial connection failure and on mid-session disconnections.
    The on_disconnect callback receives a DisconnectState at each attempt,
    letting the caller display progress or cancel retries via stop_retry().
    """

    def __init__(self, config: ClientConfig) -> None:
        """
        Initialize the TCP client.

        Args:
            config: Client configuration.
        """
        self._logger = Logger.get_instance()
        self.config: ClientConfig = config

        # Resolve performance mode settings once
        self._perf = get_settings(config.performance_mode)

        # Event callbacks — set via set_callback()
        self.on_recv: Optional[Callable[[Response], None]] = None
        self.on_connect: Optional[Callable[[], None]] = None
        self.on_disconnect: Optional[Callable[[DisconnectState], None]] = None

        # Connection state
        self.is_connected: bool = False
        self.running: bool = True
        self.thread_handler: Optional[threading.Thread] = None

        # Retry state
        self._fail_count: int = 0
        self._stop_retry_flag: bool = False

        # Internal components — re-created on reconnect via _reset()
        self._init_components()

        self._logger.debug(
            f"Client initialized for {self.config.server_addr}:{self.config.port} "
            f"[{config.performance_mode.name}]"
        )

    # -------------------------------------------------------------------------
    # Internal initialization
    # -------------------------------------------------------------------------

    def _init_components(self) -> None:
        """Initialize (or re-initialize) all internal components."""
        self.socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(self._perf.socket_timeout)
        self.sender: Sender = Sender(mode=Mode.CLIENT, conn=self.socket)
        self.request_handler: RequestHandler = RequestHandler(
            sender=self.sender,
            mode=Mode.CLIENT,
            max_workers=self.config.max_workers,
        )
        self._message_buffer: MessageBuffer = MessageBuffer(
            max_message_size=self.config.max_message_size
        )
        self._handshake_done: Event = Event()

    def _reset(self) -> None:
        """
        Reset all internal state for a fresh reconnection attempt.

        Called automatically when a mid-session disconnection is detected
        and retry is enabled.
        """
        self._logger.debug("Resetting client state for reconnection")
        self.is_connected = False
        self.running = True
        self._init_components()

        # Re-bind on_recv to the new request_handler
        if self.on_recv:
            self.request_handler.set_on_recv(self.on_recv)

    # -------------------------------------------------------------------------
    # Retry control
    # -------------------------------------------------------------------------

    def stop_retry(self) -> None:
        """
        Cancel all pending reconnection attempts.

        If a retry loop is running, it will stop after the current attempt
        and fire on_disconnect with permanent=True.
        """
        self._logger.info("stop_retry() called — cancelling reconnection attempts")
        self._stop_retry_flag = True

    def retry(self, max_: Optional[int] = None) -> None:
        """
        Force an immediate reconnection attempt, even if retry_max was reached.

        Args:
            max_: Override retry_max for this session (optional).
        """
        if max_ is not None:
            self.config = dataclasses.replace(self.config, retry=max_)
            self._logger.info(f"retry() called — new retry_max={max_}")
        else:
            self._logger.info("retry() called — forcing reconnection attempt")

        self._stop_retry_flag = False
        self._fail_count = 0
        self._reset()
        threading.Thread(target=self._reconnect_loop, daemon=True).start()

    # -------------------------------------------------------------------------
    # Internal retry logic
    # -------------------------------------------------------------------------

    def _fire_on_disconnect(self, permanent: bool, reason: DisconnectReason) -> None:
        """Fire the on_disconnect callback with the current retry state."""
        if self.on_disconnect:
            state = DisconnectState(
                permanent=permanent,
                attempt=self._fail_count,
                retry_max=self.config.retry,
                reason=reason,
            )
            try:
                self.on_disconnect(state)
            except Exception as e:
                self._logger.error(f"Error in on_disconnect callback: {type(e).__name__}: {e}")

    def _reconnect_loop(self, reason: DisconnectReason = DisconnectReason.SERVER_CLOSED) -> bool:
        """
        Attempt reconnection up to config.retry times.

        Fires on_disconnect at each failed attempt with permanent=False,
        and a final time with permanent=True if all attempts are exhausted
        or stop_retry() was called.

        Returns:
            True if reconnection succeeded, False otherwise.
        """
        while not self._stop_retry_flag and self._fail_count < self.config.retry:
            self._fail_count += 1
            self._logger.info(
                f"Reconnection attempt {self._fail_count}/{self.config.retry} "
                f"in {self.config.retry_delay}s..."
            )
            time.sleep(self.config.retry_delay)

            self._reset()
            if self.connect():
                return True

            # Attempt failed — notify caller
            self._fire_on_disconnect(permanent=False, reason=reason)

        # All attempts exhausted or stop_retry() called
        self._fire_on_disconnect(permanent=True, reason=reason)
        return False

    def _try_reconnect(self, reason: DisconnectReason) -> bool:
        """
        Start the reconnect loop if retry is enabled.

        Returns:
            True if reconnection eventually succeeded, False otherwise.
        """
        if self.config.retry == 0:
            self._fire_on_disconnect(permanent=True, reason=reason)
            return False

        return self._reconnect_loop(reason)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def set_callback(self, event: Union[str, Events], func: Callable) -> None:
        """
        Bind a callback function to a client event.

        Args:
            event: Event type (Events enum or string).
            func: Callback function:
                - ON_RECV:       func(response: Response)
                - ON_CONNECT:    func()
                - ON_DISCONNECT: func(state: DisconnectState)
        """
        for event_ in events:
            if event == event_ or event == event_.value:
                setattr(self, event_.value, func)

                if event_ == Events.ON_RECV:
                    self.request_handler.set_on_recv(func)

                self._logger.debug(f"Bound callback to event: {event_.value}")
                return

        self._logger.warning(f"Unknown event type: {event}")

    def route(self, type_: MessageType) -> Callable:
        """
        Decorator to register a route callback for a specific message type.

        Usage:
            @client.route(MY_TYPE)
            def on_my_type(response: Response, client=None) -> None:
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

    def connect(self) -> bool:
        """
        Connect to the server and start the message handler thread.

        Blocks until the handshake is complete (or times out) before returning,
        so it is safe to send messages immediately after this returns True.

        If the connection fails and retry > 0, automatically retries up to
        config.retry times with config.retry_delay seconds between attempts.

        Returns:
            True if connection and handshake succeeded, False otherwise.
        """
        try:
            self._logger.info(f"Connecting to server {self.config.server_addr}:{self.config.port}")
            self.socket.connect((self.config.server_addr, self.config.port))
            self.is_connected = True
            self._fail_count = 0
            self._stop_retry_flag = False
            self._logger.info(
                f"Successfully connected to server {self.config.server_addr}:{self.config.port}"
            )

            self.thread_handler = threading.Thread(target=self._handle_client, daemon=True)
            self.thread_handler.start()
            self._logger.debug("Started client message handler thread")

            handshake_ok = self._handshake_done.wait(timeout=self.config.handshake_timeout)

            if not handshake_ok:
                self._logger.error(
                    f"Handshake timeout after {self.config.handshake_timeout}s — disconnecting"
                )
                self.disconnect()
                return False

            return True

        except (TimeoutError, ConnectionRefusedError) as e:
            self._logger.error(
                f"Connection failed to {self.config.server_addr}:{self.config.port}: "
                f"{type(e).__name__}"
            )
            return self._try_reconnect(DisconnectReason.ERROR)

        except Exception as e:
            self._logger.error(f"Unexpected error during connection: {type(e).__name__}: {e}")
            return False

    def get_sender(self) -> Sender:
        """Return the sender instance."""
        return self.sender

    def send_and_wait(self, request: Request, timeout: float = 5.0) -> Optional[Response]:
        """
        Send a request and block until the matching response is received.

        The request queue is registered before sending to avoid a race condition
        where the response could arrive before wait() is called.

        Args:
            request: Request to send.
            timeout: Maximum time to wait for a response in seconds (default: 5.0).

        Returns:
            Matching Response, or None on timeout or send failure.
        """
        request_id = request.request_id
        self._logger.debug(f"send_and_wait: registering request {request_id[:8]}...")

        self.request_handler.register(request_id)

        if not self.sender.send(request):
            self._logger.error(f"Failed to send request {request_id[:8]}...")
            self.request_handler.unregister(request_id)
            return None

        return self.request_handler.wait(request_id, timeout)

    def ping_server(self, timeout: float = 5.0) -> Optional[float]:
        """
        Ping the server and measure round-trip latency.

        Args:
            timeout: Maximum time to wait for pong in seconds (default: 5.0).

        Returns:
            Latency in milliseconds, or None on timeout.
        """
        self._logger.debug("Pinging server")
        response = self.send_and_wait(Request(PING, b""), timeout=timeout)

        if response:
            self._logger.info(f"Ping: {response.latency:.2f}ms")
            return response.latency

        self._logger.warning("Ping timed out")
        return None

    def disconnect(self) -> bool:
        """
        Disconnect from the server and clean up resources.

        Fires on_disconnect with reason=MANUAL and permanent=True.

        Returns:
            True if disconnection succeeded, False on unexpected error.
        """
        try:
            self._logger.info("Disconnecting from server")
            self.running = False
            self.is_connected = False
            self._stop_retry_flag = True
            self.socket.close()
            self._logger.debug("Socket closed")

            if self.thread_handler and threading.current_thread() != self.thread_handler:
                self.thread_handler.join(timeout=self._perf.socket_timeout + 0.1)
                self._logger.debug("Message handler thread joined")

            self._fire_on_disconnect(permanent=True, reason=DisconnectReason.MANUAL)

            self._logger.info("Successfully disconnected from server")
            return True

        except Exception as e:
            self._logger.error(f"Error during disconnection: {type(e).__name__}: {e}")
            return False

    # -------------------------------------------------------------------------
    # Internal message loop
    # -------------------------------------------------------------------------

    def _handle_client(self) -> None:
        """
        Receive and dispatch messages from the server.

        Runs in a dedicated background thread. Unblocks connect() once the
        HELLO handshake message is processed.

        On disconnection, fires on_disconnect and automatically attempts to
        reconnect if retry > 0.
        """
        self._logger.debug("Client message handler started")

        while self.running:
            result = recv(self.socket, self.config.buffer_size)

            if result.timed_out:
                # Socket timeout — connection still alive, loop again
                continue

            if result.disconnected:
                if not self.running:
                    # Manual disconnect() was called — on_disconnect already fired
                    break

                self._logger.info("Server disconnected")
                self._handshake_done.set()
                self.is_connected = False

                reason = (
                    DisconnectReason.SERVER_CLOSED
                    if result.status.name == "CLOSED"
                    else DisconnectReason.ERROR
                )

                if self.config.retry != 0 and not self._stop_retry_flag:
                    # Fire initial on_disconnect before starting retry loop
                    self._fire_on_disconnect(permanent=False, reason=reason)
                    self._reconnect_loop(reason)
                else:
                    self._fire_on_disconnect(permanent=True, reason=reason)

                break

            # result.ok — process received data
            try:
                self._message_buffer.add_data(result.data)

                for response in self._message_buffer.extract_messages():
                    self._logger.debug(
                        f"Received message from server: {response.type.name} "
                        f"(code={response.type.code})"
                    )
                    self.request_handler.handle(response)

                    if not self._handshake_done.is_set() and response.type == HELLO:
                        self._handshake_done.set()
                        self._logger.debug("Handshake complete — connect() unblocked")

                        if self.on_connect:
                            try:
                                self.on_connect()
                                self._logger.debug("Called on_connect callback")
                            except Exception as e:
                                self._logger.error(
                                    f"Error in on_connect callback: {type(e).__name__}: {e}"
                                )

            except Exception as e:
                self._logger.error(f"Error processing message from server: {type(e).__name__}: {e}")
