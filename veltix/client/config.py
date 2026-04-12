# ============================================================================
# CONFIGURATION
# ============================================================================
import dataclasses

from ..internal.buffer_size import BufferSize
from ..internal.performance_mode import PerformanceMode
from ..socket.core import SocketCore


@dataclasses.dataclass
class ClientConfig:
    """
    TCP client configuration.

    Attributes:
        server_addr:       Server address to connect to.
        port:              Server port to connect to.
        buffer_size:       Buffer size for receiving data in bytes.
                           Use BufferSize enum for common presets (default: BufferSize.SMALL).
                           Can also be set to any custom integer value.
        max_message_size:  Maximum allowed message size in bytes (default: 10MB).
        handshake_timeout: Maximum time to wait for handshake completion (default: 5.0s).
        max_workers:       Number of worker threads for callback execution (default: 4).
                           Increase if your on_recv callback is slow or blocking.
        retry:             Number of reconnection attempts on failure (default: 0 = disabled).
                           Applies both to the initial connect() and to mid-session disconnections.
        retry_delay:       Seconds to wait between reconnection attempts (default: 1.0).
        performance_mode:  Controls internal timing parameters (default: BALANCED).
    """

    server_addr: str = "127.0.0.1"
    port: int = 8080
    buffer_size: int = BufferSize.SMALL
    max_message_size: int = 10 * 1024 * 1024  # 10 MB
    handshake_timeout: float = 5.0
    max_workers: int = 4
    retry: int = 0
    retry_delay: float = 1.0
    performance_mode: PerformanceMode = PerformanceMode.BALANCED
    socket_core: SocketCore = SocketCore.THREADING
