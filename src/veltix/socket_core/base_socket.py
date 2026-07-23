"""Base socket abstract class for Veltix."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    from ..internal.bus import VeltixBus
    from ..network.id_allocator import ClientAllocator
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
        client_allocator: Optional ID allocator for client-bound request IDs.
    """

    client_manager: ClientsManager
    handshake_timeout: float
    bus: VeltixBus
    client_allocator: Optional[ClientAllocator]

    @abstractmethod
    def send(self, data: bytes) -> bool:
        """Send raw bytes over the connection.

        Args:
            data: The bytes to send.

        Returns:
            True if the data was sent successfully, False otherwise.
        """
        ...

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
    def settimeout(self, timeout: float) -> bool:
        """Set the socket timeout for blocking operations.

        Args:
            timeout: Timeout in seconds, or ``None`` for non-blocking mode.

        Returns:
            True if the timeout was set successfully, False otherwise.
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
            True if disconnection succeeded, False otherwise.
        """
        ...

    @abstractmethod
    def recv(self, buf_size: int) -> bytes:
        """Receive data from the connection.

        Args:
            buf_size: Maximum number of bytes to receive.

        Returns:
            The received bytes, or an empty byte-string on failure.
        """
        ...
