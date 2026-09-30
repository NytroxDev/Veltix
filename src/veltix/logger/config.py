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
        show_level: Show log level name
        show_caller: Show caller file and line number (e.g. server.py:42)
        file_path: Path to log file
        file_rotation_size: Max file size in bytes before rotation
        file_backup_count: Number of backup files to keep
        stream: Output stream for console logs
    """

    # Basic settings
    level: LogLevel = LogLevel.INFO
    enabled: bool = True
    use_colors: bool = True
    show_timestamp: bool = True
    show_level: bool = True
    show_caller: bool = True

    # File logging
    file_path: str | Path | None = None
    file_rotation_size: int = 10 * 1024 * 1024  # 10 MB
    file_backup_count: int = 5

    # Advanced
    stream: TextIO = dataclasses.field(default=sys.stdout)

    def __post_init__(self) -> None:
        """Validate and normalize configuration."""
        if not isinstance(self.level, LogLevel):
            members = ", ".join(level.name for level in LogLevel)
            raise TypeError(f"level must be a LogLevel member ({members}), got {self.level!r}")
        if isinstance(self.file_path, (str, Path)):
            if not self.file_path:
                raise ValueError("file_path must not be empty")
            self.file_path = Path(self.file_path)
        elif self.file_path is not None:
            raise TypeError(f"file_path must be a str or Path, got {type(self.file_path).__name__}")
        if not hasattr(self.stream, "write"):
            raise TypeError(
                f"stream must be writable (have a write() method), got {type(self.stream).__name__}"
            )
        if self.file_rotation_size <= 0:
            raise ValueError(f"file_rotation_size must be positive, got {self.file_rotation_size}")
        if self.file_backup_count <= 0:
            raise ValueError(f"file_backup_count must be positive, got {self.file_backup_count}")
