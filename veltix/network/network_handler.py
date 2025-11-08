# veltix_core.py - Optimized Edition
import selectors
import socket
import time
from collections import deque


# ---- Buffer pool: pre-allocate bytearrays for recv_into to avoid allocations ----
class BufferPool:
    """Zero-allocation buffer pool with fast path optimization"""
    __slots__ = ('buf_size', '_free', '_created')

    def __init__(self, buf_size=8192, pool_size=1024):  # Doubled defaults
        self.buf_size = buf_size
        self._free = deque([bytearray(buf_size) for _ in range(pool_size)], maxlen=pool_size)
        self._created = pool_size

    def get(self):
        try:
            return self._free.pop()
        except IndexError:
            self._created += 1
            return bytearray(self.buf_size)

    def put(self, buf):
        if len(buf) == self.buf_size and len(self._free) < self._free.maxlen:
            self._free.append(buf)

    def stats(self):
        return {'free': len(self._free), 'created': self._created}


# ---- Connection data structure stored in selector ----
class _ConnData:
    __slots__ = ("addr", "inb_view", "outb", "last_activity", "recv_buf",
                 "created_at", "bytes_recv", "bytes_sent", "conn_ready")

    def __init__(self, addr, recv_buf):
        self.addr = addr
        self.inb_view = None
        self.outb = bytearray()
        self.recv_buf = recv_buf
        now = time.monotonic()
        self.last_activity = now
        self.created_at = now
        self.bytes_recv = 0
        self.bytes_sent = 0
        self.conn_ready = False  # For client connections


# ---- Core universal class: provides low-level primitives and loop ----
class VxCore:
    def __init__(self, recv_bufsize=8192, bufpool_size=1024,
                 selector_timeout=0.005, conn_timeout=30.0, max_outbuf=1048576):
        self.sel = selectors.DefaultSelector()
        self.bufpool = BufferPool(buf_size=recv_bufsize, pool_size=bufpool_size)
        self.selector_timeout = selector_timeout
        self.conn_timeout = conn_timeout
        self.max_outbuf = max_outbuf  # 1MB default per connection
        self._running = False
        self._stats = {'accepts': 0, 'connects': 0, 'closes': 0, 'errors': 0}

        # callbacks (set by user)
        self.on_connect = None
        self.on_data = None
        self.on_close = None
        self.on_error = None  # fn(sock, addr, error)

        # Rate limiting (simple per-IP tracking)
        self._ip_conn_count = {}
        self.max_conn_per_ip = 100

    # ---- socket option helpers ----
    @staticmethod
    def _configure_sock_for_server(sock):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        try:
            # Linux: reduce TIME_WAIT
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, 0)
        except (AttributeError, OSError):
            pass
        sock.setblocking(False)

    @staticmethod
    def _configure_sock_for_client(sock):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        try:
            # Increase TCP buffer sizes for throughput
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)  # 256KB
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 262144)
        except (AttributeError, OSError):
            pass
        try:
            # TCP_QUICKACK on Linux for low latency
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
        except (AttributeError, OSError):
            pass
        sock.setblocking(False)

    # ---- server setup ----
    def start_server(self, host: str, port: int, backlog=8192):
        lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._configure_sock_for_server(lsock)
        lsock.bind((host, port))
        lsock.listen(backlog)
        self.sel.register(lsock, selectors.EVENT_READ)
        return lsock

    # ---- non-blocking connect (client) ----
    def connect(self, host: str, port: int):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._configure_sock_for_client(sock)
        sock.connect_ex((host, port))
        recv_buf = self.bufpool.get()
        data = _ConnData(addr=(host, port), recv_buf=recv_buf)
        self.sel.register(sock, selectors.EVENT_WRITE | selectors.EVENT_READ, data=data)
        self._stats['connects'] += 1
        return sock

    # ---- send raw bytes (non-blocking) ----
    def send(self, sock: socket.socket, data: bytes):
        """Queue bytes efficiently with overflow protection"""
        try:
            key = self.sel.get_key(sock)
        except KeyError:
            return False

        data_obj: _ConnData = key.data
        if len(data_obj.outb) + len(data) > self.max_outbuf:
            # Buffer overflow protection - close connection
            self._close_sock(sock)
            return False

        data_obj.outb += data
        self.sel.modify(sock, selectors.EVENT_READ | selectors.EVENT_WRITE, data=data_obj)
        return True

    def send_now(self, sock: socket.socket, data: bytes):
        """Attempt immediate send with fallback to queueing"""
        try:
            sent = sock.send(data)
            if sent < len(data):
                return self.send(sock, data[sent:])
            return True
        except BlockingIOError:
            return self.send(sock, data)
        except Exception:
            self._close_sock(sock)
            return False

    # ---- close connection helper ----
    def _close_sock(self, sock):
        try:
            key = self.sel.get_key(sock)
        except KeyError:
            return

        data_obj = key.data
        addr = data_obj.addr

        # Update rate limiting
        if addr and isinstance(addr, tuple):
            ip = addr[0]
            self._ip_conn_count[ip] = max(0, self._ip_conn_count.get(ip, 1) - 1)
            if self._ip_conn_count[ip] == 0:
                del self._ip_conn_count[ip]

        try:
            self.sel.unregister(sock)
        except Exception:
            pass

        try:
            sock.close()
        except Exception:
            pass

        if data_obj.recv_buf:
            self.bufpool.put(data_obj.recv_buf)

        self._stats['closes'] += 1

        if self.on_close:
            try:
                self.on_close(sock, addr)
            except Exception:
                pass

    # ---- accept routine with rate limiting ----
    def _accept(self, lsock):
        try:
            conn, addr = lsock.accept()
        except (BlockingIOError, InterruptedError):
            return
        except Exception:
            self._stats['errors'] += 1
            return

        # Rate limiting per IP
        ip = addr[0]
        conn_count = self._ip_conn_count.get(ip, 0)
        if conn_count >= self.max_conn_per_ip:
            try:
                conn.close()
            except Exception:
                pass
            return

        self._ip_conn_count[ip] = conn_count + 1

        self._configure_sock_for_client(conn)
        recv_buf = self.bufpool.get()
        data = _ConnData(addr=addr, recv_buf=recv_buf)
        data.conn_ready = True
        self.sel.register(conn, selectors.EVENT_READ, data=data)
        self._stats['accepts'] += 1

        if self.on_connect:
            try:
                self.on_connect(conn, addr)
            except Exception:
                pass

    # ---- service connection: read/write ----
    def _service_connection(self, key, mask):
        sock = key.fileobj
        data: _ConnData = key.data
        now = time.monotonic()
        data.last_activity = now

        # Handle client connection completion
        if not data.conn_ready and (mask & selectors.EVENT_WRITE):
            try:
                err = sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                if err == 0:
                    data.conn_ready = True
                    if self.on_connect:
                        try:
                            self.on_connect(sock, data.addr)
                        except Exception:
                            pass
                    # Continue to write if we have data
                else:
                    self._close_sock(sock)
                    return
            except Exception:
                self._close_sock(sock)
                return

        # READ
        if mask & selectors.EVENT_READ:
            try:
                n = sock.recv_into(data.recv_buf)
            except BlockingIOError:
                n = 0
            except (ConnectionResetError, BrokenPipeError):
                self._close_sock(sock)
                return
            except Exception:
                self._stats['errors'] += 1
                self._close_sock(sock)
                return

            if n > 0:
                data.bytes_recv += n
                mv = memoryview(data.recv_buf)[:n]
                data.inb_view = mv
                if self.on_data:
                    try:
                        self.on_data(sock, mv)
                    except Exception as e:
                        if self.on_error:
                            try:
                                self.on_error(sock, data.addr, e)
                            except Exception:
                                pass
                data.inb_view = None
            else:
                self._close_sock(sock)
                return

        # WRITE
        if mask & selectors.EVENT_WRITE:
            if data.outb:
                try:
                    # Try to send all at once
                    sent = sock.send(data.outb)
                    if sent > 0:
                        data.bytes_sent += sent
                        del data.outb[:sent]
                except BlockingIOError:
                    pass
                except (ConnectionResetError, BrokenPipeError):
                    self._close_sock(sock)
                    return
                except Exception:
                    self._stats['errors'] += 1
                    self._close_sock(sock)
                    return

            # Stop listening for write events if buffer empty
            if not data.outb:
                try:
                    self.sel.modify(sock, selectors.EVENT_READ, data=data)
                except Exception:
                    pass

    # ---- timeout cleanup ----
    def _cleanup_timeouts(self):
        """Remove stale connections (called periodically)"""
        now = time.monotonic()
        to_close = []
        for key in list(self.sel.get_map().values()):
            if key.data is None:
                continue
            data: _ConnData = key.data
            if now - data.last_activity > self.conn_timeout:
                to_close.append(key.fileobj)

        for sock in to_close:
            self._close_sock(sock)

    # ---- loop control ----
    def run_forever(self):
        """Run the selector loop with periodic cleanup"""
        self._running = True
        last_cleanup = time.monotonic()
        cleanup_interval = 5.0  # Check timeouts every 5 seconds

        try:
            while self._running:
                events = self.sel.select(timeout=self.selector_timeout)

                # Process all events in batch
                for key, mask in events:
                    if key.data is None:
                        self._accept(key.fileobj)
                    else:
                        self._service_connection(key, mask)

                # Periodic cleanup
                now = time.monotonic()
                if now - last_cleanup > cleanup_interval:
                    self._cleanup_timeouts()
                    last_cleanup = now

        finally:
            self._running = False
            # Graceful shutdown
            for key in list(self.sel.get_map().values()):
                sock = key.fileobj
                try:
                    self.sel.unregister(sock)
                except Exception:
                    pass
                try:
                    # noinspection PyUnresolvedReferences
                    sock.close()
                except Exception:
                    pass
            self.sel.close()

    def stop(self):
        """Signal the loop to stop"""
        self._running = False

    def close_socket(self, sock):
        """Gracefully close a specific socket"""
        self._close_sock(sock)

    # ---- Statistics and monitoring ----
    def get_stats(self):
        """Return current statistics"""
        active_conns = len([k for k in self.sel.get_map().values() if k.data is not None])
        return {
            **self._stats,
            'active_connections': active_conns,
            'ip_tracked': len(self._ip_conn_count),
            'buffer_pool': self.bufpool.stats()
        }

    def get_connection_info(self, sock):
        """Get detailed info about a specific connection"""
        try:
            key = self.sel.get_key(sock)
            data: _ConnData = key.data
            return {
                'addr': data.addr,
                'bytes_recv': data.bytes_recv,
                'bytes_sent': data.bytes_sent,
                'outbuf_size': len(data.outb),
                'age': time.monotonic() - data.created_at,
                'idle': time.monotonic() - data.last_activity
            }
        except KeyError:
            return None