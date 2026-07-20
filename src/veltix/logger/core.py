"""Core logger implementation."""

from __future__ import annotations

import inspect
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import LoggerConfig
from .formatter import Formatter
from .levels import LogLevel
from .writer import Writer

_VELTIX_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + os.sep


class Logger:
    """Thread-safe singleton logger with console and file output.

    The logger is implemented as a singleton: calling ``Logger()`` or
    ``Logger.get_instance()`` always returns the same object. It supports
    configurable log levels, optional file rotation, caller detection, and
    per-level usage statistics.

    Typical usage::

        from veltix import Logger

        logger = Logger.get_instance()
        logger.info("Server started")
    """

    _instance: Optional[Logger] = None
    _initialized: bool = False
    _lock = threading.RLock()

    def __new__(cls, config: Optional[LoggerConfig] = None) -> Logger:
        """Create or retrieve the singleton Logger instance.

        Args:
            config: Optional configuration. On the first call it sets up the
                logger; on subsequent calls it can be used to reconfigure it.

        Returns:
            The singleton :class:`Logger` instance.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Optional[LoggerConfig] = None) -> None:
        """Initialise the singleton on first call; reconfigure on later calls with a config.

        Args:
            config: Optional configuration to apply. Ignored on the first call
                when *config* was already provided to ``__new__``.
        """
        if not self._initialized:
            self._initialized = True
        elif config is not None:
            self._lock.acquire()
            try:
                self.config = config
                self._formatter = Formatter(use_colors=self.config.use_colors)
                self._writer = Writer(self.config)
                self._stats = dict.fromkeys(LogLevel, 0)
            finally:
                self._lock.release()
            return
        else:
            return

        self.config = config or LoggerConfig()
        self._formatter = Formatter(use_colors=self.config.use_colors)
        self._writer = Writer(self.config)
        self._stats = dict.fromkeys(LogLevel, 0)

    @classmethod
    def get_instance(cls, config: Optional[LoggerConfig] = None) -> Logger:
        """Get or create the singleton instance."""
        return cls(config)

    def configure(self, config: LoggerConfig) -> None:
        """Reconfigure the logger with a new config (writer, formatter, stats reset)."""
        with self._lock:
            self.config = config
            self._formatter = Formatter(use_colors=self.config.use_colors)
            self._writer = Writer(self.config)
            self._stats = dict.fromkeys(LogLevel, 0)

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (mainly for testing)."""
        with cls._lock:
            cls._instance = None

    def _log(self, level: LogLevel, message: str, caller: Optional[str] = None) -> None:
        with self._lock:
            if not self.config.enabled or level < self.config.level:
                return

            if caller is None and self.config.show_caller:
                caller = self._get_caller_info()
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
                filename = os.path.abspath(frame.f_code.co_filename)
                if not filename.startswith(_VELTIX_ROOT):
                    return f"{Path(frame.f_code.co_filename).name}:{frame.f_lineno}"
                frame = frame.f_back
        except Exception:
            pass
        return None

    def trace(self, message: str, caller: Optional[str] = None) -> None:
        """Log a TRACE-level message (severity 5).

        Args:
            message: The log message.
            caller: Optional explicit caller override (``"file.py:42"``).
        """
        self._log(LogLevel.TRACE, message, caller=caller)

    def debug(self, message: str, caller: Optional[str] = None) -> None:
        """Log a DEBUG-level message (severity 10).

        Args:
            message: The log message.
            caller: Optional explicit caller override.
        """
        self._log(LogLevel.DEBUG, message, caller=caller)

    def info(self, message: str, caller: Optional[str] = None) -> None:
        """Log an INFO-level message (severity 20).

        Args:
            message: The log message.
            caller: Optional explicit caller override.
        """
        self._log(LogLevel.INFO, message, caller=caller)

    def success(self, message: str, caller: Optional[str] = None) -> None:
        """Log a SUCCESS-level message (severity 25).

        Args:
            message: The log message.
            caller: Optional explicit caller override.
        """
        self._log(LogLevel.SUCCESS, message, caller=caller)

    def warning(self, message: str, caller: Optional[str] = None) -> None:
        """Log a WARNING-level message (severity 30).

        Args:
            message: The log message.
            caller: Optional explicit caller override.
        """
        self._log(LogLevel.WARNING, message, caller=caller)

    def error(self, message: str, caller: Optional[str] = None) -> None:
        """Log an ERROR-level message (severity 40).

        Args:
            message: The log message.
            caller: Optional explicit caller override.
        """
        self._log(LogLevel.ERROR, message, caller=caller)

    def critical(self, message: str, caller: Optional[str] = None) -> None:
        """Log a CRITICAL-level message (severity 50).

        Args:
            message: The log message.
            caller: Optional explicit caller override.
        """
        self._log(LogLevel.CRITICAL, message, caller=caller)

    def set_level(self, level: LogLevel) -> None:
        """Change the minimum log level at runtime.

        Messages below this level are silently discarded.

        Args:
            level: The new minimum :class:`LogLevel`.
        """
        with self._lock:
            self.config.level = level

    def enable(self) -> None:
        """Enable log output."""
        with self._lock:
            self.config.enabled = True

    def disable(self) -> None:
        """Disable all log output."""
        with self._lock:
            self.config.enabled = False

    def get_stats(self) -> dict[LogLevel, int]:
        """Return per-level message counts since the last reset.

        Returns:
            A dictionary mapping each :class:`LogLevel` to the number of
            messages logged at that level.
        """
        with self._lock:
            return self._stats.copy()
