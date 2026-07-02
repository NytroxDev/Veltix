"""Selector-based socket implementation for Veltix."""

from __future__ import annotations

import contextlib
import selectors
import socket
import threading
import time
from typing import TYPE_CHECKING, Optional, Union

from ..internal.network import recv as _network_recv
from ..logger import Logger
from ..network.message_buffer import MessageBuffer
from ..server.client_info import ClientInfo
from .base_socket import BaseSocket, SocketEvents
from .managers.clients_manager import ClientEntry, ClientsManager

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..handler.request_handler import RequestHandler


class AsyncSocket(BaseSocket):
    """Selector-based socket implementation for Veltix."""

    def __init__(self, request_handler: RequestHandler, max_message_size: int) -> None:
        self.client_manager = ClientsManager(max_message_size)

        self.id_count = 0

        self.running = False

        self._selector_thread: Optional[threading.Thread] = None

        self.on_connect: Optional[Callable] = None
        self.on_disconnect: Optional[Callable] = None
        self.on_recv: Optional[Callable] = None

        self.max_message_size = max_message_size
        self.request_handler = request_handler
        self.handshake_timeout: float = 5.0
        self._logger = Logger.get_instance()

        self._sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        with contextlib.suppress(AttributeError, OSError):
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        self._selector = selectors.DefaultSelector()

        self._handshake_requests: dict[int, bytes] = {}

        self._handshake_pending: list[int] = []

        self._client_connect_time: dict[int, float] = {}

        self._client_buffer = MessageBuffer(max_message_size)

        self._logger.debug("AsyncSocket initialized")

    @classmethod
    def _create_client_instance(
        cls,
        sock: socket.socket,
        logger: Logger,
        request_handler: RequestHandler,
        max_message_size: int,
    ) -> AsyncSocket:
        """Create a properly initialized client socket instance."""
        conn = cls.__new__(cls)
        conn.client_manager = ClientsManager(max_message_size)

        conn.id_count = 0

        conn.running = False

        conn._selector_thread = None

        conn.on_connect = None
        conn.on_disconnect = None
        conn.on_recv = None

        conn.max_message_size = max_message_size
        conn.request_handler = request_handler
        conn.handshake_timeout = 5.0
        conn._logger = logger

        conn._sock = sock
        conn._sock.setblocking(False)
        conn._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        with contextlib.suppress(AttributeError, OSError):
            conn._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        conn._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        conn._selector = selectors.DefaultSelector()

        conn._handshake_requests = {}

        conn._handshake_pending = []

        conn._client_connect_time = {}

        conn._client_buffer = MessageBuffer(max_message_size)
        conn._logger.debug(f"created client socket instance (fd={conn._sock.fileno()})")
        return conn

    # ── Shared helpers ────────────────────────────────────────────────────────

    def recv(self, buf_size: int) -> bytes:
        return self._sock.recv(buf_size)

    def send(self, data: bytes) -> bool:
        try:
            self._sock.sendall(data)
            self._logger.debug(f"send {len(data)} bytes")
            return True
        except BlockingIOError:
            try:
                self._sock.setblocking(True)
                self._sock.sendall(data)
                self._sock.setblocking(False)
                return True
            except Exception as e:
                self._logger.debug(f"send BlockingIOError fallback failed: {e}")
                return False
        except Exception as e:
            self._logger.debug(f"send failed: {e}")
            return False

    def settimeout(self, timeout: float) -> bool:
        try:
            self._sock.settimeout(timeout)
            self._logger.debug(f"settimeout {timeout}s")
            return True
        except Exception as e:
            self._logger.debug(f"settimeout {timeout}s failed: {e}")
            return False

    def set_callback(self, event: SocketEvents, callback: Callable) -> bool:
        if event == SocketEvents.RECV:
            self.on_recv = callback
        elif event == SocketEvents.CONNECT:
            self.on_connect = callback
        elif event == SocketEvents.DISCONNECT:
            self.on_disconnect = callback
        else:
            self._logger.debug(f"set_callback: unknown event {event}")
            return False
        self._logger.debug(f"set_callback: {event.name}")
        return True

    # ── Server ────────────────────────────────────────────────────────────────

    def bind(self, host: str, port: int, max_client: int, buffer_size: int, timeout: float) -> bool:
        self._sock.setblocking(False)
        self._sock.bind((host, port))
        self._sock.listen()
        self._selector.register(self._sock, selectors.EVENT_READ, data="listen")
        self.running = True
        self._selector_thread = threading.Thread(
            target=self._selector_loop, args=(max_client, buffer_size), daemon=True
        )
        self._selector_thread.start()
        self._logger.debug(
            f"bound to {host}:{port}, max_client={max_client}, running={self.running}"
        )
        return self.running

    def _selector_loop(self, max_client, buffer_size):
        while self.running:
            events = self._selector.select(0.5)

            for key, _ in events:
                if key.data == "listen":
                    self._accept_client(max_client)
                elif key.data == "client":
                    self._handle_self_read(buffer_size)
                else:
                    self._handle_server_client(key.data, buffer_size)

            self._process_pending_handshakes()
            self._check_handshake_timeouts()

    def _check_handshake_timeouts(self) -> None:
        now = time.monotonic()
        for client_id in list(self._client_connect_time.keys()):
            connect_time = self._client_connect_time.get(client_id)
            if connect_time is None:
                continue
            if now - connect_time <= self.handshake_timeout:
                continue
            entry = self.client_manager.get_client(client_id)
            if entry and not entry.info.handshake_done:
                self._logger.warning(f"handshake timeout for client {entry.id} ({entry.info.addr})")
                self._close_server_client(entry)

    def _process_pending_handshakes(self) -> None:
        if not self._handshake_pending:
            return
        pending = self._handshake_pending[:]
        self._handshake_pending.clear()
        for client_id in pending:
            entry = self.client_manager.get_client(client_id)
            if not entry or entry.info.handshake_done:
                continue
            try:
                handshake_request_id, hello = self.request_handler.handshake_handler.prepare_hello()
                self.request_handler.register(handshake_request_id)
                self._logger.debug(f"sending hello to client {client_id} at {entry.info.addr}")
                self.request_handler.handshake_handler.send_hello(hello, entry.info.conn)
                self._handshake_requests[client_id] = handshake_request_id
            except Exception as e:
                self._logger.error(f"handshake failed for client {client_id}: {e}")
                self._close_server_client(entry)

    def fileno(self) -> int:
        return self._sock.fileno()

    def _accept_client(self, max_client: int):
        if (max_client != -1 and self.client_manager.count() >= max_client) or not self.running:
            self._logger.debug("_accept_client: max clients reached or server not running")
            return
        try:
            conn, addr = self._sock.accept()
        except BlockingIOError:
            return
        except OSError as e:
            self._logger.error(f"accept failed: {e}")
            return
        self._logger.debug(f"accepted client from {addr}")

        self._send_hello(conn, addr)
        return

    def _send_hello(self, conn: socket.socket, addr: tuple) -> None:
        client_sock = AsyncSocket._create_client_instance(
            conn, self._logger, self.request_handler, self.max_message_size
        )
        client = ClientInfo(client_sock, addr, self.id_count)
        client_id = self.client_manager.add_client(client)
        self._selector.register(client_sock, selectors.EVENT_READ, data=client_id)
        self.id_count += 1
        self._handshake_requests[client_id] = b""
        self._client_connect_time[client_id] = time.monotonic()

        try:
            handshake_request_id, hello = self.request_handler.handshake_handler.prepare_hello()
            self.request_handler.register(handshake_request_id)
            self._logger.debug(f"sending hello to client {client_id} at {addr}")
            self.request_handler.handshake_handler.send_hello(hello, client_sock)
            self._handshake_requests[client_id] = handshake_request_id
        except Exception as e:
            self._logger.error(f"handshake failed for client {client_id}: {e}")
            self.close_client(client_id)

    def _handle_server_client(self, client_id: int, buffer_size: int) -> None:
        entry = self.client_manager.get_client(client_id)
        if not entry:
            return

        sock = entry.info.conn

        result = _network_recv(sock, buffer_size)

        if result.timed_out:
            return

        if result.disconnected:
            self._logger.debug(f"client {client_id} disconnected")
            self.close_client(client_id)
            return

        data = result.data
        self._logger.debug(f"client {client_id} recv {len(data)} bytes")
        entry.buffer.add_data(data)
        messages = entry.buffer.extract_messages()
        if messages:
            self._logger.debug(f"client {client_id} extracted {len(messages)} messages")
            for message in messages:
                self.request_handler.handle(message, entry.info)
                handshake_request_id = self._handshake_requests.get(client_id)
                handshake_done = entry.info.handshake_done
                if handshake_request_id and not handshake_done:
                    self._check_server_handshake(entry, handshake_request_id)

    def _check_server_handshake(self, entry: ClientEntry, handshake_request_id: bytes) -> None:
        with self.request_handler.pending_requests_lock:
            queue = self.request_handler.pending_requests.pop(handshake_request_id, None)
            response = queue.get_nowait() if queue is not None and not queue.empty() else None
            self._logger.debug(
                f"handshake check for {entry.info.addr}: request_id={handshake_request_id!r}, "
                f"resolved={response is not None}, handshake_done={entry.info.handshake_done}"
            )
            if response is not None:
                self._client_connect_time.pop(entry.id, None)

        if response is None:
            return

        if not self.request_handler.handshake_handler.handle_hello_ack(response):
            self._logger.warning(
                f"Handshake failed for {entry.info.addr} — version mismatch, closing"
            )
            entry.info.conn.close()
            return

        entry.info.handshake_done = True
        self._logger.debug(f"Handshake complete for {entry.info.addr}")

        if self.on_connect:
            try:
                self.on_connect(entry.info)
            except Exception as e:
                self._logger.error(
                    f"on_connect error for {entry.info.addr}: {type(e).__name__}: {e}"
                )

    def _handle_self_read(self, buffer_size: int):
        result = _network_recv(self, buffer_size)

        if result.timed_out:
            return

        if result.disconnected:
            self._logger.debug("self_read: disconnected from server")
            if self.on_disconnect:
                self.on_disconnect()
            self.disconnect(0.5)
            return

        data = result.data
        self._logger.debug(f"self_read: recv {len(data)} bytes")
        self._client_buffer.add_data(data)
        messages = self._client_buffer.extract_messages()
        if messages:
            self._logger.debug(f"self_read: extracted {len(messages)} messages")
            for message in messages:
                self.request_handler.handle(message)

    def close_client(self, client: Union[ClientEntry, int]) -> bool:
        if isinstance(client, ClientEntry):
            self._close_server_client(client)
            return True
        entry = self.client_manager.get_client(client)
        if not entry:
            self._logger.debug(f"close_client: client {client} not found")
            return False
        self._close_server_client(entry)
        return True

    def _close_server_client(self, entry: ClientEntry) -> None:
        self._logger.debug(f"closing server client {entry.id} ({entry.info.addr})")
        entry.info.conn.close()

        try:
            self._selector.unregister(entry.info.conn)
        except KeyError:
            pass

        self.client_manager.remove_client(entry.id)

        self._handshake_requests.pop(entry.id, None)
        self._client_connect_time.pop(entry.id, None)

        if self.on_disconnect:
            self.on_disconnect(entry.info)

    def close(self) -> bool:
        try:
            self._logger.debug("closing server socket")
            self.running = False
            self._selector.unregister(self._sock)
            try:
                self._sock.close()
            except OSError:
                pass
            self.client_manager.iter_on_clients(self._close_server_client)
            self._selector.close()
            if self._selector_thread and self._selector_thread != threading.current_thread():
                self._selector_thread.join(timeout=0.2)
            self._logger.debug("server socket closed")
            return True
        except Exception as e:
            self._logger.debug(f"close failed: {e}")
            return False

    def connect(self, host: str, port: int, buffer_size: int, timeout: float) -> bool:
        try:
            self._sock.connect((host, port))
            self._sock.setblocking(False)
            self.running = True
            self._selector.register(self._sock, selectors.EVENT_READ, data="client")
            self._selector_thread = threading.Thread(
                target=self._selector_loop, args=(0, buffer_size), daemon=True
            )
            self._selector_thread.start()
            self._logger.debug(f"connected to {host}:{port}")
            return True
        except (socket.timeout, ConnectionRefusedError) as e:
            self._logger.debug(f"connect to {host}:{port} failed: {e}")
            return False
        except Exception as e:
            self._logger.debug(f"connect to {host}:{port} failed: {e}")
            return False

    def disconnect(self, timeout: float = 5.0) -> bool:
        try:
            self._logger.debug("disconnecting client socket")
            self.running = False
            self._selector.unregister(self._sock)
            self._sock.close()
            if self._selector_thread and threading.current_thread() != self._selector_thread:
                self._selector_thread.join(timeout=timeout + 0.1)
            self._logger.debug("client socket disconnected")
            return True

        except Exception as e:
            self._logger.debug(f"disconnect failed: {e}")
            return False
