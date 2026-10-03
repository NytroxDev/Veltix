"""Threading-based socket implementation for Veltix."""

from __future__ import annotations

import contextlib
import socket
import threading
from typing import TYPE_CHECKING

from ..internal.events import ClientEvent, ErrorEvent, ServerEvent
from ..internal.network import (
    RecvResult,
    apply_tcp_tunings,
    connect_and_handshake,
    dispatch_messages,
    recv,
    reject_full_connection,
)
from ..network import _rust
from ..network.message_buffer import MessageBuffer
from ..server.client_info import ClientInfo
from .base_socket import ServerSocket
from .managers.clients_manager import ClientEntry, ClientsManager
from .thread_registry import ThreadRegistry

if TYPE_CHECKING:
    from ..handler.request_handler import RequestHandler
    from ..internal.bus import VeltixBus


class ThreadingSocket(ServerSocket):
    """Threading-based socket implementation for Veltix (one thread per client)."""

    def __init__(
        self,
        request_handler: RequestHandler,
        max_message_size: int,
        bus: VeltixBus,
        sock: socket.socket | None = None,
        handshake_timeout: float = 5.0,
        use_rust: bool | None = None,
    ) -> None:
        self.bus = bus
        self._use_rust: bool = _rust.rust_enabled() if use_rust is None else use_rust

        self.client_manager = ClientsManager(max_message_size, bus=bus, use_rust=self._use_rust)

        self._running_event = threading.Event()
        self._registry = ThreadRegistry()

        self.max_message_size = max_message_size
        self.request_handler = request_handler
        self.handshake_timeout = handshake_timeout

        self._sock: socket.socket = (
            sock if sock is not None else socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        )
        apply_tcp_tunings(self._sock)

    @property
    def threads(self) -> dict[int, threading.Thread]:
        """Return the live per-client receive threads, keyed by thread id."""
        return self._registry.threads

    # ── Server ────────────────────────────────────────────────────────────────

    def bind(self, host: str, port: int, max_client: int, buffer_size: int, timeout: float) -> bool:
        if self._running_event.is_set():
            return False
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        with contextlib.suppress(AttributeError, OSError):
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self._sock.bind((host, port))
        self._sock.listen()
        self._running_event.set()
        self._registry.start_th = threading.Thread(
            target=self._accept_loop,
            args=(host, port, max_client, buffer_size, timeout),
            daemon=True,
            name="veltix-accept",
        )
        self._registry.start_th.start()
        return True

    def _accept_loop(
        self, host: str, port: int, max_client: int, buffer_size: int, timeout: float
    ) -> None:
        self._sock.settimeout(timeout)
        self.bus.info(f"Server listening on {host}:{port}")

        while self._running_event.is_set():
            try:
                conn_, addr = self._sock.accept()

                if max_client >= 0 and self.client_manager.count() >= max_client:
                    reject_full_connection(
                        conn_,
                        addr,
                        self.bus,
                        self.request_handler.handshake_handler,
                        self.client_manager.count(),
                        max_client,
                    )
                    continue
                conn = ThreadingSocket(
                    self.request_handler,
                    self.max_message_size,
                    self.bus,
                    sock=conn_,
                    handshake_timeout=self.handshake_timeout,
                )

                thread_id = self._registry.next_id()

                client = ClientInfo(
                    conn=conn,
                    addr=addr,
                    thread_id=thread_id,
                    handshake_done=False,
                    bus=self.bus,
                )

                client_id = self.client_manager.add_client(client)

                self.bus.info(
                    f"New client connected: {addr} (total: {self.client_manager.count()}/{max_client})"
                )

                thread = threading.Thread(
                    target=self._handle_server_client,
                    args=(client_id, buffer_size, timeout),
                    daemon=True,
                    name=f"veltix-client-{thread_id}",
                )
                thread.start()

                self._registry.register(thread_id, thread)

            except TimeoutError:
                continue
            except OSError as e:
                # Transient errors (e.g. EMFILE) must not kill the accept
                # loop: log and keep accepting, like the selector backend.
                self.bus.emit(ErrorEvent.ACCEPT, {"error": str(e)})
                self.bus.error(f"Accept error: {type(e).__name__}: {e}")
                continue
            except Exception as e:
                if self._running_event.is_set():
                    self.bus.emit(ErrorEvent.ACCEPT, {"error": f"{type(e).__name__}: {e}"})
                    self.bus.error(f"Accept error: {type(e).__name__}: {e}")
                self._running_event.clear()
                return

    def _handle_server_client(self, client_id: int, buffer_size: int, timeout: float) -> None:
        entry = self.client_manager.get_client(client_id)
        if not entry:
            raise ValueError(f"Client {client_id} not found")

        entry.info.conn.settimeout(timeout)

        ok = self.request_handler.handshake_handler.do_server_handshake(
            entry.info.conn._sock,
            timeout=entry.info.conn.handshake_timeout,
        )
        if not ok:
            self.bus.warning(f"Handshake failed for {entry.info.addr}")
            self._close_server_client(entry)
            return
        entry.info.handshake_done = True
        self.bus.debug(f"Handshake complete for {entry.info.addr}")

        try:
            self.bus.emit(ServerEvent.ON_CONNECT, entry.info)
        except Exception as e:
            self.bus.error(f"ServerEvent.ON_CONNECT error: {type(e).__name__}: {e}")

        while self._running_event.is_set():
            result = recv(entry.info.conn, buffer_size)

            if result.timed_out:
                continue

            if not self._process_server_message(result, entry):
                break

    def _process_server_message(self, result: RecvResult, entry: ClientEntry) -> bool:
        if result.timed_out:
            return True

        if result.disconnected:
            self.bus.info(f"Client {entry.info.addr} disconnected")
            self._close_server_client(entry)
            return False

        entry.buffer.add_data(result.data or b"")
        dispatch_messages(
            entry.buffer,
            self.bus,
            lambda response: self.request_handler.handle(response, entry.info),
            client_addr=entry.info.addr,
        )
        return True

    def _close_server_client(self, entry: ClientEntry) -> None:
        entry.info.conn.close()

        self._registry.pop_and_join(entry.info.thread_id, 0.2)

        # Only the caller that actually removed the entry emits the event: a
        # concurrent close (close_all, close_client, the client's own recv
        # loop) must not fire ON_DISCONNECT twice.
        if not self.client_manager.remove_client(entry.id):
            return

        try:
            self.bus.emit(ServerEvent.ON_DISCONNECT, entry.info)
        except Exception as e:
            self.bus.error(f"ServerEvent.ON_DISCONNECT error: {type(e).__name__}: {e}")

    def close_client(self, client: ClientEntry | int) -> bool:
        if isinstance(client, ClientEntry):
            self._close_server_client(client)
            return True
        else:
            entry = self.client_manager.get_client(client)
            if not entry:
                return False
            self._close_server_client(entry)
            return True

    def close_all(self) -> bool:
        try:
            self._running_event.clear()
            self._shutdown_socket()
            with contextlib.suppress(OSError):
                self._sock.close()

            threads = self._registry.snapshot()

            # Close every client socket first so the receive threads exit in
            # parallel and clean up themselves.
            for entry in self.client_manager.get_all_clients():
                entry.info.conn.close()

            for thread in threads:
                self._registry.join_foreign(thread, 0.2)
            self._registry.join_foreign(self._registry.start_th, 0.2)
            self._registry.join_foreign(self._registry.thread_handler, 0.2)

            # Sweep the registry: receive threads that exited via the
            # running-event check (rather than a socket error) never clean
            # themselves up. The remove_client gate in _close_server_client
            # guarantees each client fires ON_DISCONNECT exactly once, even
            # against a concurrent close from a receive thread.
            self.client_manager.iter_on_clients(self._close_server_client)

            self._registry.clear()
            return True
        except Exception:
            return False

    def close(self) -> bool:
        return self.close_all()

    # ── Client ────────────────────────────────────────────────────────────────

    def connect(self, host: str, port: int, buffer_size: int, timeout: float) -> bool:
        self.bus.info(f"Connecting to {host}:{port}")
        if not connect_and_handshake(
            self._sock,
            self.bus,
            self.request_handler.handshake_handler,
            host,
            port,
            timeout,
        ):
            return False

        self._running_event.set()

        if hasattr(self, "client") and self.client:
            with self.client._state_lock:
                self.client.is_connected = True
                self.client._connecting = False

        self._registry.thread_handler = threading.Thread(
            target=self._handle_client,
            args=(buffer_size, timeout),
            daemon=True,
            name="veltix-client-handler",
        )
        self._registry.thread_handler.start()
        return True

    def _handle_client(self, buffer_size: int, timeout: float) -> None:
        message_buffer = MessageBuffer(
            max_message_size=self.max_message_size, use_rust=self._use_rust
        )

        while self._running_event.is_set():
            result = recv(self, buffer_size)

            if result.timed_out:
                continue

            if result.disconnected:
                self.bus.info("Disconnected from server")
                self.bus.emit(ClientEvent.SOCKET_DISCONNECTED)
                break

            message_buffer.add_data(result.data or b"")
            dispatch_messages(
                message_buffer,
                self.bus,
                lambda response: self.request_handler.handle(response),
            )

    def disconnect(self, timeout: float = 5.0) -> bool:
        try:
            self._running_event.clear()
            self._shutdown_socket()
            self._sock.close()

            self._registry.join_foreign(self._registry.thread_handler, timeout + 0.1)

            self.bus.info("Disconnected from server")
            return True

        except Exception as e:
            self.bus.error(f"Disconnect error: {type(e).__name__}: {e}")
            return False
