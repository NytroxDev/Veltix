"""Per-connection socket returned by the accept loops."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base_socket import BaseSocket

if TYPE_CHECKING:
    import socket

    from ..internal.bus import VeltixBus


class AcceptedSocket(BaseSocket):
    """One connection accepted by a backend, as seen by the server layer.

    A backend plays three roles at once: the listener, the client peer, and
    every connection it accepts. Only the first two need a lifecycle, so an
    accepted connection gets this leaf instead of a full backend: it carries
    the raw socket, the bus and the outbound queue, and nothing else. The
    owning backend keeps doing the reading and the teardown bookkeeping.

    Attributes:
        handshake_timeout: Timeout in seconds for the handshake phase.
        bus: Event bus for structured observability.
    """

    def __init__(
        self,
        sock: socket.socket,
        bus: VeltixBus,
        handshake_timeout: float = 5.0,
    ) -> None:
        """Wrap an accepted raw socket.

        Args:
            sock: The raw socket returned by ``accept()``.
            bus: Event bus for structured observability.
            handshake_timeout: Timeout in seconds for the handshake phase.
        """
        self._sock = sock
        self.bus = bus
        self.handshake_timeout = handshake_timeout

    def close(self) -> bool:
        """Shut the connection down and close it.

        Called by the owning backend when tearing the client down. Unlike a
        backend's own close, this never touches the registry, the selector
        or any sibling connection.

        Returns:
            True if the socket was closed successfully, False otherwise.
        """
        self._shutdown_socket()
        try:
            self._sock.close()
            return True
        except OSError:
            return False
