"""Connection lifecycle (connect, disconnect, reconnect) for the Veltix client."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from ..exceptions import ServerFullError
from ..internal.events import ClientEvent, ErrorEvent
from .disconnect import DisconnectReason, DisconnectState
from .reconnect_handler import ReconnectHandler

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..handler.request_handler import RequestHandler
    from ..socket_core.base_socket import BaseSocket
    from .config import ClientConfig
    from .core import ClientCore


class ClientLifecycle:
    """Drives a client's connection state machine.

    Owns the connection flags (``is_connected``, ``running``), the shutdown
    signal and the :class:`~veltix.client.reconnect_handler.ReconnectHandler`.
    It is also the socket backend's ``socket.client`` owner, so the backend can
    flag connect/disconnect state, and it implements the ``ClientContext``
    protocol consumed by the reconnect handler.
    """

    __slots__ = (
        "_core",
        "_state_lock",
        "is_connected",
        "_connecting",
        "running",
        "_shutdown_event",
        "_socket_used",
        "_reconnect_handler",
    )

    def __init__(self, core: ClientCore) -> None:
        self._core = core
        self._state_lock = threading.Lock()
        self.is_connected = False
        self._connecting = False
        self.running = True
        self._shutdown_event = threading.Event()
        self._socket_used = False
        self._reconnect_handler = ReconnectHandler(context=self, bus=core.bus)
        core.bus.subscribe(ClientEvent.SOCKET_DISCONNECTED, self._on_socket_disconnect)

    @property
    def config(self) -> ClientConfig:
        """Return the client configuration."""
        return self._core.config

    def init_components(self) -> None:
        """(Re)initialise all internal components (socket, sender, handler)."""
        self._core.init_components(self)

    def _rebuild_components(self) -> None:
        """Rebuild the socket stack for a fresh connection cycle.

        A failed, dropped, or manually closed connection leaves the client
        socket unusable for a new ``connect()``: AsyncSocket releases the fd,
        ThreadingSocket leaves it in a stale state. Recreating the components
        restores a connectable socket while preserving the registered routes
        and the ``on_recv`` callback, mirroring ``ReconnectHandler.reset``.
        """
        old_routes = self._core.request_handler.copy_routes()
        old_on_recv = self._core.request_handler.on_recv
        self.init_components()
        for type_, func in old_routes.items():
            self._core.request_handler.register_route(type_, func)
        if old_on_recv:
            self._core.request_handler.set_on_recv(old_on_recv)

    # -------------------------------------------------------------------------
    # Internal context (used by ReconnectHandler)
    # -------------------------------------------------------------------------

    def _context_connect(self) -> bool:
        """Connect from within a retry context (suppresses own reconnect)."""
        return self.connect(_from_retry=True)

    def _context_on_disconnect(self, state: DisconnectState) -> None:
        """Forward disconnect state to subscribers."""
        self._core.bus.emit(ClientEvent.ON_DISCONNECT, state)

    def _context_init(self) -> None:
        """Reinitialise components before a reconnection attempt."""
        self.init_components()

    def _context_set_running(self, value: bool) -> None:
        """Set whether the client is considered running."""
        with self._state_lock:
            old = self.running
            self.running = value
        if old != value:
            self._core.bus.info(f"Client running state: {value}")
            if not value:
                self._shutdown_event.set()

    def _context_set_connected(self, value: bool) -> None:
        """Set the connection flag without triggering side effects."""
        with self._state_lock:
            old = self.is_connected
            self.is_connected = value
        if old != value:
            self._core.bus.debug(f"Client connected state: {value}")

    def _context_get_request_handler(self) -> RequestHandler | None:
        """Return the current request handler instance."""
        return self._core.request_handler

    def _context_get_on_recv(self) -> Callable | None:
        """Return the current on_recv callback."""
        return self._core.request_handler.on_recv

    def _context_get_socket(self) -> BaseSocket | None:
        """Return the current socket instance."""
        return self._core.socket

    def _on_socket_disconnect(self, event: object = None, payload: object = None) -> None:
        """Handle socket-level disconnect from the server (triggers reconnect)."""
        with self._state_lock:
            if not self.running or self._connecting:
                return
            self.is_connected = False
        self._try_reconnect(DisconnectReason.SERVER_CLOSED)

    def _try_reconnect(self, reason: DisconnectReason) -> bool:
        """Internal reconnect entrypoint used by connect() and tests."""
        return self._reconnect_handler.try_reconnect(reason)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

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
        config = self._core.config
        with self._state_lock:
            self.running = True
            self._connecting = True
        self._shutdown_event.clear()

        if not _from_retry and self._socket_used and not self.is_connected:
            # A previous failure, drop, or disconnect left the old socket
            # unusable (AsyncSocket releases the fd, ThreadingSocket leaves it
            # stale). Rebuild the stack so connect() can be called again.
            self._rebuild_components()
        self._socket_used = True

        try:
            self._core.bus.emit(
                ClientEvent.CONNECTING,
                {
                    "host": config.server_addr,
                    "port": config.port,
                },
            )
            self._core.bus.info(f"Connecting to server {config.server_addr}:{config.port}")
            connected = self._core.socket.connect(
                config.server_addr,
                config.port,
                config.buffer_size,
                config.handshake_timeout,
            )
            if not connected:
                self._core.bus.error(
                    f"Connection failed to {config.server_addr}:{config.port}. "
                    "Fix: check that the server is running on that address and port, "
                    "then call connect() again."
                )
                return False if _from_retry else self._try_reconnect(DisconnectReason.ERROR)

            with self._state_lock:
                self.is_connected = True

            self._reconnect_handler.init_connect()
            self._core.bus.info(
                f"Successfully connected to server {config.server_addr}:{config.port}"
            )

            self._core.bus.emit(ClientEvent.ON_CONNECT, None)

            return True

        except (TimeoutError, ConnectionRefusedError) as e:
            self._core.bus.emit(
                ErrorEvent.NETWORK,
                {
                    "error": str(e),
                    "host": config.server_addr,
                    "port": config.port,
                },
            )
            self._core.bus.error(
                f"Connection failed to {config.server_addr}:{config.port}: "
                f"{type(e).__name__}. Fix: check that the server is running on that "
                "address and port, then call connect() or retry() again."
            )
            return False if _from_retry else self._try_reconnect(DisconnectReason.ERROR)

        except ServerFullError:
            self._core.bus.error(
                f"Server rejected connection: server full "
                f"({config.server_addr}:{config.port}). "
                "Fix: raise ServerConfig(max_connection=...) on the server side, "
                "or connect again when the server has free slots."
            )
            if _from_retry:
                # The reconnect loop reports the failed attempt and fires its
                # own on_disconnect. Raising would escape and kill the loop.
                return False
            self._core.bus.emit(
                ClientEvent.ON_DISCONNECT,
                DisconnectState(
                    permanent=False,
                    attempt=0,
                    retry_max=0,
                    reason=DisconnectReason.SERVER_CLOSED,
                ),
            )
            raise

        except Exception as e:
            self._core.bus.emit(
                ErrorEvent.NETWORK,
                {
                    "error": str(e),
                    "host": config.server_addr,
                    "port": config.port,
                },
            )
            self._core.bus.error(f"Unexpected error during connection: {type(e).__name__}: {e}")
            return False
        finally:
            with self._state_lock:
                self._connecting = False

    def disconnect(self) -> bool:
        """
        Disconnect from the server and clean up resources.

        Fires on_disconnect with reason=MANUAL and permanent=True.

        Returns:
            True if disconnection succeeded, False on unexpected error.
        """
        try:
            self._core.bus.emit(ClientEvent.DISCONNECTING)
            self._core.bus.info("Disconnecting from server")
            with self._state_lock:
                self.running = False
                self.is_connected = False
            self._reconnect_handler.mark_manual_disconnect()
            self._reconnect_handler.stop_retry()
            self._core.request_handler.shutdown(wait=False)
            self._core.socket.close()
            self._core.bus.debug("Socket closed")

            self._reconnect_handler.fire_on_disconnect(
                permanent=True, reason=DisconnectReason.MANUAL
            )

            self._core.bus.info("Successfully disconnected from server")
            self._shutdown_event.set()
            return True

        except Exception as e:
            self._core.bus.error(f"Error during disconnection: {type(e).__name__}: {e}")
            return False

    def stop_retry(self) -> None:
        """Cancel all pending reconnection attempts."""
        self._reconnect_handler.stop_retry()

    def wait_until_closed(self) -> None:
        """Block until the client is disconnected (via disconnect() or server close)."""
        try:
            self._shutdown_event.wait()
        except KeyboardInterrupt:
            self.disconnect()

    def retry(self, max_: int | None = None) -> None:
        """
        Force reconnection attempts, optionally overriding retry count.

        Args:
            max_: Override retry_max for this session.
        """
        self._reconnect_handler.retry(max_=max_)

    @property
    def _fail_count(self) -> int:
        """Expose reconnect fail count for backward compatibility and tests."""
        return self._reconnect_handler._fail_count
