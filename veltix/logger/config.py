"""Logger configuration for Veltix."""

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
        level: Minimum log level to display (default: INFO)
        enabled: Enable/disable all logging (default: True)
        use_colors: Enable colored output for console (default: True)
        show_timestamp: Show timestamp in logs (default: True)
        show_caller: Show file:line information (default: True)
        show_level: Show log level name (default: True)

        # File output
        file_path: Path to log file (default: None = no file logging)
        file_rotation_size: Max file size in bytes before rotation (default: 10MB)
        file_backup_count: Number of backup files to keep (default: 5)

        # Advanced
        stream: Output stream for console logs (default: stdout)
        async_write: Use async file writing for performance (default: False)
        buffer_size: Buffer size for async writes (default: 100)
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
