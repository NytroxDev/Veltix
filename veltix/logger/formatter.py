"""Log message formatting."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .levels import LogLevel

if TYPE_CHECKING:
    from datetime import datetime


class Formatter:
    """Handles log message formatting."""

    COLORS = {
        LogLevel.TRACE: "\033[90m",
        LogLevel.DEBUG: "\033[37m",
        LogLevel.INFO: "\033[36m",
        LogLevel.SUCCESS: "\033[32m",
        LogLevel.WARNING: "\033[33m",
        LogLevel.ERROR: "\033[31m",
        LogLevel.CRITICAL: "\033[41m",
    }

    RESET = "\033[0m"

    def __init__(self, use_colors: bool = True) -> None:
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
        parts = []

        if show_timestamp and timestamp:
            parts.append(f"[{timestamp.strftime('%H:%M:%S.%f')[:-3]}]")

        if show_level:
            parts.append(self._format_level(level))

        if show_caller and caller:
            parts.append(f"[{caller}]")

        parts.append(message)

        result = " ".join(parts)

        if self.use_colors:
            color = self.COLORS.get(level, "")
            result = f"{color}{result}{self.RESET}"

        return result

    @staticmethod
    def _format_level(level: LogLevel) -> str:
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
