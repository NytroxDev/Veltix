"""Log message formatting."""

from __future__ import annotations

import logging

from .levels import LogLevel


class VeltixFormatter(logging.Formatter):
    """Custom formatter: [HH:MM:SS.mmm] LEVEL  message + optional colors."""

    COLORS = {
        LogLevel.TRACE: "\033[90m",
        LogLevel.DEBUG: "\033[37m",
        LogLevel.INFO: "\033[36m",
        LogLevel.SUCCESS: "\033[32m",
        LogLevel.WARNING: "\033[33m",
        LogLevel.ERROR: "\033[31m",
        LogLevel.CRITICAL: "\033[41m",
    }

    LEVEL_NAMES = {
        LogLevel.TRACE: "TRACE",
        LogLevel.DEBUG: "DEBUG",
        LogLevel.INFO: "INFO ",
        LogLevel.SUCCESS: "OK   ",
        LogLevel.WARNING: "WARN ",
        LogLevel.ERROR: "ERROR",
        LogLevel.CRITICAL: "CRIT ",
    }

    RESET = "\033[0m"

    def __init__(
        self, use_colors: bool = True, show_timestamp: bool = True, show_level: bool = True
    ) -> None:
        super().__init__()
        self.use_colors = use_colors
        self.show_timestamp = show_timestamp
        self.show_level = show_level

    def format(self, record: logging.LogRecord) -> str:
        parts = []

        if self.show_timestamp:
            ts = self.formatTime(record, "%H:%M:%S") + f".{record.msecs:03.0f}"[-3:]
            parts.append(f"[{ts}]")

        if self.show_level:
            level = self._get_level(record)
            parts.append(self.LEVEL_NAMES.get(level, record.levelname))

        parts.append(record.getMessage())

        result = " ".join(parts)

        if self.use_colors and self.show_level:
            color = self.COLORS.get(level, "")
            if color:
                result = f"{color}{result}{self.RESET}"

        return result

    @staticmethod
    def _get_level(record: logging.LogRecord) -> LogLevel:
        """Map a logging record to a LogLevel."""
        for level in LogLevel:
            if level.value == record.levelno:
                return level
        return LogLevel.INFO
