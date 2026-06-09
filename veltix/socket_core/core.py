"""Socket core selection for Veltix."""

from enum import Enum

from .async_socket import AsyncSocket
from .threading_socket import ThreadingSocket


class SocketCore(Enum):
    """Available socket implementations."""

    THREADING = ThreadingSocket
    ASYNC = AsyncSocket
    # RUST = RustSocket     # planned: v3.0.0
