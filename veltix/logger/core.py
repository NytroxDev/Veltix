"""Core logger implementation."""

import inspect
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from veltix.logger.config import LoggerConfig
from veltix.logger.formatter import Formatter

from .levels import LogLevel
from .writer import Writer


class Logger:
    """
    Veltix logger with simple, powerful API.

    Thread-safe logger with console and file output support.
    Can be passed to Client/Server or used standalone.

    This is a singleton - only one instance can exist.
    """

    _instance: Optional["Logger"] = None
    _lock = threading.Lock()

    def __new__(cls, config: Optional[LoggerConfig] = None) -> "Logger":
        """
        Create or return the singleton instance.

        Args:
            config: Logger configuration (only used on first creation)

        Returns:
            The singleton Logger instance
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Optional[LoggerConfig] = None):
        """
        Initialize logger (only on first creation).

        Args:
            config: Logger configuration (uses defaults if None, only used on first creation)
        """
        if self._initialized:
            return

        self.config = config or LoggerConfig()
        self._lock = threading.RLock()

        # Components
        self._formatter = Formatter(use_colors=self.config.use_colors)
        self._writer = Writer(self.config)

        # Statistics
        self._stats = dict.fromkeys(LogLevel, 0)
        self._initialized = True

    @classmethod
    def get_instance(cls, config: Optional[LoggerConfig] = None) -> "Logger":
        """
        Get the singleton instance.

        Args:
            config: Logger configuration (only used on first creation)

        Returns:
            The singleton Logger instance
        """
        return cls(config)

    @classmethod
    def reset_instance(cls) -> None:
        """
        Reset the singleton instance (mainly for testing).
        """
        with cls._lock:
            cls._instance = None

    def _log(self, level: LogLevel, message: str) -> None:
        """
        Internal logging method.

        Args:
            level: Log level
            message: Message to log
        """
        # Check if enabled and level
        if not self.config.enabled or level < self.config.level:
            return

        # Get caller info
        caller = None
        if self.config.show_caller:
            caller = self._get_caller_info()

        # Get timestamp
        timestamp = None
        if self.config.show_timestamp:
            timestamp = datetime.now()

        # Format message
        formatted = self._formatter.format(
            level=level,
            message=message,
            caller=caller,
            timestamp=timestamp,
            show_timestamp=self.config.show_timestamp,
            show_caller=self.config.show_caller,
            show_level=self.config.show_level,
        )

        # Write message
        with self._lock:
            self._writer.write(formatted)
            self._stats[level] += 1

    @staticmethod
    def _get_caller_info() -> Optional[str]:
        """Get caller file and line number."""
        try:
            # Walk up stack to find first frame outside logger module
            frame = inspect.currentframe()
            if frame is None:
                return None

            # Skip logger frames
            while frame:
                filename = frame.f_code.co_filename
                # Skip logger module frames
                if "logger" not in filename.lower():
                    break
                frame = frame.f_back

            if frame:
                filename = Path(frame.f_code.co_filename).name
                lineno = frame.f_lineno
                return f"{filename}:{lineno}"

        except Exception:
            pass

        return None

    # === Public API ===

    def trace(self, message: str) -> None:
        """Log TRACE level message."""
        self._log(LogLevel.TRACE, message)

    def debug(self, message: str) -> None:
        """Log DEBUG level message."""
        self._log(LogLevel.DEBUG, message)

    def info(self, message: str) -> None:
        """Log INFO level message."""
        self._log(LogLevel.INFO, message)

    def success(self, message: str) -> None:
        """Log SUCCESS level message."""
        self._log(LogLevel.SUCCESS, message)

    def warning(self, message: str) -> None:
        """Log WARNING level message."""
        self._log(LogLevel.WARNING, message)

    def error(self, message: str) -> None:
        """Log ERROR level message."""
        self._log(LogLevel.ERROR, message)

    def critical(self, message: str) -> None:
        """Log CRITICAL level message."""
        self._log(LogLevel.CRITICAL, message)

    # === Configuration ===

    def set_level(self, level: LogLevel) -> None:
        """
        Change log level.

        Args:
            level: New minimum log level
        """
        self.config.level = level

    def enable(self) -> None:
        """Enable logging."""
        self.config.enabled = True

    def disable(self) -> None:
        """Disable all logging."""
        self.config.enabled = False

    def get_stats(self) -> dict[LogLevel, int]:
        """
        Get logging statistics.

        Returns:
            Dictionary mapping log levels to message counts
        """
        with self._lock:
            return self._stats.copy()
