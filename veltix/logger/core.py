"""Core logger implementation."""

from __future__ import annotations

import inspect
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import LoggerConfig
from .formatter import Formatter
from .levels import LogLevel
from .writer import Writer


class Logger:
    """
    Thread-safe singleton logger with console and file output.

    Can be passed to Client/Server or used standalone.
    """

    _instance: Optional[Logger] = None
    _lock = threading.Lock()

    def __new__(cls, config: Optional[LoggerConfig] = None) -> Logger:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Optional[LoggerConfig] = None) -> None:
        if self._initialized:
            return

        self.config = config or LoggerConfig()
        self._lock = threading.RLock()
        self._formatter = Formatter(use_colors=self.config.use_colors)
        self._writer = Writer(self.config)
        self._stats: dict[LogLevel, int] = dict.fromkeys(LogLevel, 0)
        self._initialized = True

    @classmethod
    def get_instance(cls, config: Optional[LoggerConfig] = None) -> Logger:
        """Get or create the singleton instance."""
        return cls(config)

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (mainly for testing)."""
        with cls._lock:
            cls._instance = None

    def _log(self, level: LogLevel, message: str) -> None:
        with self._lock:
            if not self.config.enabled or level < self.config.level:
                return

            caller = self._get_caller_info() if self.config.show_caller else None
            timestamp = datetime.now() if self.config.show_timestamp else None

            formatted = self._formatter.format(
                level=level,
                message=message,
                caller=caller,
                timestamp=timestamp,
                show_timestamp=self.config.show_timestamp,
                show_caller=self.config.show_caller,
                show_level=self.config.show_level,
            )

            self._writer.write(formatted)
            self._stats[level] += 1

    @staticmethod
    def _get_caller_info() -> Optional[str]:
        try:
            frame = inspect.currentframe()
            while frame:
                if "logger" not in frame.f_code.co_filename.lower():
                    break
                frame = frame.f_back

            if frame:
                return f"{Path(frame.f_code.co_filename).name}:{frame.f_lineno}"
        except Exception:
            pass
        return None

    def trace(self, message: str) -> None:
        self._log(LogLevel.TRACE, message)

    def debug(self, message: str) -> None:
        self._log(LogLevel.DEBUG, message)

    def info(self, message: str) -> None:
        self._log(LogLevel.INFO, message)

    def success(self, message: str) -> None:
        self._log(LogLevel.SUCCESS, message)

    def warning(self, message: str) -> None:
        self._log(LogLevel.WARNING, message)

    def error(self, message: str) -> None:
        self._log(LogLevel.ERROR, message)

    def critical(self, message: str) -> None:
        self._log(LogLevel.CRITICAL, message)

    def set_level(self, level: LogLevel) -> None:
        with self._lock:
            self.config.level = level

    def enable(self) -> None:
        with self._lock:
            self.config.enabled = True

    def disable(self) -> None:
        with self._lock:
            self.config.enabled = False

    def get_stats(self) -> dict[LogLevel, int]:
        with self._lock:
            return self._stats.copy()
