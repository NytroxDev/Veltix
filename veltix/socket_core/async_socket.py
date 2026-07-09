"""Selector-based socket implementation for Veltix."""

from __future__ import annotations

import contextlib
import selectors
import socket
import threading
from typing import TYPE_CHECKING, Optional, Union, cast

from ..internal.events import ClientEvent, ErrorEvent, MessageEvent, ServerEvent
from ..internal.network import recv as _network_recv
from ..network.message_buffer import MessageBuffer
from ..server.client_info import ClientInfo
from .base_socket import BaseSocket
from .managers.clients_manager import ClientEntry, ClientsManager

if TYPE_CHECKING:
    from ..handler.request_handler import RequestHandler
    from ..internal.bus import VeltixBus


class AsyncSocket(BaseSocket):
    """Selector-based socket implementation for Veltix."""

    def __init__(self, request_handler: RequestHandler, max_message_size: int, bus: VeltixBus) -> None:
        self.bus = bus
        self.client_manager = ClientsManager(max_message_size)

        self.id_count = 0

        self.running = False

        self._selector_thread: Optional[threading.Thread] = None

        self.max_message_size = max_message_size
        self.request_handler = request_handler
        self.handshake_timeout: float = 5.0

        self._sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        self._selector = selectors.DefaultSelector()

        self._client_buffer = MessageBuffer(max_message_size)

        self.bus.debug("AsyncSocket initialized")

    @classmethod
    def _create_client_instance(
        cls,
        sock: socket.socket,
        bus: VeltixBus,
        request_handler: RequestHandler,
        max_message_size: int,
        handshake_timeout: float = 5.0,
        nonblocking: bool = True,
    ) -> AsyncSocket:
        """Create a properly initialized client socket instance."""
        conn = cls.__new__(cls)
        conn.bus = bus
        conn.client_manager = ClientsManager(max_message_size)

        conn.id_count = 0

        conn.running = False

        conn._selector_thread = None

        conn.max_message_size = max_message_size
        conn.request_handler = request_handler
        conn.handshake_timeout = handshake_timeout

        conn._sock = sock
        conn._sock.setblocking(not nonblocking)
        conn._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        with contextlib.suppress(AttributeError, OSError):
            conn._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        conn._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        conn._selector = selectors.DefaultSelector()

        conn._client_buffer = MessageBuffer(max_message_size)
        conn.bus.debug(f"created client socket instance (fd={conn._sock.fileno()})")
        return conn

    # ── Shared helpers ────────────────────────────────────────────────────────

    def recv(self, buf_size: int) -> bytes:
        return self._sock.recv(buf_size)

    def send(self, data: bytes) -> bool:
        try:
            self._sock.sendall(data)
            self.bus.debug(f"send {len(data)} bytes")
            return True
        except BlockingIOError:
            try:
                self._sock.setblocking(True)
                self._sock.sendall(data)
                self._sock.setblocking(False)
                return True
            except Exception as e:
                self.bus.emit(ErrorEvent.SEND, {"error": str(e)})
                self.bus.debug(f"send BlockingIOError fallback failed: {e}")
                return False
        except Exception as e:
            self.bus.emit(ErrorEvent.SEND, {"error": str(e)})
            self.bus.debug(f"send failed: {e}")
            return False

    def _shutdown_socket(self) -> None:
        with contextlib.suppress(OSError):
            self._sock.shutdown(socket.SHUT_RDWR)

    def settimeout(self, timeout: float) -> bool:
        try:
            self._sock.settimeout(timeout)
            self.bus.debug(f"settimeout {timeout}s")
            return True
        except Exception as e:
            self.bus.debug(f"settimeout {timeout}s failed: {e}")
            return False

    # ── Server ────────────────────────────────────────────────────────────────

    def bind(self, host: str, port: int, max_client: int, buffer_size: int, timeout: float) -> bool:
        self._sock.setblocking(False)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        with contextlib.suppress(AttributeError, OSError):
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self._sock.bind((host, port))
        self._sock.listen()
        self._selector.register(self._sock, selectors.EVENT_READ, data="listen")
        self.running = True
        self._selector_thread = threading.Thread(
            target=self._selector_loop, args=(max_client, buffer_size), daemon=True
        )
        self._selector_thread.start()
        self.bus.debug(
            f"bound to {host}:{port}, max_client={max_client}, running={self.running}"
        )
        return self.running

    def _selector_loop(self, max_client: int, buffer_size: int) -> None:
        while self.running:
            events = self._selector.select(0.5)

            for key, _ in events:
                if key.data == "listen":
                    self._accept_client(max_client)
                elif key.data == "client":
                    self._handle_self_read(buffer_size)
                    if not self.running:
                        break
                else:
                    self._handle_server_client(key.data, buffer_size)

    def fileno(self) -> int:
        return self._sock.fileno()

    def _accept_client(self, max_client: int) -> None:
        if max_client != -1 and self.client_manager.count() >= max_client:
            self.bus.emit(ErrorEvent.CONNECTION_REFUSED, {
                "max_client": max_client,
                "current": self.client_manager.count(),
            })
            return
        if not self.running:
            return
        try:
            conn, addr = self._sock.accept()
        except BlockingIOError:
            return
        except OSError as e:
            self.bus.emit(ErrorEvent.ACCEPT, {"error": str(e)})
            self.bus.error(f"accept failed: {e}")
            return
        self.bus.debug(f"accepted client from {addr}")

        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        client_sock = AsyncSocket._create_client_instance(
            conn,
            self.bus,
            self.request_handler,
            self.max_message_size,
            handshake_timeout=self.handshake_timeout,
            nonblocking=False,
        )
        client = ClientInfo(client_sock, addr, self.id_count, handshake_done=False, bus=self.bus)
        client_id = self.client_manager.add_client(client)

        client.handshake_done = True

        ok = self.request_handler.handshake_handler.do_server_handshake(
            conn, timeout=client_sock.handshake_timeout
        )
        if not ok:
            client.handshake_done = False
            self.bus.warning(f"Handshake failed for {addr}")
            entry = self.client_manager.get_client(client_id)
            if entry:
                self._close_server_client(entry)
            else:
                client_sock._shutdown_socket()
                with contextlib.suppress(OSError):
                    conn.close()
            return

        conn.setblocking(False)
        self._selector.register(client_sock, selectors.EVENT_READ, data=client_id)
        self.id_count += 1
        self.bus.info(
            f"New client connected: {addr} (total: {self.client_manager.count()}/{max_client})"
        )

        try:
            self.bus.emit(ServerEvent.ON_CONNECT, client)
        except Exception as e:
            self.bus.error(f"ServerEvent.ON_CONNECT error for {addr}: {type(e).__name__}: {e}")

    def _handle_server_client(self, client_id: int, buffer_size: int) -> None:
        entry = self.client_manager.get_client(client_id)
        if not entry:
            return

        sock = entry.info.conn

        result = _network_recv(sock, buffer_size)

        if result.timed_out:
            return

        if result.disconnected:
            self.bus.debug(f"client {client_id} disconnected")
            self.close_client(client_id)
            return

        data = result.data or b""
        self.bus.debug(f"client {client_id} recv {len(data)} bytes")
        entry.buffer.add_data(data)
        messages = entry.buffer.extract_messages()
        if messages:
            self.bus.debug(f"client {client_id} extracted {len(messages)} messages")
            for message in messages:
                self.bus.emit(MessageEvent.RECEIVED, {
                    "type": message.type,
                    "length": len(message.content),
                    "client": entry.info.addr,
                })
                self.request_handler.handle(message, entry.info)

    def _handle_self_read(self, buffer_size: int) -> None:
        result = _network_recv(self, buffer_size)

        if result.timed_out:
            return

        if result.disconnected:
            self.bus.debug("self_read: disconnected from server")
            self.bus.emit(ClientEvent.SOCKET_DISCONNECTED)
            self.disconnect(0.5)
            return

        data = result.data or b""
        self.bus.debug(f"self_read: recv {len(data)} bytes")
        self._client_buffer.add_data(data)
        messages = self._client_buffer.extract_messages()
        if messages:
            self.bus.debug(f"self_read: extracted {len(messages)} messages")
            for message in messages:
                self.bus.emit(MessageEvent.RECEIVED, {
                    "type": message.type,
                    "length": len(message.content),
                    "from": "server",
                })
                self.request_handler.handle(message)

    def close_client(self, client: Union[ClientEntry, int]) -> bool:
        if isinstance(client, ClientEntry):
            self._close_server_client(client)
            return True
        entry = self.client_manager.get_client(client)
        if not entry:
            self.bus.debug(f"close_client: client {client} not found")
            return False
        self._close_server_client(entry)
        return True

    def _close_server_client(self, entry: ClientEntry) -> None:
        self.bus.debug(f"closing server client {entry.id} ({entry.info.addr})")
        client_sock = cast("AsyncSocket", entry.info.conn)

        with contextlib.suppress(KeyError):
            self._selector.unregister(client_sock)

        client_sock._shutdown_socket()
        with contextlib.suppress(OSError):
            client_sock._sock.close()

        self.client_manager.remove_client(entry.id)

        try:
            self.bus.emit(ServerEvent.ON_DISCONNECT, entry.info)
        except Exception as e:
            self.bus.error(f"ServerEvent.ON_DISCONNECT error: {type(e).__name__}: {e}")

    def close(self) -> bool:
        try:
            self.bus.debug("closing server socket")
            self.running = False
            self._selector.unregister(self._sock)
            self._shutdown_socket()
            with contextlib.suppress(OSError):
                self._sock.close()
            self.client_manager.iter_on_clients(self._close_server_client)
            self._selector.close()
            if self._selector_thread and self._selector_thread != threading.current_thread():
                self._selector_thread.join(timeout=0.2)
            self.bus.debug("server socket closed")
            return True
        except Exception as e:
            self.bus.debug(f"close failed: {e}")
            return False

    def connect(self, host: str, port: int, buffer_size: int, timeout: float) -> bool:
        try:
            self._sock.connect((host, port))

            success, meta = self.request_handler.handshake_handler.do_client_handshake(self._sock)
            if not success:
                self.bus.error("Client handshake failed")
                self._sock.close()
                return False

            self._handshake_meta = meta

            self._sock.setblocking(False)
            self.running = True
            self._selector.register(self._sock, selectors.EVENT_READ, data="client")
            self._selector_thread = threading.Thread(
                target=self._selector_loop, args=(0, buffer_size), daemon=True
            )
            self._selector_thread.start()
            self.bus.debug(f"connected to {host}:{port}")
            return True
        except (socket.timeout, ConnectionRefusedError) as e:
            self.bus.emit(ErrorEvent.NETWORK, {"error": str(e), "host": host, "port": port})
            self.bus.debug(f"connect to {host}:{port} failed: {e}")
            return False
        except Exception as e:
            self.bus.emit(ErrorEvent.NETWORK, {"error": str(e), "host": host, "port": port})
            self.bus.debug(f"connect to {host}:{port} failed: {e}")
            return False

    def disconnect(self, timeout: float = 5.0) -> bool:
        try:
            self.bus.debug("disconnecting client socket")
            self.running = False
            self._selector.unregister(self._sock)
            self._shutdown_socket()
            self._sock.close()
            if self._selector_thread and threading.current_thread() != self._selector_thread:
                self._selector_thread.join(timeout=timeout + 0.1)
            self.bus.debug("client socket disconnected")
            return True

        except Exception as e:
            self.bus.debug(f"disconnect failed: {e}")
            return False
