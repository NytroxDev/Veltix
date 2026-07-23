"""Core logger implementation."""

from __future__ import annotations

import logging
import logging.handlers
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
            self._console_handler: Optional[logging.StreamHandler] = None
            self._file_handler: Optional[logging.handlers.RotatingFileHandler] = None
            self._setup(config or LoggerConfig())
        elif config is not None:
            self._setup(config)

    def _setup(self, config: LoggerConfig) -> None:
        """Configure the internal logging.Logger with handlers and formatters."""
        self.config = config
        self._stats = dict.fromkeys(LogLevel, 0)

        # Remove old handlers
        if self._console_handler is not None:
            self._internal.removeHandler(self._console_handler)
            self._console_handler = None
        if self._file_handler is not None:
            self._internal.removeHandler(self._file_handler)
            self._file_handler.close()
            self._file_handler = None

        if not config.enabled:
            self._internal.setLevel(logging.CRITICAL + 10)
            return

        self._internal.setLevel(int(config.level))

        # Console handler
        self._console_handler = logging.StreamHandler(config.stream)
        self._console_handler.setFormatter(
            VeltixFormatter(
                use_colors=config.use_colors,
                show_timestamp=config.show_timestamp,
                show_level=config.show_level,
            )
        )
        self._internal.addHandler(self._console_handler)

        # File handler
        if config.file_path is not None:
            self._file_handler = logging.handlers.RotatingFileHandler(
                config.file_path,
                maxBytes=config.file_rotation_size,
                backupCount=config.file_backup_count,
                encoding="utf-8",
            )
            self._file_handler.setFormatter(VeltixFormatter(use_colors=False))
            self._internal.addHandler(self._file_handler)

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
            if cls._instance is not None:
                if cls._instance._console_handler is not None:
                    cls._instance._internal.removeHandler(cls._instance._console_handler)
                if cls._instance._file_handler is not None:
                    cls._instance._internal.removeHandler(cls._instance._file_handler)
                    cls._instance._file_handler.close()
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
        self._internal.log(int(level), message)

    def set_level(self, level: LogLevel) -> None:
        """Change the minimum log level at runtime.

        Args:
            level: The new minimum :class:`LogLevel`.
        """
        with self._lock:
            self.config.level = level
            self._internal.setLevel(int(level))

    def enable(self) -> None:
        """Enable log output."""
        with self._lock:
            self.config.enabled = True
            self._internal.setLevel(int(self.config.level))

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
