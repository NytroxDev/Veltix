import dataclasses

from ..internal.buffer_size import BufferSize
from ..internal.performance_mode import PerformanceMode
from ..socket_core.core import SocketCore


@dataclasses.dataclass
class ServerConfig:
    """
    TCP server configuration.

    Attributes:
        host:              Server listening address (default: '0.0.0.0').
        port:              Server listening port (default: 8080).
        buffer_size:       Buffer size for receiving data in bytes.
                           Use BufferSize enum for common presets (default: BufferSize.SMALL).
                           Can also be set to any custom integer value.
        max_connection:    Maximum number of simultaneous connections (default: -1 = unlimited).
        max_message_size:  Maximum allowed message size in bytes (default: 10MB).
        handshake_timeout: Maximum time to wait for handshake completion in seconds (default: 5.0).
        max_workers:       Number of worker threads for callback execution (default: 4).
                           Increase if your on_recv callback is slow or blocking.
        performance_mode:  Controls internal timing parameters (default: BALANCED).
        socket_core:       Socket implementation to use (default: THREADING).
                           Switch to ASYNC (v1.7.0) or RUST (v3.0.0) without changing
                           any other code.
    """

    host: str = "0.0.0.0"
    port: int = 8080
    buffer_size: int = BufferSize.SMALL
    max_connection: int = -1
    max_message_size: int = 10 * 1024 * 1024  # 10 MB
    handshake_timeout: float = 5.0
    max_workers: int = 4
    performance_mode: PerformanceMode = PerformanceMode.BALANCED
    socket_core: SocketCore = SocketCore.THREADING
