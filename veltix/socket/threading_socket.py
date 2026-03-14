"""Threading-based socket implementation for Veltix."""

import socket


class ThreadingSocket:
    """
    Threading-based socket implementation for Veltix.

    Wraps the standard library socket with the BaseSocket interface.
    All blocking operations run in dedicated threads managed by the server
    and client — one thread per connected client.

    Internal configuration (SO_REUSEADDR, default timeout) is handled
    automatically — Server and Client never need to call setsockopt or
    fileno directly.
    """

    def __init__(self):
        self._sock: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.settimeout(0.5)

    def bind(self, addr: tuple[str, int]) -> None:
        self._sock.bind(addr)

    def listen(self) -> None:
        self._sock.listen()

    def accept(self) -> tuple["ThreadingSocket", tuple[str, int]]:
        conn, addr = self._sock.accept()
        wrapped = ThreadingSocket.__new__(ThreadingSocket)
        wrapped._sock = conn
        return wrapped, addr

    def connect(self, addr: tuple[str, int]) -> None:
        self._sock.connect(addr)

    def send(self, data: bytes) -> bool:
        try:
            self._sock.send(data)
            return True
        except Exception:
            return False

    def recv(self, buffer_size: int) -> bytes:
        return self._sock.recv(buffer_size)

    def close(self) -> None:
        self._sock.close()

    def settimeout(self, timeout: float) -> None:
        self._sock.settimeout(timeout)
