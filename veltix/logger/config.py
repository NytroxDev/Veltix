"""Logger configuration for Veltix."""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from typing import TextIO

from .levels import LogLevel


@dataclasses.dataclass
class LoggerConfig:
    """
    Configuration for Veltix logger.

    Attributes:
        level: Minimum log level to display
        enabled: Enable/disable all logging
        use_colors: Enable colored output for console
        show_timestamp: Show timestamp in logs
        show_caller: Show file:line information
        show_level: Show log level name

        # File output
        file_path: Path to log file
        file_rotation_size: Max file size in bytes before rotation
        file_backup_count: Number of backup files to keep

        # Advanced
        stream: Output stream for console logs
        async_write: Use async file writing for performance
        buffer_size: Buffer size for async writes
    """

    # Basic settings
    level: LogLevel = LogLevel.INFO
    enabled: bool = True
    use_colors: bool = True
    show_timestamp: bool = True
    show_caller: bool = True
    show_level: bool = True

    # File logging
    file_path: str | Path | None = None
    file_rotation_size: int = 10 * 1024 * 1024  # 10 MB
    file_backup_count: int = 5

    # Advanced
    stream: TextIO = dataclasses.field(default=sys.stdout)
    async_write: bool = False
    buffer_size: int = 100

    def __post_init__(self):
        """Validate and normalize configuration."""
        if self.file_path:
            self.file_path = Path(self.file_path)
