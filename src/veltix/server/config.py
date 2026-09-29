from __future__ import annotations

import dataclasses

from ..internal.buffer_size import BufferSize
from ..socket_core.core import SocketCore


@dataclasses.dataclass
class ServerConfig:
    """
    TCP server configuration.

    Attributes:
        host:              Server listening address (default: '0.0.0.0').
        port:              Server listening port (default: 8080).
        buffer_size:       Buffer size for receiving data in bytes.
                           Use BufferSize enum for common presets (default: BufferSize.MEDIUM).
                           Can also be set to any custom integer value.
        max_connection:    Maximum number of simultaneous connections (default: -1 = unlimited).
        max_message_size:  Maximum allowed message size in bytes (default: 10MB).
        handshake_timeout: Maximum time to wait for handshake completion in seconds (default: 5.0).
        max_workers:       Number of worker threads for callback execution (default: 4).
                           Increase if your on_recv callback is slow or blocking.
        socket_core:       Socket implementation to use (default: ASYNC).
                            Switch to THREADING or RUST (v3.0.0) without changing
                            any other code.
        id_window:         Number of unique request IDs per direction in the protocol (default: 30000).
                            Must fit in REQUEST_ID_SIZE bytes (max 65535).
    """

    host: str = "0.0.0.0"
    port: int = 8080
    buffer_size: int = BufferSize.MEDIUM
    max_connection: int = -1
    max_message_size: int = 10 * 1024 * 1024  # 10 MB
    handshake_timeout: float = 5.0
    max_workers: int = 4
    socket_core: SocketCore = SocketCore.ASYNC
    id_window: int = 30000

    def __post_init__(self) -> None:
        if not 0 <= self.port <= 65535:
            raise ValueError(f"port ({self.port}) must be between 0 and 65535")
        if self.buffer_size <= 0:
            raise ValueError(f"buffer_size ({self.buffer_size}) must be positive")
        if self.max_connection != -1 and self.max_connection < 1:
            raise ValueError(
                f"max_connection ({self.max_connection}) must be -1 (unlimited) or a "
                "positive integer"
            )
        if self.max_message_size <= 0:
            raise ValueError(f"max_message_size ({self.max_message_size}) must be positive")
        if self.handshake_timeout <= 0:
            raise ValueError(f"handshake_timeout ({self.handshake_timeout}) must be positive")
        if self.max_workers < 1:
            raise ValueError(f"max_workers ({self.max_workers}) must be at least 1")
        if not 1 <= self.id_window <= 65535:
            raise ValueError(f"id_window ({self.id_window}) must be between 1 and 65535")
