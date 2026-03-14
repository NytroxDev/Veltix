"""Base socket protocol for Veltix."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class BaseSocket(Protocol):
    """
    Protocol defining the interface that all Veltix socket implementations must satisfy.

    Any class implementing these methods is automatically considered a valid
    BaseSocket — no inheritance required. This allows third-party and native
    implementations (AsyncSocket, RustSocket via PyO3) to conform without
    depending on Veltix internals.

    Implementations are responsible for their own internal configuration
    (socket options, file descriptors, event loops) — none of that leaks
    into this interface.
    """

    def bind(self, addr: tuple[str, int]) -> None:
        """
        Bind the socket to a local address.

        Args:
            addr: Tuple of (host, port) to bind to.
        """
        ...

    def listen(self) -> None:
        """Start listening for incoming connections."""
        ...

    def accept(self) -> tuple["BaseSocket", tuple[str, int]]:
        """
        Accept an incoming connection.

        Blocks until a client connects.

        Returns:
            Tuple of (client_socket, (host, port)).
        """
        ...

    def connect(self, addr: tuple[str, int]) -> None:
        """
        Connect to a remote server.

        Args:
            addr: Tuple of (host, port) to connect to.
        """
        ...

    def send(self, data: bytes) -> bool:
        """
        Send raw bytes over the socket.

        Args:
            data: Bytes to send.

        Returns:
            True if the data was sent successfully, False otherwise.
        """
        ...

    def recv(self, buffer_size: int) -> bytes:
        """
        Receive raw bytes from the socket.

        Args:
            buffer_size: Maximum number of bytes to read.

        Returns:
            Received bytes, or empty bytes if the connection was closed.
        """
        ...

    def close(self) -> None:
        """Close the socket and release its resources."""
        ...

    def settimeout(self, timeout: float) -> None:
        """
        Set a timeout on blocking socket operations.

        Args:
            timeout: Timeout in seconds. Use 0 for non-blocking mode.
        """
        ...
