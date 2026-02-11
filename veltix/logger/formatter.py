"""Log message formatting."""

from datetime import datetime
from typing import Optional

from .levels import LogLevel


class Formatter:
    """Handles log message formatting."""

    # ANSI color codes
    COLORS = {
        LogLevel.TRACE: "\033[90m",  # Gray
        LogLevel.DEBUG: "\033[37m",  # White
        LogLevel.INFO: "\033[36m",  # Cyan
        LogLevel.SUCCESS: "\033[32m",  # Green
        LogLevel.WARNING: "\033[33m",  # Yellow
        LogLevel.ERROR: "\033[31m",  # Red
        LogLevel.CRITICAL: "\033[41m",  # Red background
    }

    RESET = "\033[0m"

    def __init__(self, use_colors: bool = True):
        """
        Initialize formatter.

        Args:
            use_colors: Enable ANSI color codes
        """
        self.use_colors = use_colors

    def format(
        self,
        level: LogLevel,
        message: str,
        caller: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        show_timestamp: bool = True,
        show_caller: bool = True,
        show_level: bool = True,
    ) -> str:
        """
        Format a log message.

        Args:
            level: Log level
            message: Message to format
            caller: Caller information (file:line)
            timestamp: Message timestamp
            show_timestamp: Include timestamp
            show_caller: Include caller info
            show_level: Include level name

        Returns:
            Formatted message string
        """
        parts = []

        # Timestamp
        if show_timestamp and timestamp:
            time_str = timestamp.strftime("%H:%M:%S.%f")[:-3]  # Milliseconds
            parts.append(f"[{time_str}]")

        # Level
        if show_level:
            level_str = self._format_level(level)
            parts.append(level_str)

        # Caller
        if show_caller and caller:
            parts.append(f"[{caller}]")

        # Message
        parts.append(message)

        result = " ".join(parts)

        # Apply colors
        if self.use_colors:
            color = self.COLORS.get(level, "")
            result = f"{color}{result}{self.RESET}"

        return result

    @staticmethod
    def _format_level(level: LogLevel) -> str:
        """Format level name with consistent width."""
        level_names = {
            LogLevel.TRACE: "TRACE",
            LogLevel.DEBUG: "DEBUG",
            LogLevel.INFO: "INFO ",
            LogLevel.SUCCESS: "OK   ",
            LogLevel.WARNING: "WARN ",
            LogLevel.ERROR: "ERROR",
            LogLevel.CRITICAL: "CRIT ",
        }
        return level_names.get(level, str(level))
