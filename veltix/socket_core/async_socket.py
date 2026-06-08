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

    def close(self) -> bool: ...
    def bind(
        self, host: str, port: int, max_client: int, buffer_size: int, timeout: float
    ) -> bool: ...
    def connect(self, host: str, port: int, buffer_size: int, timeout: float) -> bool: ...
    def close_client(self, client) -> bool: ...
    def disconnect(self, timeout: float) -> bool: ...
