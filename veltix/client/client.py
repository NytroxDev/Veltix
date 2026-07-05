# client.py
"""TCP client implementation for Veltix."""

import socket
import time
from typing import Callable, Optional, Union

from ..handler.request_handler import RequestHandler
from ..internal.events import Events, events
from ..logger.core import Logger
from ..network.request import Request, Response
from ..network.sender import Mode, Sender
from ..network.system_types import PING
from ..network.types import MessageType
from ..socket_core.base_socket import BaseSocket, SocketEvents
from .config import ClientConfig
from .disconnect import DisconnectReason, DisconnectState
from .reconnect_handler import ReconnectHandler


class Client:
    """
    TCP client for the Veltix protocol.

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

        self._reconnect_handler: Optional[ReconnectHandler] = None

        self.on_recv: Optional[Callable[[Response], None]] = None
        self.on_connect: Optional[Callable[[], None]] = None
        self.on_disconnect: Optional[Callable] = None

        self.is_connected: bool = False
        self._connecting: bool = False
        self.running: bool = True

        self.init_components()

        self._logger.debug(f"Client initialized for {self.config.server_addr}:{self.config.port}")

    # -------------------------------------------------------------------------
    # Internal initialization
    # -------------------------------------------------------------------------

    def init_components(self) -> None:
        """(Re)initialise all internal components (socket, sender, handler)."""
        old_handler = getattr(self, "request_handler", None)
        old_socket = getattr(self, "socket", None)

        if old_handler:
            old_handler.shutdown(wait=False)
        if old_socket:
            old_socket.close()

        self.socket: BaseSocket = self.config.socket_core.value(
            request_handler=None,
            max_message_size=self.config.max_message_size,
        )
        self.socket.settimeout(0.5)
        self.sender: Sender = Sender(mode=Mode.CLIENT, conn=self.socket)
        self.request_handler: RequestHandler = RequestHandler(
            sender=self.sender,
            mode=Mode.CLIENT,
            max_workers=self.config.max_workers,
        )
        self.socket.request_handler = self.request_handler

        def _on_socket_disconnect() -> None:
            # Ignore disconnect events during connect() or manual disconnect().
            if not self.running or self._connecting:
                return

            self.is_connected = False
            self._try_reconnect(DisconnectReason.SERVER_CLOSED)

        if self._reconnect_handler is None:
            self._reconnect_handler = ReconnectHandler(context=self)

        self.socket.set_callback(SocketEvents.DISCONNECT, _on_socket_disconnect)

    # -------------------------------------------------------------------------
    # Context API
    # -------------------------------------------------------------------------

    def context_connect(self) -> bool:
        """Connect from within a retry context (suppresses own reconnect)."""
        return self.connect(_from_retry=True)

    def context_on_disconnect(self, state: DisconnectState) -> None:
        """Forward disconnect state to the public on_disconnect callback."""
        if self.on_disconnect:
            self.on_disconnect(state)

    def context_init(self) -> None:
        """Reinitialise components before a reconnection attempt."""
        self.init_components()

    def context_set_running(self, value: bool) -> None:
        """Set whether the client is considered running."""
        self.running = value

    def context_set_connected(self, value: bool) -> None:
        """Set the connection flag without triggering side effects."""
        self.is_connected = value

    def context_get_request_handler(self) -> Optional[RequestHandler]:
        """Return the current request handler instance."""
        return self.request_handler

    def context_get_on_recv(self) -> Optional[Callable]:
        """Return the current on_recv callback."""
        return self.on_recv

    def context_get_socket(self) -> Optional[BaseSocket]:
        """Return the current socket instance."""
        return self.socket

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

    def _try_reconnect(self, reason: DisconnectReason) -> bool:
        """Internal reconnect entrypoint used by connect() and tests."""
        handler = self._reconnect_handler
        assert handler is not None
        return handler.try_reconnect(reason)

    def connect(self, _from_retry: bool = False) -> bool:
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
            self._connecting = True
            connected = self.socket.connect(
                self.config.server_addr,
                self.config.port,
                self.config.buffer_size,
                0.5,
            )
            if not connected:
                self._connecting = False
                self._logger.error(
                    f"Connection failed to {self.config.server_addr}:{self.config.port}"
                )
                return False if _from_retry else self._try_reconnect(DisconnectReason.ERROR)

            self.is_connected = True
            self._connecting = False
            assert self._reconnect_handler is not None
            self._reconnect_handler.init_connect()
            self._logger.info(
                f"Successfully connected to server {self.config.server_addr}:{self.config.port}"
            )

            if self.on_connect:
                try:
                    self.on_connect()
                except Exception as e:
                    self._logger.error(f"on_connect error: {type(e).__name__}: {e}")

            return True

        except (socket.timeout, ConnectionRefusedError) as e:
            self._logger.error(
                f"Connection failed to {self.config.server_addr}:{self.config.port}: "
                f"{type(e).__name__}"
            )
            return False if _from_retry else self._try_reconnect(DisconnectReason.ERROR)

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
        self._logger.debug(f"send_and_wait: registering request {request_id.hex()}...")

        self.request_handler.register(request_id)

        if not self.sender.send(request):
            self._logger.error(f"Failed to send request {request_id.hex()}...")
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
        request = Request(PING, b"")
        t_send = time.perf_counter()
        response = self.send_and_wait(request, timeout=timeout)
        t_recv = time.perf_counter()

        if response:
            rtt = (t_recv - t_send) * 1000
            self._logger.info(f"Ping: {rtt:.2f}ms")
            return rtt

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
            assert self._reconnect_handler is not None
            self._reconnect_handler.stop_retry()
            self.request_handler.shutdown(wait=False)
            self.socket.close()
            self._logger.debug("Socket closed")

            self._reconnect_handler.fire_on_disconnect(
                permanent=True, reason=DisconnectReason.MANUAL
            )

            self._logger.info("Successfully disconnected from server")
            return True

        except Exception as e:
            self._logger.error(f"Error during disconnection: {type(e).__name__}: {e}")
            return False

    def stop_retry(self) -> None:
        """Cancel all pending reconnection attempts."""
        if self._reconnect_handler is not None:
            self._reconnect_handler.stop_retry()

    def retry(self, max_: Optional[int] = None) -> None:
        """
        Force reconnection attempts, optionally overriding retry count.

        Args:
            max_: Override retry_max for this session.
        """
        if self._reconnect_handler is not None:
            self._reconnect_handler.retry(max_=max_)

    @property
    def _fail_count(self) -> int:
        """Expose reconnect fail count for backward compatibility and tests."""
        return self._reconnect_handler._fail_count if self._reconnect_handler else 0
