"""Threading-based socket implementation for Veltix."""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Callable
from typing import Optional

from ..handler.request_handler import RequestHandler
from ..internal.network import RecvResult, recv
from ..logger import Logger
from ..network.message_buffer import MessageBuffer
from ..server.client_info import ClientInfo
from .base_socket import BaseSocket, SocketEvents


class ThreadingSocket(BaseSocket):
    """Threading-based socket implementation for Veltix (one thread per client)."""

    def __init__(self, request_handler: RequestHandler, max_message_size: int) -> None:
        self.n_th = 0
        self._n_th_lock = threading.Lock()

        self._client_buffers: dict[ThreadingSocket, MessageBuffer] = {}
        self._buffers_lock = threading.Lock()

        self.clients: list[ClientInfo] = []
        self._clients_lock = threading.Lock()

        self.threads: dict[int, threading.Thread] = {}
        self._threads_lock = threading.Lock()

        self.running = False
        self.start_th: Optional[threading.Thread] = None
        self.thread_handler: Optional[threading.Thread] = None

        self.on_connect: Optional[Callable] = None
        self.on_disconnect: Optional[Callable] = None
        self.on_recv: Optional[Callable] = None

        self.max_message_size = max_message_size
        self.request_handler = request_handler
        self._logger = Logger.get_instance()

        self._sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._sock.settimeout(0.5)

    @classmethod
    def _create_client_instance(
        cls,
        sock: socket.socket,
        logger: Logger,
        request_handler: RequestHandler,
        max_message_size: int,
    ) -> ThreadingSocket:
        """Create a properly initialized client socket instance."""
        conn = cls.__new__(cls)
        conn._sock = sock
        conn._logger = logger
        conn.request_handler = request_handler
        conn.max_message_size = max_message_size
        conn.running = False
        conn.on_connect = None
        conn.on_disconnect = None
        conn.on_recv = None
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

    def bind(self, host: str, port: int, max_client: int, buffer_size: int, timeout: float) -> None:
        if self.running:
            return
        self.running = True
        self._sock.bind((host, port))
        self.start_th = threading.Thread(
            target=self._accept_loop,
            args=(host, port, max_client, buffer_size, timeout),
            daemon=True,
        )
        self.start_th.start()

    def _accept_loop(
        self, host: str, port: int, max_client: int, buffer_size: int, timeout: float
    ) -> None:
        self._sock.listen()
        self._sock.settimeout(timeout)
        self._logger.info(f"Server listening on {host}:{port}")

        while self.running:
            try:
                with self._clients_lock:
                    current_count = len(self.clients)

                if 0 < max_client <= current_count:
                    time.sleep(0.1)
                    continue

                conn_, addr = self._sock.accept()
                conn = ThreadingSocket._create_client_instance(
                    conn_, self._logger, self.request_handler, self.max_message_size
                )

                with self._n_th_lock:
                    self.n_th += 1
                    thread_id = self.n_th

                client = ClientInfo(conn=conn, addr=addr, thread_id=thread_id, handshake_done=False)

                with self._clients_lock:
                    self.clients.append(client)
                    total = len(self.clients)

                self._logger.info(f"New client connected: {addr} (total: {total}/{max_client})")

                thread = threading.Thread(
                    target=self._handle_server_client,
                    args=(client, buffer_size, timeout),
                    daemon=True,
                )
                thread.start()

                with self._threads_lock:
                    self.threads[thread_id] = thread

            except TimeoutError:
                continue
            except OSError:
                return
            except Exception as e:
                if self.running:
                    self._logger.error(f"Accept error: {type(e).__name__}: {e}")
                return

    def _handle_server_client(self, client: ClientInfo, buffer_size: int, timeout: float) -> None:
        client.conn.settimeout(timeout)

        with self._buffers_lock:
            self._client_buffers[client.conn] = MessageBuffer(
                max_message_size=self.max_message_size
            )

        handshake_request_id, hello = self.request_handler.handshake_handler.prepare_hello()
        self.request_handler.register(handshake_request_id)
        self.request_handler.handshake_handler.send_hello(hello, client.conn)

        while self.running:
            result = recv(client.conn, buffer_size)
            if not self._process_server_message(result, client, handshake_request_id):
                break

    def _process_server_message(
        self, result: RecvResult, client: ClientInfo, handshake_request_id: bytes
    ) -> bool:
        if result.timed_out:
            return True

        if result.disconnected:
            self._logger.info(f"Client {client.addr} disconnected")
            self.request_handler.unregister(handshake_request_id)
            self._close_server_client(client)
            return False

        try:
            with self._buffers_lock:
                buffer = self._client_buffers.get(client.conn)
                if buffer is None:
                    self._logger.warning(f"No buffer for client {client.addr}")
                    return True
                buffer.add_data(result.data)
                messages = buffer.extract_messages()

            for response in messages:
                self._logger.debug(
                    f"Message from {client.addr}: {response.type.name} (code={response.type.code})"
                )

                handler_result = self.request_handler.handle(response, client)
                if isinstance(handler_result, Exception):
                    self._logger.error(f"Handler error for {client.addr}: {handler_result}")

                if not client.handshake_done:
                    self._check_server_handshake(client, handshake_request_id)

        except Exception as e:
            self._logger.error(
                f"Error processing message from {client.addr}: {type(e).__name__}: {e}"
            )

        return True

    def _check_server_handshake(self, client: ClientInfo, handshake_request_id: bytes) -> None:
        with self.request_handler.pending_requests_lock:
            queue = self.request_handler.pending_requests.get(handshake_request_id)
            is_resolved = queue is not None and not queue.empty()
            if is_resolved:
                self.request_handler.pending_requests.pop(handshake_request_id, None)
                client.handshake_done = True

        if not is_resolved:
            return

        self._logger.debug(f"Handshake complete for {client.addr}")

        if self.on_connect:
            try:
                self.on_connect(client)
            except Exception as e:
                self._logger.error(f"on_connect error for {client.addr}: {type(e).__name__}: {e}")

    def _close_server_client(self, client: ClientInfo) -> None:
        client.conn.close()

        with self._threads_lock:
            thread = self.threads.pop(client.thread_id, None)
            if thread and thread != threading.current_thread():
                thread.join(timeout=0.2)

        with self._buffers_lock:
            self._client_buffers.pop(client.conn, None)

        with self._clients_lock:
            if client in self.clients:
                self.clients.remove(client)

        if self.on_disconnect:
            self.on_disconnect(client)

    def close_all(self) -> bool:
        try:
            self.running = False
            with self._clients_lock:
                clients_copy = list(self.clients)
            for client in clients_copy:
                self._close_server_client(client)
            self._sock.close()
            if self.start_th and self.start_th != threading.current_thread():
                self.start_th.join(timeout=0.2)
            return True
        except Exception:
            return False

    close = close_all

    # ── Client ────────────────────────────────────────────────────────────────

    def connect(self, host: str, port: int, buffer_size: int, timeout: float) -> bool:
        try:
            self._logger.info(f"Connecting to {host}:{port}")
            self._sock.connect((host, port))
            self.running = True

            self.thread_handler = threading.Thread(
                target=self._handle_client,
                args=(buffer_size, timeout),
                daemon=True,
            )
            self.thread_handler.start()
            return True

        except (TimeoutError, ConnectionRefusedError) as e:
            self._logger.error(f"Connection failed to {host}:{port}: {type(e).__name__}")
            return False

        except Exception as e:
            self._logger.error(f"Unexpected connection error: {type(e).__name__}: {e}")
            return False

    def _handle_client(self, buffer_size: int, timeout: float) -> None:
        message_buffer = MessageBuffer(max_message_size=self.max_message_size)

        while self.running:
            result = recv(self, buffer_size)

            if result.timed_out:
                continue

            if result.disconnected:
                self._logger.info("Disconnected from server")
                if self.on_disconnect:
                    self.on_disconnect()
                break

            try:
                message_buffer.add_data(result.data)

                for response in message_buffer.extract_messages():
                    self._logger.debug(
                        f"Message from server: {response.type.name} (code={response.type.code})"
                    )

                    handler_result = self.request_handler.handle(response)
                    if isinstance(handler_result, Exception):
                        self._logger.error(f"Handler error: {handler_result}")

            except Exception as e:
                self._logger.error(f"Error processing server message: {type(e).__name__}: {e}")

    def disconnect(self, timeout: float = 5.0) -> bool:
        try:
            self.running = False

            if self.thread_handler and threading.current_thread() != self.thread_handler:
                self.thread_handler.join(timeout=timeout + 0.1)

            self._sock.close()
            self._logger.info("Disconnected from server")
            return True

        except Exception as e:
            self._logger.error(f"Disconnect error: {type(e).__name__}: {e}")
            return False
