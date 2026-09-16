"""Base socket abstract class for Veltix."""

from __future__ import annotations

import contextlib
import socket
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional, Union

from ..internal.events import ErrorEvent

if TYPE_CHECKING:
    from ..internal.bus import VeltixBus
    from .managers.clients_manager import ClientEntry, ClientsManager


class BaseSocket(ABC):
    """Abstract base class defining the socket backend interface.

    Concrete implementations (``ThreadingSocket``, ``AsyncSocket``) must
    implement every abstract method declared here. The server and client
    layers depend only on this interface, allowing socket backends to be
    swapped at runtime.

    Attributes:
        client_manager: Manages connected client entries.
        handshake_timeout: Timeout in seconds for the handshake phase.
        bus: Event bus for structured observability.
    """

    client: Optional[Any] = None
    client_manager: ClientsManager
    handshake_timeout: float
    bus: VeltixBus
    _sock: socket.socket

    def send(self, data: bytes) -> bool:
        """Send raw bytes over the connection.

        Args:
            data: The bytes to send.

        Returns:
            True if the data was sent successfully, False otherwise.
        """
        try:
            self._sock.sendall(data)
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
            self.bus.error(f"send failed: {e}")
            return False

    def recv(self, buf_size: int) -> bytes:
        """Receive data from the connection.

        Args:
            buf_size: Maximum number of bytes to receive.

        Returns:
            The received bytes, or an empty byte-string on failure.
        """
        return self._sock.recv(buf_size)

    def settimeout(self, timeout: float) -> bool:
        """Set the socket timeout for blocking operations.

        Args:
            timeout: Timeout in seconds.

        Returns:
            True if the timeout was set successfully, False otherwise.
        """
        try:
            self._sock.settimeout(timeout)
            return True
        except Exception:
            return False

    def _shutdown_socket(self) -> None:
        with contextlib.suppress(OSError):
            self._sock.shutdown(socket.SHUT_RDWR)

    def fileno(self) -> int:
        """Return the underlying socket file descriptor.

        Returns:
            The file descriptor of the underlying socket.
        """
        return self._sock.fileno()

    @abstractmethod
    def close(self) -> bool:
        """Close the socket and release associated resources.

        Returns:
            True if the socket was closed successfully, False otherwise.
        """
        ...

    @abstractmethod
    def bind(self, host: str, port: int, max_client: int, buffer_size: int, timeout: float) -> bool:
        """Bind the socket to an address and start listening for connections.

        Args:
            host: The host address to bind to.
            port: The port number to bind to.
            max_client: Maximum number of concurrent clients (-1 for unlimited).
            buffer_size: Receive buffer size in bytes.
            timeout: Timeout in seconds for handshakes.

        Returns:
            True if binding succeeded, False otherwise.
        """
        ...

    @abstractmethod
    def connect(self, host: str, port: int, buffer_size: int, timeout: float) -> bool:
        """Connect to a remote server.

        Args:
            host: The server host address.
            port: The server port number.
            buffer_size: Receive buffer size in bytes.
            timeout: Timeout in seconds for the connection attempt.

        Returns:
            True if the connection was established, False otherwise.
        """
        ...

    @abstractmethod
    def close_client(self, client: Union[ClientEntry, int]) -> bool:
        """Close a specific client connection on the server side.

        Args:
            client: The client entry or client ID to disconnect.

        Returns:
            True if the client was disconnected, False otherwise.
        """
        ...

    @abstractmethod
    def disconnect(self, timeout: float) -> bool:
        """Disconnect from the remote server (client-side).

        Args:
            timeout: Timeout in seconds for the disconnection.

        Returns:
            True if disconnection succeeded, False otherwise. Returns True
            when the socket was never connected (no-op).
        """
        ...
