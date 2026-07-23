"""Core logger implementation."""

from __future__ import annotations

import logging
import threading
from typing import Optional

from .config import LoggerConfig
from .formatter import VeltixFormatter
from .levels import LogLevel


class Logger:
    """Thread-safe singleton logger backed by stdlib logging.

    The logger is implemented as a singleton: calling ``Logger()`` or
    ``Logger.get_instance()`` always returns the same object.

    Typical usage::

        from veltix import Logger

        logger = Logger.get_instance()
        logger.info("Server started")
    """

    _instance: Optional[Logger] = None
    _initialized: bool = False
    _lock = threading.RLock()

    def __new__(cls, config: Optional[LoggerConfig] = None) -> Logger:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Optional[LoggerConfig] = None) -> None:
        if not self._initialized:
            self._initialized = True
            self._stats = dict.fromkeys(LogLevel, 0)
            self._internal = logging.getLogger("veltix")
            self._internal.propagate = False
            self._handler: Optional[logging.StreamHandler] = None
            self._setup(config or LoggerConfig())
        elif config is not None:
            self._setup(config)

    def _setup(self, config: LoggerConfig) -> None:
        """Configure the internal logging.Logger with handlers and formatters."""
        self.config = config
        self._stats = dict.fromkeys(LogLevel, 0)

        # Remove old handler
        if self._handler is not None:
            self._internal.removeHandler(self._handler)

        if not config.enabled:
            self._internal.setLevel(logging.CRITICAL + 10)
            return

        self._internal.setLevel(self._to_logging_level(config.level))

        self._handler = logging.StreamHandler(config.stream)
        self._handler.setFormatter(VeltixFormatter(use_colors=config.use_colors))
        self._internal.addHandler(self._handler)

    @classmethod
    def get_instance(cls, config: Optional[LoggerConfig] = None) -> Logger:
        """Get or create the singleton instance."""
        return cls(config)

    def configure(self, config: LoggerConfig) -> None:
        """Reconfigure the logger with a new config."""
        with self._lock:
            self._setup(config)

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (mainly for testing)."""
        with cls._lock:
            if cls._instance is not None and cls._instance._handler is not None:
                cls._instance._internal.removeHandler(cls._instance._handler)
            cls._instance = None

    # ── Log methods ───────────────────────────────────────────────────────────

    def trace(self, message: str) -> None:
        """Log a TRACE-level message (severity 5).

        Args:
            message: The log message.
        """
        self._log(LogLevel.TRACE, message)

    def debug(self, message: str) -> None:
        """Log a DEBUG-level message (severity 10).

        Args:
            message: The log message.
        """
        self._log(LogLevel.DEBUG, message)

    def info(self, message: str) -> None:
        """Log an INFO-level message (severity 20).

        Args:
            message: The log message.
        """
        self._log(LogLevel.INFO, message)

    def success(self, message: str) -> None:
        """Log a SUCCESS-level message (severity 25).

        Args:
            message: The log message.
        """
        self._log(LogLevel.SUCCESS, message)

    def warning(self, message: str) -> None:
        """Log a WARNING-level message (severity 30).

        Args:
            message: The log message.
        """
        self._log(LogLevel.WARNING, message)

    def error(self, message: str) -> None:
        """Log an ERROR-level message (severity 40).

        Args:
            message: The log message.
        """
        self._log(LogLevel.ERROR, message)

    def critical(self, message: str) -> None:
        """Log a CRITICAL-level message (severity 50).

        Args:
            message: The log message.
        """
        self._log(LogLevel.CRITICAL, message)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _log(self, level: LogLevel, message: str) -> None:
        if not self.config.enabled or level < self.config.level:
            return

        self._stats[level] += 1
        logging_level = self._to_logging_level(level)
        self._internal.log(logging_level, message)

    def set_level(self, level: LogLevel) -> None:
        """Change the minimum log level at runtime.

        Args:
            level: The new minimum :class:`LogLevel`.
        """
        with self._lock:
            self.config.level = level
            if self._handler is not None:
                self._internal.setLevel(self._to_logging_level(level))

    def enable(self) -> None:
        """Enable log output."""
        with self._lock:
            self.config.enabled = True
            self._internal.setLevel(self._to_logging_level(self.config.level))

    def disable(self) -> None:
        """Disable all log output."""
        with self._lock:
            self.config.enabled = False
            self._internal.setLevel(logging.CRITICAL + 10)

    def get_stats(self) -> dict[LogLevel, int]:
        """Return per-level message counts since the last reset.

        Returns:
            A dictionary mapping each :class:`LogLevel` to the number of
            messages logged at that level.
        """
        with self._lock:
            return self._stats.copy()

    @staticmethod
    def _to_logging_level(level: LogLevel) -> int:
        """Map a LogLevel to a stdlib logging level.

        Custom levels (TRACE=5, SUCCESS=25) are mapped to the nearest
        standard level for the internal logger.
        """
        if level <= LogLevel.DEBUG:
            return logging.DEBUG
        if level <= LogLevel.INFO:
            return logging.INFO
        if level <= LogLevel.WARNING:
            return logging.WARNING
        if level <= LogLevel.ERROR:
            return logging.ERROR
        return logging.CRITICAL
