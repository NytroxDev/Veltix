# client.py
"""TCP client implementation for Veltix."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..internal.bus import VeltixBus
from .config import ClientConfig  # noqa: TC001 - re-exported by __init__.py
from .core import ClientCore
from .disconnect import DisconnectReason  # noqa: TC001 - re-exported by __init__.py
from .lifecycle import ClientLifecycle
from .messaging import ClientMessaging
from .routing import ClientRouting

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..handler.request_handler import RequestHandler
    from ..network.request import Request
    from ..network.response import Response
    from ..network.sender import Sender
    from ..network.types import MessageType
    from ..socket_core.base_socket import BaseSocket
    from .disconnect import DisconnectState


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
        self._core = ClientCore(config, VeltixBus())
        self._connection = ClientLifecycle(self._core)
        self._messaging = ClientMessaging(self._core)
        self._routing = ClientRouting(self._core)

        self.init_components()

        self.bus.debug(f"Client initialized for {self.config.server_addr}:{self.config.port}")

    # -------------------------------------------------------------------------
    # Internal initialization
    # -------------------------------------------------------------------------

    def init_components(self) -> None:
        """(Re)initialise all internal components (socket, sender, handler)."""
        self._connection.init_components()

    @property
    def config(self) -> ClientConfig:
        """Return the client configuration."""
        return self._core.config

    @property
    def bus(self) -> VeltixBus:
        """Return the event bus for this client."""
        return self._core.bus

    @property
    def socket(self) -> BaseSocket:
        """Return the active socket backend."""
        return self._core.socket

    @property
    def request_handler(self) -> RequestHandler:
        """Return the underlying request handler."""
        return self._core.request_handler

    @property
    def is_connected(self) -> bool:
        """Return whether the client currently holds a live connection."""
        return self._connection.is_connected

    @property
    def running(self) -> bool:
        """Return whether the client is still considered running."""
        return self._connection.running

    @property
    def _fail_count(self) -> int:
        """Expose reconnect fail count for backward compatibility and tests."""
        return self._connection._fail_count

    # -------------------------------------------------------------------------
    # Internal context (used by ReconnectHandler)
    # -------------------------------------------------------------------------

    def _context_connect(self) -> bool:
        """Connect from within a retry context (suppresses own reconnect)."""
        return self._connection._context_connect()

    def _context_on_disconnect(self, state: DisconnectState) -> None:
        """Forward disconnect state to subscribers."""
        self._connection._context_on_disconnect(state)

    def _context_init(self) -> None:
        """Reinitialise components before a reconnection attempt."""
        self._connection._context_init()

    def _context_set_running(self, value: bool) -> None:
        """Set whether the client is considered running."""
        self._connection._context_set_running(value)

    def _context_set_connected(self, value: bool) -> None:
        """Set the connection flag without triggering side effects."""
        self._connection._context_set_connected(value)

    def _context_get_request_handler(self) -> RequestHandler | None:
        """Return the current request handler instance."""
        return self._connection._context_get_request_handler()

    def _context_get_on_recv(self) -> Callable | None:
        """Return the current on_recv callback."""
        return self._connection._context_get_on_recv()

    def _context_get_socket(self) -> BaseSocket | None:
        """Return the current socket instance."""
        return self._connection._context_get_socket()

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def on_recv(self, func: Callable) -> None:
        """Register a callback for all received messages (before routing).

        Args:
            func: func(response: Response)
        """
        self._routing.on_recv(func)

    def on_connect(self, func: Callable) -> None:
        """Register a callback for successful connection.

        Multiple callbacks can be registered and will be called in order.

        Args:
            func: func()
        """
        self._routing.on_connect(func)

    def on_disconnect(self, func: Callable) -> None:
        """Register a callback for disconnection.

        Multiple callbacks can be registered and will be called in order.

        Args:
            func: func(state: DisconnectState)
        """
        self._routing.on_disconnect(func)

    def route(self, type_: MessageType) -> Callable:
        """
        Decorator to register a route callback for a specific message type.

        Usage:
            @client.route(MY_TYPE)
            def on_my_type(response: Response) -> None:
                ...

        Args:
            type_: Message type to intercept.

        Returns:
            Decorator function.
        """
        return self._routing.route(type_)

    def _try_reconnect(self, reason: DisconnectReason) -> bool:
        """Internal reconnect entrypoint used by connect() and tests."""
        return self._connection._try_reconnect(reason)

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
        return self._connection.connect(_from_retry=_from_retry)

    @property
    def sender(self) -> Sender:
        """Return the sender instance for this client."""
        return self._core.sender

    def send(self, request: Request) -> bool:
        """Send a request to the server.

        Args:
            request: Request to send.

        Returns:
            True if the send succeeded.
        """
        return self._messaging.send(request)

    def send_and_wait(self, request: Request, timeout: float = 5.0) -> Response | None:
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
        return self._messaging.send_and_wait(request, timeout=timeout)

    def ping_server(self, timeout: float = 5.0) -> float | None:
        """
        Ping the server and measure round-trip latency.

        Args:
            timeout: Maximum time to wait for pong in seconds (default: 5.0).

        Returns:
            Latency in milliseconds, or None on timeout.
        """
        return self._messaging.ping_server(timeout)

    def disconnect(self) -> bool:
        """
        Disconnect from the server and clean up resources.

        Fires on_disconnect with reason=MANUAL and permanent=True.

        Returns:
            True if disconnection succeeded, False on unexpected error.
        """
        return self._connection.disconnect()

    def stop_retry(self) -> None:
        """Cancel all pending reconnection attempts."""
        self._connection.stop_retry()

    def wait_until_closed(self) -> None:
        """Block until the client is disconnected (via disconnect() or server close)."""
        self._connection.wait_until_closed()

    def retry(self, max_: int | None = None) -> None:
        """
        Force reconnection attempts, optionally overriding retry count.

        Args:
            max_: Override retry_max for this session.
        """
        self._connection.retry(max_=max_)
