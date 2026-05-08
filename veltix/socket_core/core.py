"""Socket core selection for Veltix."""

from enum import Enum

from .threading_socket import ThreadingSocket


class SocketCore(Enum):
    """Available socket implementations."""

    THREADING = ThreadingSocket
    # ASYNC = AsyncSocket   # planned: v1.7.0
    # RUST = RustSocket     # planned: v3.0.0
