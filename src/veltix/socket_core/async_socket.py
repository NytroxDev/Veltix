"""Selector-based socket implementation for Veltix."""

from __future__ import annotations

import contextlib
import queue
import selectors
import socket
import threading
from collections import deque
from typing import TYPE_CHECKING, cast

from ..exceptions import ServerFullError
from ..internal.events import ClientEvent, ErrorEvent, ServerEvent
from ..internal.network import (
    apply_tcp_tunings,
    dispatch_messages,
)
from ..internal.network import (
    recv as _network_recv,
)
from ..network import _rust
from ..network.message_buffer import MessageBuffer
from ..server.client_info import ClientInfo
from .base_socket import BaseSocket
from .managers.clients_manager import ClientEntry, ClientsManager

MAX_DRAIN_ITERATIONS = 100

if TYPE_CHECKING:
    from ..handler.request_handler import RequestHandler
    from ..internal.bus import VeltixBus


class AsyncSocket(BaseSocket):
    """Selector-based socket implementation for Veltix."""

    def __init__(
        self,
        request_handler: RequestHandler,
        max_message_size: int,
        bus: VeltixBus,
        sock: socket.socket | None = None,
        handshake_timeout: float = 5.0,
        nonblocking: bool = True,
        use_rust: bool | None = None,
    ) -> None:
        self.bus = bus
        self._use_rust: bool = _rust.rust_enabled() if use_rust is None else use_rust
        self.client_manager = ClientsManager(max_message_size, bus=bus, use_rust=self._use_rust)

        self.id_count = 0

        self._running_event = threading.Event()

        self._selector_thread: threading.Thread | None = None

        # Outbound queue: bytes that did not fit the kernel send buffer are
        # buffered here and flushed by the selector loop when the socket
        # becomes writable, so messages larger than the buffer are delivered
        # instead of being dropped (see send()).
        self._outbound: deque[bytes] = deque()
        self._outbound_lock = threading.Lock()
        # Write-interest registration state, selector thread only.
        self._write_state: dict[int, bool] = {}
        self._is_client = False
        # Sockets with queued outbound data, reported by senders (any thread)
        # and consumed by the selector thread once per loop iteration. The
        # fast path stays O(1): no per-client work when nothing is queued.
        self._owner = self
        self._write_dirty: list[AsyncSocket] = []
        self._write_dirty_lock = threading.Lock()
        self._conn_ids: dict[int, int] = {}

        self.max_message_size = max_message_size
        self.request_handler = request_handler
        self.handshake_timeout = handshake_timeout

        if sock is None:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            apply_tcp_tunings(self._sock)

            self._selector = selectors.DefaultSelector()

            # Completed (or failed) handshakes are posted here by worker
            # threads and drained by the selector loop.
            self._handshake_queue: queue.Queue[tuple[str, int]] = queue.Queue()

            self._client_buffer = MessageBuffer(max_message_size, use_rust=self._use_rust)

            self.bus.debug("AsyncSocket initialized")
        else:
            self._sock = sock
            self._sock.setblocking(not nonblocking)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            with contextlib.suppress(AttributeError, OSError):
                self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            apply_tcp_tunings(self._sock)

            self.bus.debug(f"created client socket instance (fd={self._sock.fileno()})")

    # ── Server ────────────────────────────────────────────────────────────────

    def bind(self, host: str, port: int, max_client: int, buffer_size: int, timeout: float) -> bool:
        self._sock.setblocking(False)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        with contextlib.suppress(AttributeError, OSError):
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self._sock.bind((host, port))
        self._sock.listen()
        self._selector.register(self, selectors.EVENT_READ, data="listen")
        self._running_event.set()
        self._selector_thread = threading.Thread(
            target=self._selector_loop,
            args=(max_client, buffer_size),
            daemon=True,
            name="veltix-selector",
        )
        self._selector_thread.start()
        self.bus.debug(
            f"bound to {host}:{port}, max_client={max_client}, running={self._running_event.is_set()}"
        )
        return self._running_event.is_set()

    def _selector_loop(self, max_client: int, buffer_size: int) -> None:
        while self._running_event.is_set():
            self._drain_handshake_queue(max_client)
            self._sync_dirty_sockets()
            events = self._selector.select(0.5)

            for key, mask in events:
                if key.data == "listen":
                    self._accept_client(max_client)
                elif key.data == "client":
                    if mask & selectors.EVENT_WRITE:
                        self._flush_outbound()
                    if mask & selectors.EVENT_READ and self._running_event.is_set():
                        self._handle_self_read(buffer_size)
                else:
                    if mask & selectors.EVENT_WRITE:
                        self._flush_client_outbound(key.data)
                    if mask & selectors.EVENT_READ:
                        self._handle_server_client(key.data, buffer_size)

    def _accept_client(self, max_client: int) -> None:
        if not self._running_event.is_set():
            return
        try:
            conn, addr = self._sock.accept()
        except BlockingIOError:
            return
        except OSError as e:
            self.bus.emit(ErrorEvent.ACCEPT, {"error": str(e)})
            self.bus.error(f"accept failed: {e}")
            return

        if max_client >= 0 and self.client_manager.count() >= max_client:
            self.bus.info(
                f"Connection rejected: server full ({addr}, "
                f"{self.client_manager.count()}/{max_client})"
            )
            self.bus.emit(
                ErrorEvent.CONNECTION_REFUSED,
                {
                    "max_client": max_client,
                    "current": self.client_manager.count(),
                    "addr": addr,
                },
            )
            self.bus.emit(
                ServerEvent.CLIENT_REJECTED,
                {
                    "max_client": max_client,
                    "current": self.client_manager.count(),
                    "reason": "server_full",
                    "addr": addr,
                },
            )
            with contextlib.suppress(OSError):
                self.request_handler.handshake_handler.send_rejection(conn, "server_full")
            with contextlib.suppress(OSError):
                conn.close()
            return

        self.bus.debug(f"accepted client from {addr}")

        apply_tcp_tunings(conn)

        client_sock = AsyncSocket(
            self.request_handler,
            self.max_message_size,
            self.bus,
            sock=conn,
            handshake_timeout=self.handshake_timeout,
            nonblocking=False,
            use_rust=self._use_rust,
        )
        # Accepted sockets are managed by the parent selector (only the
        # selector thread touches it); give them the references so an
        # outbound enqueue can wake it up and report itself as dirty.
        client_sock._selector = self._selector
        client_sock._owner = self
        client_id = self.client_manager.add_client(
            ClientInfo(
                client_sock,
                addr,
                self.id_count,
                handshake_done=False,
                bus=self.bus,
            )
        )
        self.id_count += 1
        self._conn_ids[id(client_sock)] = client_id

        # thread_id mirrors the manager client_id (1-based) so the metadata
        # stays consistent with the threading backend.
        entry = self.client_manager.get_client(client_id)
        if entry is not None:
            entry.info.thread_id = client_id

        # The blocking handshake runs in a worker thread: a peer that connects
        # but never completes its handshake must not stall the selector loop
        # (remote DoS). The worker posts the outcome to a queue that the
        # selector thread drains, because only it may touch the selector.
        threading.Thread(
            target=self._handshake_worker,
            args=(client_id, conn, addr),
            daemon=True,
            name=f"veltix-handshake-{client_id}",
        ).start()

    def _handshake_worker(self, client_id: int, conn: socket.socket, addr: tuple[str, int]) -> None:
        """Run the blocking handshake off the selector thread.

        Args:
            client_id: Manager ID of the accepted client.
            conn: Raw accepted socket (owned by this thread until done).
            addr: ``(host, port)`` of the peer.
        """
        ok = self.request_handler.handshake_handler.do_server_handshake(
            conn, timeout=self.handshake_timeout
        )
        if not ok:
            self.bus.warning(f"Handshake failed for {addr}")
            self._handshake_queue.put(("fail", client_id))
            return

        entry = self.client_manager.get_client(client_id)
        if entry is None:
            # Server shut down while the handshake was in flight.
            with contextlib.suppress(OSError):
                conn.close()
            return

        entry.info.handshake_done = True
        with contextlib.suppress(OSError):
            conn.setblocking(False)
        self._handshake_queue.put(("ok", client_id))

    def _drain_handshake_queue(self, max_client: int) -> None:
        """Register (or clean up) clients whose handshake finished in a worker.

        Args:
            max_client: Maximum connection count, for logging only.
        """
        while True:
            try:
                kind, client_id = self._handshake_queue.get_nowait()
            except queue.Empty:
                break

            entry = self.client_manager.get_client(client_id)
            if entry is None:
                continue

            if kind == "ok":
                self._selector.register(entry.info.conn, selectors.EVENT_READ, data=client_id)
                self.bus.info(
                    f"New client connected: {entry.info.addr} "
                    f"(total: {self.client_manager.count()}/{max_client})"
                )
                try:
                    self.bus.emit(ServerEvent.ON_CONNECT, entry.info)
                except Exception as e:
                    self.bus.error(
                        f"ServerEvent.ON_CONNECT error for {entry.info.addr}: "
                        f"{type(e).__name__}: {e}"
                    )
            else:
                self._close_server_client(entry)

    def _handle_server_client(self, client_id: int, buffer_size: int) -> None:
        entry = self.client_manager.get_client(client_id)
        if not entry:
            return

        sock = entry.info.conn

        for _ in range(MAX_DRAIN_ITERATIONS):
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
            dispatch_messages(
                entry.buffer,
                self.bus,
                lambda message: self.request_handler.handle(message, entry.info),
                client_addr=entry.info.addr,
            )

    def _handle_self_read(self, buffer_size: int) -> None:
        for _ in range(MAX_DRAIN_ITERATIONS):
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
            dispatch_messages(
                self._client_buffer,
                self.bus,
                lambda response: self.request_handler.handle(response),
            )

    # ── Outbound queue (large sends) ─────────────────────────────────────────

    def send(self, data: bytes) -> bool:
        """Send raw bytes, queueing any remainder past the kernel buffer.

        Non-blocking by design: the selector thread never blocks on a slow
        peer. When the kernel send buffer is full, the unsent tail is queued
        and flushed by the selector loop as soon as the socket becomes
        writable again, so messages larger than the buffer are delivered
        instead of being dropped.

        Args:
            data: The bytes to send.

        Returns:
            True when the data was sent or queued for delivery, False on a
            hard connection error.
        """
        try:
            sent = self._sock.send(data)
        except BlockingIOError as e:
            self._enqueue(data[getattr(e, "characters_written", 0) :])
            return True
        except OSError as e:
            self.bus.emit(ErrorEvent.SEND, {"error": str(e)})
            self.bus.error(f"send failed: {e}")
            return False

        if sent < len(data):
            remainder = self._send_rest(data, sent)
            if remainder is None:
                return False
            if remainder:
                self._enqueue(remainder)
        return True

    def _send_rest(self, data: bytes, start: int) -> bytes | None:
        """Send ``data[start:]`` until the kernel buffer blocks.

        Args:
            data: The bytes being sent.
            start: Offset of the first unsent byte.

        Returns:
            The unsent remainder (``b""`` when everything was sent), or
            ``None`` on a hard connection error.
        """
        view = memoryview(data)
        total = start
        while total < len(view):
            try:
                n = self._sock.send(view[total:])
            except BlockingIOError:
                break
            except OSError as e:
                self.bus.emit(ErrorEvent.SEND, {"error": str(e)})
                self.bus.error(f"send failed: {e}")
                return None
            if n <= 0:
                break
            total += n

        return bytes(view[total:])

    def _enqueue(self, data: bytes) -> None:
        with self._outbound_lock:
            self._outbound.append(data)
        # Wake the owner selector so the queued bytes are registered for
        # writing and flushed promptly instead of waiting for the next poll
        # cycle. wakeup() lives on the concrete selector (e.g. EpollSelector),
        # not on BaseSelector, so resolve it dynamically.
        self._owner._mark_dirty(self)

    def _has_outbound(self) -> bool:
        with self._outbound_lock:
            return bool(self._outbound)

    def _drop_outbound(self) -> None:
        with self._outbound_lock:
            self._outbound.clear()

    def _flush_outbound(self) -> None:
        """Push queued bytes on a writable socket (selector thread)."""
        while True:
            with self._outbound_lock:
                if not self._outbound:
                    return
                chunk = self._outbound.popleft()
            try:
                sent = self._sock.send(chunk)
            except BlockingIOError as e:
                with self._outbound_lock:
                    self._outbound.appendleft(chunk[getattr(e, "characters_written", 0) :])
                return
            except OSError as e:
                self.bus.emit(ErrorEvent.SEND, {"error": str(e)})
                self.bus.error(f"send failed: {e}")
                with self._outbound_lock:
                    self._outbound.clear()
                return
            if sent < len(chunk):
                remainder = self._send_rest(chunk, sent)
                if remainder is None:
                    with self._outbound_lock:
                        self._outbound.clear()
                    return
                # Keep the unsent tail in front: it is the current head of
                # the byte stream and must go out before later chunks.
                with self._outbound_lock:
                    self._outbound.appendleft(remainder)
                return

    def _sync_dirty_sockets(self) -> None:
        """Register write interest for sockets that reported queued data."""
        with self._write_dirty_lock:
            dirty = self._write_dirty
            self._write_dirty = []
        for sock in dirty:
            if sock is self:
                if self._is_client:
                    self._sync_socket_interest(sock, "client")
                continue
            client_id = self._conn_ids.get(id(sock))
            if client_id is None:
                continue
            self._sync_socket_interest(sock, client_id)

    def _mark_dirty(self, sock: AsyncSocket) -> None:
        """Report a socket with queued outbound data to the owner selector."""
        with self._write_dirty_lock:
            self._write_dirty.append(sock)
        wakeup = getattr(self._selector, "wakeup", None)
        if wakeup is not None:
            with contextlib.suppress(OSError):
                wakeup()

    def _sync_socket_interest(self, sock: AsyncSocket, data: int | str) -> None:
        """Mirror a socket's outbound state onto the selector interest set.

        Only the selector thread calls this. Sockets with queued data are
        registered for ``EVENT_WRITE``; once drained they go back to
        ``EVENT_READ`` only, so the loop never spins on a busy-tick.

        Args:
            sock: The socket to sync.
            data: Selector data key carried by the registration.
        """
        wants_write = sock._has_outbound()
        sid = id(sock)
        current = self._write_state.get(sid)
        if current == wants_write:
            return
        with contextlib.suppress(KeyError, OSError, ValueError):
            if wants_write:
                self._selector.modify(sock, selectors.EVENT_READ | selectors.EVENT_WRITE, data=data)
            else:
                self._selector.modify(sock, selectors.EVENT_READ, data=data)
        self._write_state[sid] = wants_write

    def _flush_client_outbound(self, client_id: int) -> None:
        entry = self.client_manager.get_client(client_id)
        if entry is None:
            return
        cast("AsyncSocket", entry.info.conn)._flush_outbound()

    def close_client(self, client: ClientEntry | int) -> bool:
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

        self._write_state.pop(id(client_sock), None)
        self._conn_ids.pop(id(client_sock), None)
        client_sock._drop_outbound()

        with contextlib.suppress(KeyError):
            self._selector.unregister(client_sock)

        client_sock._shutdown_socket()
        with contextlib.suppress(OSError):
            client_sock._sock.close()

        # Only the caller that actually removed the entry emits the event: a
        # concurrent close (close, close_client, the selector loop) must not
        # fire ON_DISCONNECT twice.
        if not self.client_manager.remove_client(entry.id):
            return

        try:
            self.bus.emit(ServerEvent.ON_DISCONNECT, entry.info)
        except Exception as e:
            self.bus.error(f"ServerEvent.ON_DISCONNECT error: {type(e).__name__}: {e}")

    def close(self) -> bool:
        try:
            self.bus.debug("closing server socket")
            self._running_event.clear()
            with contextlib.suppress(KeyError):
                self._selector.unregister(self)
            self._drop_outbound()
            self._write_state.clear()
            self._conn_ids.clear()
            with self._write_dirty_lock:
                self._write_dirty.clear()
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

            success, _ = self.request_handler.handshake_handler.do_client_handshake(
                self._sock, timeout=timeout
            )
            if not success:
                self.bus.error("Client handshake failed")
                self._sock.close()
                return False

            self._sock.setblocking(False)
            self._running_event.set()
            self._is_client = True
            self._selector.register(self, selectors.EVENT_READ, data="client")

            if hasattr(self, "client") and self.client:
                with self.client._state_lock:
                    self.client.is_connected = True
                    self.client._connecting = False

            self._selector_thread = threading.Thread(
                target=self._selector_loop,
                args=(0, buffer_size),
                daemon=True,
                name="veltix-selector",
            )
            self._selector_thread.start()
            self.bus.debug(f"connected to {host}:{port}")
            return True
        except (TimeoutError, ConnectionRefusedError) as e:
            # The socket may be half-open (connect or handshake in flight):
            # release its fd now instead of leaking it until reconnection.
            self._sock.close()
            self.bus.emit(ErrorEvent.NETWORK, {"error": str(e), "host": host, "port": port})
            self.bus.debug(f"connect to {host}:{port} failed: {e}")
            return False
        except ServerFullError:
            raise
        except Exception as e:
            self.bus.emit(ErrorEvent.NETWORK, {"error": str(e), "host": host, "port": port})
            self.bus.debug(f"connect to {host}:{port} failed: {e}")
            return False

    def disconnect(self, timeout: float = 5.0) -> bool:
        try:
            self.bus.debug("disconnecting client socket")
            self._running_event.clear()
            with contextlib.suppress(KeyError):
                self._selector.unregister(self)
            self._drop_outbound()
            self._write_state.clear()
            self._conn_ids.clear()
            with self._write_dirty_lock:
                self._write_dirty.clear()
            self._shutdown_socket()
            self._sock.close()
            if self._selector_thread and threading.current_thread() != self._selector_thread:
                self._selector_thread.join(timeout=timeout + 0.1)
            self.bus.debug("client socket disconnected")
            return True

        except Exception as e:
            self.bus.debug(f"disconnect failed: {e}")
            return False
