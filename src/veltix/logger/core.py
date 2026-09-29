"""Core logger implementation."""

from __future__ import annotations

import logging
import logging.handlers
import threading

from .config import LoggerConfig
from .formatter import VeltixFormatter
from .levels import LogLevel


def _format_message(message: str, args: tuple[object, ...]) -> str:
    """Apply %-style formatting to a log message like stdlib ``logging``.

    With no args the message is returned untouched. A single mapping
    argument applies to named ``%(key)s`` placeholders.

    Args:
        message: The raw log message.
        args: Formatting arguments (positional or a single mapping).

    Returns:
        The formatted message.
    """
    if len(args) == 1 and isinstance(args[0], dict):
        return message % args[0]
    if args:
        return message % args
    return message


class Logger:
    """Thread-safe singleton logger backed by stdlib logging.

    The logger is implemented as a singleton: calling ``Logger()`` or
    ``Logger.get_instance()`` always returns the same object. Passing a
    :class:`LoggerConfig` to either call re-configures the singleton in
    place and resets the level counters, exactly like ``configure()``.

    Typical usage::

        from veltix import Logger

        logger = Logger.get_instance()
        logger.info("Server started")
    """

    _instance: Logger | None = None
    _initialized: bool = False
    _lock = threading.RLock()

    def __new__(cls, config: LoggerConfig | None = None) -> Logger:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: LoggerConfig | None = None) -> None:
        if not self._initialized:
            self._initialized = True
            self._stats = dict.fromkeys(LogLevel, 0)
            self._internal = logging.getLogger("veltix")
            self._internal.propagate = False
            self._console_handler: logging.StreamHandler | None = None
            self._file_handler: logging.handlers.RotatingFileHandler | None = None
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

        # Console handler
        self._console_handler = logging.StreamHandler(config.stream)
        self._console_handler.setFormatter(
            VeltixFormatter(
                use_colors=config.use_colors,
                show_timestamp=config.show_timestamp,
                show_level=config.show_level,
                show_caller=config.show_caller,
            )
        )
        self._internal.addHandler(self._console_handler)

        # File handler
        if config.file_path is not None:
            try:
                self._file_handler = logging.handlers.RotatingFileHandler(
                    config.file_path,
                    maxBytes=config.file_rotation_size,
                    backupCount=config.file_backup_count,
                    encoding="utf-8",
                )
            except OSError as exc:
                raise ValueError(f"cannot open log file '{config.file_path}': {exc}") from exc
            self._file_handler.setFormatter(
                VeltixFormatter(use_colors=False, show_caller=config.show_caller)
            )
            self._internal.addHandler(self._file_handler)

        # Apply the enabled state last: handlers stay attached (same as
        # disable()), so a later enable() restores output without rebuilding.
        if config.enabled:
            self._internal.setLevel(int(config.level))
        else:
            self._internal.setLevel(logging.CRITICAL + 10)

    @classmethod
    def get_instance(cls, config: LoggerConfig | None = None) -> Logger:
        """Get the singleton, optionally reconfiguring it with *config*.

        Passing a config re-applies it to the existing instance (handlers are
        rebuilt and the level counters reset), exactly like ``configure()``.

        Args:
            config: Optional configuration to apply to the singleton.

        Returns:
            The shared :class:`Logger` instance.
        """
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

    def trace(self, message: str, *args: object) -> None:
        """Log a TRACE-level message (severity 5).

        Args:
            message: The log message, with %-style placeholders when *args
                are provided.
            *args: Optional formatting arguments, like stdlib logging.
        """
        self._log(LogLevel.TRACE, message, *args)

    def debug(self, message: str, *args: object) -> None:
        """Log a DEBUG-level message (severity 10).

        Args:
            message: The log message, with %-style placeholders when *args
                are provided.
            *args: Optional formatting arguments, like stdlib logging.
        """
        self._log(LogLevel.DEBUG, message, *args)

    def info(self, message: str, *args: object) -> None:
        """Log an INFO-level message (severity 20).

        Args:
            message: The log message, with %-style placeholders when *args
                are provided.
            *args: Optional formatting arguments, like stdlib logging.
        """
        self._log(LogLevel.INFO, message, *args)

    def success(self, message: str, *args: object) -> None:
        """Log a SUCCESS-level message (severity 25).

        Args:
            message: The log message, with %-style placeholders when *args
                are provided.
            *args: Optional formatting arguments, like stdlib logging.
        """
        self._log(LogLevel.SUCCESS, message, *args)

    def warning(self, message: str, *args: object) -> None:
        """Log a WARNING-level message (severity 30).

        Args:
            message: The log message, with %-style placeholders when *args
                are provided.
            *args: Optional formatting arguments, like stdlib logging.
        """
        self._log(LogLevel.WARNING, message, *args)

    def error(self, message: str, *args: object) -> None:
        """Log an ERROR-level message (severity 40).

        Args:
            message: The log message, with %-style placeholders when *args
                are provided.
            *args: Optional formatting arguments, like stdlib logging.
        """
        self._log(LogLevel.ERROR, message, *args)

    def critical(self, message: str, *args: object) -> None:
        """Log a CRITICAL-level message (severity 50).

        Args:
            message: The log message, with %-style placeholders when *args
                are provided.
            *args: Optional formatting arguments, like stdlib logging.
        """
        self._log(LogLevel.CRITICAL, message, *args)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _log(self, level: LogLevel, message: str, *args: object, stacklevel: int = 3) -> None:
        if not self.config.enabled or level < self.config.level:
            return

        # Deliberately lock-free: _log runs on the network hot path and the
        # GIL keeps the dict intact; counts are best-effort and may be
        # slightly under-reported under heavy multi-thread contention.
        self._stats[level] += 1
        self._internal.log(int(level), _format_message(message, args), stacklevel=stacklevel)

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

        Counts are best-effort: under heavy multi-thread contention a few
        increments may be lost (no lock on the hot path), so treat them as
        an approximation rather than an exact tally.

        Returns:
            A dictionary mapping each :class:`LogLevel` to the number of
            messages logged at that level.
        """
        with self._lock:
            return self._stats.copy()
