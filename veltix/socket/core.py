"""Socket core selection for Veltix."""

from enum import Enum

from .threading_socket import ThreadingSocket


class SocketCore(Enum):
    """
    Available socket implementations.

    Attributes:
        THREADING: Standard threading-based socket (default).
                   One thread per connected client.
        ASYNC:     Asyncio-based socket (v1.7.0).
                   Single event loop for all connections.
        RUST:      Rust core via PyO3 (v3.0.0).
                   Maximum throughput with native Tokio runtime.
    """

    THREADING = ThreadingSocket
    # ASYNC = AsyncSocket      # v1.7.0
    # RUST = RustSocket        # v3.0.0
