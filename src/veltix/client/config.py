from __future__ import annotations

import dataclasses

from ..internal.buffer_size import BufferSize
from ..socket_core.core import SocketCore


@dataclasses.dataclass(slots=True)
class ClientConfig:
    """
    TCP client configuration.

    Attributes:
        server_addr:       Server address to connect to.
        port:              Server port to connect to.
        buffer_size:       Buffer size for receiving data in bytes.
                           Use BufferSize enum for common presets (default: BufferSize.MEDIUM).
                           Can also be set to any custom integer value.
        max_message_size:  Maximum allowed message size in bytes (default: 10MB).
        handshake_timeout: Maximum time to wait for handshake completion (default: 5.0s).
        max_workers:       Number of worker threads for callback execution (default: 4).
                           Increase if your on_recv callback is slow or blocking.
        retry:             Number of reconnection attempts on failure (default: 0 = disabled).
                           Applies both to the initial connect() and to mid-session disconnections.
        retry_delay:       Seconds to wait between reconnection attempts (default: 1.0).
        socket_core:       Socket implementation to use (default: ASYNC).
                            Switch between THREADING and ASYNC without changing
                            any other code.
    """

    server_addr: str = "127.0.0.1"
    port: int = 8080
    buffer_size: int = BufferSize.MEDIUM
    max_message_size: int = 10 * 1024 * 1024  # 10 MB
    handshake_timeout: float = 5.0
    max_workers: int = 4
    retry: int = 0
    retry_delay: float = 1.0
    socket_core: SocketCore = SocketCore.ASYNC

    def __post_init__(self) -> None:
        if not 0 <= self.port <= 65535:
            raise ValueError(f"port ({self.port}) must be between 0 and 65535")
        if self.buffer_size <= 0:
            raise ValueError(f"buffer_size ({self.buffer_size}) must be positive")
        if self.max_message_size <= 0:
            raise ValueError(f"max_message_size ({self.max_message_size}) must be positive")
        if self.handshake_timeout <= 0:
            raise ValueError(f"handshake_timeout ({self.handshake_timeout}) must be positive")
        if self.max_workers < 1:
            raise ValueError(f"max_workers ({self.max_workers}) must be at least 1")
        if self.retry < 0:
            raise ValueError(f"retry ({self.retry}) must be zero or positive")
        if self.retry_delay <= 0:
            raise ValueError(f"retry_delay ({self.retry_delay}) must be positive")
