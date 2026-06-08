"""Selector-based socket implementation for Veltix."""

from __future__ import annotations

import selectors
import socket
import threading
import time
from typing import TYPE_CHECKING, Optional, Union

from ..internal.network import RecvResult, recv
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
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        self._selector = selectors.DefaultSelector()

        self._client_buffer = MessageBuffer(max_message_size)

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
        conn._logger = Logger.get_instance()

        conn._sock = sock
        conn._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        conn._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        conn._selector = selectors.DefaultSelector()

        conn._client_buffer = MessageBuffer(max_message_size)
        return conn

    # ── Shared helpers ────────────────────────────────────────────────────────

    def recv(self, buf_size: int) -> bytes:
        return self._sock.recv(buf_size)

    def send(self, data: bytes) -> bool:
        try:
            self._sock.sendall(data)
            return True
        except Exception:
            return False

    def settimeout(self, timeout: float) -> bool:
        try:
            self._sock.settimeout(timeout)
            return True
        except Exception:
            return False

    def set_callback(self, event: SocketEvents, callback: Callable) -> bool:
        if event == SocketEvents.RECV:
            self.on_recv = callback
        elif event == SocketEvents.CONNECT:
            self.on_connect = callback
        elif event == SocketEvents.DISCONNECT:
            self.on_disconnect = callback
        else:
            return False
        return True

    # ── Server ────────────────────────────────────────────────────────────────

    def bind(self, host: str, port: int, max_client: int, buffer_size: int, timeout: float) -> bool:
        self._sock.setblocking(False)
        self._sock.bind((host, port))
        self._sock.listen()
        self._selector.register(self._sock, selectors.EVENT_READ, data="listen")
        self.running = True
        self._selector_thread = threading.Thread(
            target=self._selector_loop, args=(max_client, buffer_size, timeout)
        )
        self._selector_thread.start()
        return self.running

    def _selector_loop(self, max_client, buffer_size, timeout):
        while self.running:
            events = self._selector.select(0.5)

            for key, mask in events:
                if key.data == "listen":
                    self._accept_client(max_client)
                elif key.data == "client":
                    self._handle_self_read(buffer_size)
                else:
                    self._handle_server_client(key.data, buffer_size)

    def _accept_client(self, max_client: int):
        if self.client_manager.count() >= max_client or not self.running:
            return
        conn, addr = self._sock.accept()
        client_sock = AsyncSocket._create_client_instance(
            conn, self._logger, self.request_handler, self.max_message_size
        )
        client = ClientInfo(client_sock, addr, self.id_count)
        client_id = self.client_manager.add_client(client)
        self._selector.register(client_sock, selectors.EVENT_READ, data=client_id)
        self.id_count += 1
        return

    def _handle_server_client(self, client_id: int, buffer_size: int) -> None:
        entry = self.client_manager.get_client(client_id)
        if not entry:
            return

        sock = entry.info.conn

        try:
            data = sock.recv(buffer_size)
        except BlockingIOError:
            return
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            data = b""

        if not data:
            self.close_client(client_id)
            return

        entry.buffer.add_data(data)
        messages = entry.buffer.extract_messages()
        if messages:
            for message in messages:
                self.request_handler.handle(message, entry.info)

    def _handle_self_read(self, buffer_size: int):
        try:
            data = self._sock.recv(buffer_size)
        except BlockingIOError:
            return
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            data = b""

        if not data:
            self.disconnect(0.5)
            return

        self._client_buffer.add_data(data)
        messages = self._client_buffer.extract_messages()
        if messages:
            for message in messages:
                self.request_handler.handle(message)

    def close_client(self, client: Union[ClientEntry, int]) -> bool:
        if isinstance(client, ClientEntry):
            self._close_server_client(client)
            return True
        entry = self.client_manager.get_client(client)
        if not entry:
            return False
        self._close_server_client(entry)
        return True

    def _close_server_client(self, entry: ClientEntry) -> None:
        entry.info.conn.close()

        self._selector.unregister(entry.info.conn)

        self.client_manager.remove_client(entry.id)

        if self.on_disconnect:
            self.on_disconnect(entry.info)

    def close(self) -> bool:
        try:
            self.running = False
            self._selector.unregister(self._sock)
            self._sock.close()
            self.client_manager.iter_on_clients(self._close_server_client)
            self._selector.close()
            if self._selector_thread and self._selector_thread != threading.current_thread():
                self._selector_thread.join(timeout=0.2)
            return True
        except Exception:
            return False

    def connect(self, host: str, port: int, buffer_size: int, timeout: float) -> bool:
        try:
            self._sock.connect((host, port))
            self._sock.setblocking(False)
            self.running = True
            self._selector.register(self._sock, selectors.EVENT_READ, data="client")
            self._selector_thread = threading.Thread(
                target=self._selector_loop, args=(0, buffer_size, timeout)
            )
            self._selector_thread.start()
            return True
        except (TimeoutError, ConnectionRefusedError) as e:
            return False
        except Exception as e:
            return False

    def disconnect(self, timeout: float = 5.0) -> bool:
        try:
            self.running = False
            self._selector.unregister(self._sock)
            self._sock.close()
            if self._selector_thread and threading.current_thread() != self._selector_thread:
                self._selector_thread.join(timeout=timeout + 0.1)
            return True

        except Exception as e:
            return False
