"""Server lifecycle management (start, stop, restart) for Veltix."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from ..internal.events import ServerEvent

if TYPE_CHECKING:
    from .core import ServerCore


class ServerLifecycle:
    """Drives a server's start/stop state machine.

    Owns the started/closed flags and the shutdown signal, and asks the
    shared :class:`~veltix.server.core.ServerCore` to (re)build its
    components when the server is restarted after a close.
    """

    __slots__ = ("_core", "_shutdown_event", "_state_lock", "_started", "_closed")

    def __init__(self, core: ServerCore) -> None:
        self._core = core
        self._shutdown_event = threading.Event()
        self._state_lock = threading.Lock()
        self._started = False
        self._closed = False

    def start(self) -> None:
        """Start the server and begin accepting connections.

        Non-blocking - starts a background thread and returns immediately.
        """
        with self._state_lock:
            if self._started:
                self._core.bus.warning("Server is already started")
                return

            self._started = True
            should_reinit = self._closed
            self._closed = False

        self._shutdown_event.clear()
        if should_reinit:
            old_routes = self._core.request_handler.copy_routes()
            old_on_recv = self._core.request_handler.on_recv
            self._core.init_components()
            for type_, func in old_routes.items():
                self._core.request_handler.register_route(type_, func)
            if old_on_recv:
                self._core.request_handler.set_on_recv(old_on_recv)
        try:
            self._core.socket.bind(
                host=self._core.config.host,
                port=self._core.config.port,
                max_client=self._core.config.max_connection,
                buffer_size=self._core.config.buffer_size,
                timeout=0.5,
            )
        except OSError as e:
            with self._state_lock:
                self._started = False
            self._core.bus.error(
                f"Failed to bind on {self._core.config.host}:{self._core.config.port}: {e}"
            )
            raise
        self._core.bus.emit(
            ServerEvent.STARTED,
            {
                "host": self._core.config.host,
                "port": self._core.config.port,
            },
        )
        self._core.bus.info(f"Server started on {self._core.config.host}:{self._core.config.port}")

    def close_all(self) -> None:
        """Stop the server and close all client connections."""
        with self._state_lock:
            if self._closed:
                self._core.bus.warning("Server is already closed")
                return
            self._closed = True
            self._started = False

        self._core.bus.info("Shutting down server")

        try:
            self._core.request_handler.shutdown(wait=False)
            self._core.socket.close()
            self._core.bus.info("Server socket closed")
        except Exception as e:
            self._core.bus.error(f"Error closing server socket: {e}")

        self._shutdown_event.set()

        self._core.bus.emit(
            ServerEvent.STOPPED,
            {
                "host": self._core.config.host,
                "port": self._core.config.port,
            },
        )

    def wait_until_closed(self) -> None:
        """Block until the server is shut down via close_all() or Ctrl+C."""
        try:
            self._shutdown_event.wait()
        except KeyboardInterrupt:
            self.close_all()

    def restart(self) -> None:
        """Stop the server and start it again, preserving routes and callbacks."""
        self.close_all()
        self.start()
