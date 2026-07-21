"""Threading-based socket implementation for Veltix."""

from __future__ import annotations

import contextlib
import socket
import threading
import time
from typing import TYPE_CHECKING, Optional, Union, cast

from ..internal.events import ClientEvent, ErrorEvent, MessageEvent, ServerEvent
from ..internal.network import RecvResult, recv
from ..network.message_buffer import MessageBuffer
from ..server.client_info import ClientInfo
from .base_socket import BaseSocket
from .managers.clients_manager import ClientEntry, ClientsManager

if TYPE_CHECKING:
    from ..handler.request_handler import RequestHandler
    from ..internal.bus import VeltixBus
    from ..network.id_allocator import ClientAllocator


class ThreadingSocket(BaseSocket):
    """Threading-based socket implementation for Veltix (one thread per client)."""

    def __init__(
        self, request_handler: RequestHandler, max_message_size: int, bus: VeltixBus
    ) -> None:
        self.bus = bus
        self.n_th = 0
        self._n_th_lock = threading.Lock()

        self.client_manager = ClientsManager(max_message_size, bus=bus)

        self.threads: dict[int, threading.Thread] = {}
        self._threads_lock = threading.Lock()

        self._running_event = threading.Event()
        self.start_th: Optional[threading.Thread] = None
        self.thread_handler: Optional[threading.Thread] = None

        self.max_message_size = max_message_size
        self.request_handler = request_handler
        self.handshake_timeout: float = 5.0
        self.client_allocator: Optional[ClientAllocator] = None

        self._sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    @classmethod
    def _create_client_instance(
        cls,
        sock: socket.socket,
        bus: VeltixBus,
        request_handler: RequestHandler,
        max_message_size: int,
        handshake_timeout: float = 5.0,
    ) -> ThreadingSocket:
        """Create a properly initialized client socket instance."""
        conn = cls.__new__(cls)
        conn.bus = bus
        conn._sock = sock
        conn._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        conn.request_handler = request_handler
        conn.max_message_size = max_message_size
        conn.handshake_timeout = handshake_timeout
        conn._running_event = threading.Event()
        conn.client_manager = ClientsManager(max_message_size, bus=bus)
        conn.start_th = None
        conn.thread_handler = None
        conn.threads = {}
        conn._threads_lock = threading.Lock()
        conn.n_th = 0
        conn._n_th_lock = threading.Lock()
        return conn

    # ── Shared helpers ────────────────────────────────────────────────────────

    def recv(self, buf_size: int) -> bytes:
        return self._sock.recv(buf_size)

    def send(self, data: bytes) -> bool:
        try:
            self._sock.sendall(data)
            return True
        except Exception as e:
            self.bus.emit(ErrorEvent.SEND, {"error": str(e)})
            self.bus.error(f"send failed: {e}")
            return False

    def _shutdown_socket(self) -> None:
        with contextlib.suppress(OSError):
            self._sock.shutdown(socket.SHUT_RDWR)

    def settimeout(self, timeout: float) -> bool:
        try:
            self._sock.settimeout(timeout)
            return True
        except Exception:
            return False

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
        self.start_th = threading.Thread(
            target=self._accept_loop,
            args=(host, port, max_client, buffer_size, timeout),
            daemon=True,
        )
        self.start_th.start()
        return True

    def _accept_loop(
        self, host: str, port: int, max_client: int, buffer_size: int, timeout: float
    ) -> None:
        self._sock.settimeout(timeout)
        self.bus.info(f"Server listening on {host}:{port}")

        while self._running_event.is_set():
            try:
                if 0 < max_client <= self.client_manager.count():
                    self.bus.emit(
                        ErrorEvent.CONNECTION_REFUSED,
                        {
                            "max_client": max_client,
                            "current": self.client_manager.count(),
                        },
                    )
                    self.bus.emit(
                        ServerEvent.CLIENT_REJECTED,
                        {
                            "max_client": max_client,
                            "current": self.client_manager.count(),
                            "reason": "max_connections",
                        },
                    )
                    time.sleep(0.1)
                    continue

                conn_, addr = self._sock.accept()
                conn = ThreadingSocket._create_client_instance(
                    conn_,
                    self.bus,
                    self.request_handler,
                    self.max_message_size,
                    handshake_timeout=self.handshake_timeout,
                )

                with self._n_th_lock:
                    self.n_th += 1
                    thread_id = self.n_th

                client = ClientInfo(
                    conn=conn,
                    addr=addr,
                    thread_id=thread_id,
                    handshake_done=False,
                    bus=self.bus,
                    id_offset=self.client_allocator.register() if self.client_allocator else 0,
                )

                client_id = self.client_manager.add_client(client)

                self.bus.info(
                    f"New client connected: {addr} (total: {self.client_manager.count()}/{max_client})"
                )

                thread = threading.Thread(
                    target=self._handle_server_client,
                    args=(client_id, buffer_size, timeout),
                    daemon=True,
                )
                thread.start()

                with self._threads_lock:
                    self.threads[thread_id] = thread

            except socket.timeout:
                continue
            except OSError:
                self.bus.emit(ErrorEvent.ACCEPT, {"error": "OSError"})
                self._running_event.clear()
                return
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
            cast("ThreadingSocket", entry.info.conn)._sock,
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

        try:
            entry.buffer.add_data(result.data or b"")
            messages = entry.buffer.extract_messages()

            for response in messages:
                self.bus.debug(
                    f"Message from {entry.info.addr}: {response.type.name} (code={response.type.code})"
                )
                self.bus.emit(
                    MessageEvent.RECEIVED,
                    {
                        "type": response.type,
                        "length": len(response.content),
                        "client": entry.info.addr,
                    },
                )

                handler_result = self.request_handler.handle(response, entry.info)
                if not handler_result:
                    self.bus.error(f"Handler error for {entry.info.addr}")

        except Exception as e:
            self.bus.emit(ErrorEvent.HANDLER, {"error": str(e), "client": entry.info.addr})
            self.bus.error(
                f"Error processing message from {entry.info.addr}: {type(e).__name__}: {e}"
            )

        return True

    def _close_server_client(self, entry: ClientEntry) -> None:
        entry.info.conn.close()

        with self._threads_lock:
            thread = self.threads.pop(entry.info.thread_id, None)
            if thread and thread != threading.current_thread():
                thread.join(timeout=0.2)

        self.client_manager.remove_client(entry.id)

        try:
            self.bus.emit(ServerEvent.ON_DISCONNECT, entry.info)
        except Exception as e:
            self.bus.error(f"ServerEvent.ON_DISCONNECT error: {type(e).__name__}: {e}")

    def close_client(self, client: Union[ClientEntry, int]) -> bool:
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
            self.client_manager.iter_on_clients(self._close_server_client)
            if self.start_th and self.start_th != threading.current_thread():
                self.start_th.join(timeout=0.2)
            if self.thread_handler and self.thread_handler != threading.current_thread():
                self.thread_handler.join(timeout=0.2)
            return True
        except Exception:
            return False

    def close(self) -> bool:
        return self.close_all()

    # ── Client ────────────────────────────────────────────────────────────────

    def connect(self, host: str, port: int, buffer_size: int, timeout: float) -> bool:
        try:
            self.bus.info(f"Connecting to {host}:{port}")
            self._sock.connect((host, port))

            success, meta = self.request_handler.handshake_handler.do_client_handshake(self._sock)
            if not success:
                self.bus.error("Client handshake failed")
                self._sock.close()
                return False

            self._handshake_meta = meta

            self._running_event.set()

            self.thread_handler = threading.Thread(
                target=self._handle_client,
                args=(buffer_size, timeout),
                daemon=True,
            )
            self.thread_handler.start()
            return True

        except (socket.timeout, ConnectionRefusedError) as e:
            self.bus.emit(ErrorEvent.NETWORK, {"error": str(e), "host": host, "port": port})
            self.bus.error(f"Connection failed to {host}:{port}: {type(e).__name__}")
            return False

        except Exception as e:
            self.bus.emit(ErrorEvent.NETWORK, {"error": str(e), "host": host, "port": port})
            self.bus.error(f"Unexpected connection error: {type(e).__name__}: {e}")
            return False

    def _handle_client(self, buffer_size: int, timeout: float) -> None:
        message_buffer = MessageBuffer(max_message_size=self.max_message_size)

        while self._running_event.is_set():
            result = recv(self, buffer_size)

            if result.timed_out:
                continue

            if result.disconnected:
                self.bus.info("Disconnected from server")
                self.bus.emit(ClientEvent.SOCKET_DISCONNECTED)
                break

            try:
                message_buffer.add_data(result.data or b"")

                for response in message_buffer.extract_messages():
                    self.bus.debug(
                        f"Message from server: {response.type.name} (code={response.type.code})"
                    )
                    self.bus.emit(
                        MessageEvent.RECEIVED,
                        {
                            "type": response.type,
                            "length": len(response.content),
                            "from": "server",
                        },
                    )

                    handler_result = self.request_handler.handle(response)
                    if not handler_result:
                        self.bus.error("Handler error")

            except Exception as e:
                self.bus.emit(ErrorEvent.HANDLER, {"error": str(e)})
                self.bus.error(f"Error processing server message: {type(e).__name__}: {e}")

    def disconnect(self, timeout: float = 5.0) -> bool:
        try:
            self._running_event.clear()
            self._shutdown_socket()
            self._sock.close()

            if self.thread_handler and threading.current_thread() != self.thread_handler:
                self.thread_handler.join(timeout=timeout + 0.1)

            self.bus.info("Disconnected from server")
            return True

        except Exception as e:
            self.bus.error(f"Disconnect error: {type(e).__name__}: {e}")
            return False
