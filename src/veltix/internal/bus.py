from __future__ import annotations

from .._vendor.avyra import EventBus
from ..logger.core import Logger
from .events import (
    ClientEvent,
    ErrorEvent,
    LogEvent,
    MessageEvent,
    ProtocolEvent,
    ReconnectEvent,
    ServerEvent,
)

_ALL_EVENTS = [
    ServerEvent,
    ClientEvent,
    MessageEvent,
    ProtocolEvent,
    ErrorEvent,
    LogEvent,
    ReconnectEvent,
]


class VeltixBus(EventBus):
    """Veltix event bus — wraps Avyra EventBus with sugar + auto-log subscriber.

    Each Server and Client owns its own ``VeltixBus`` instance. The bus
    automatically registers all Veltix event enums and subscribes the
    singleton Logger to ``LogEvent.*`` so that ``bus.info(...)`` produces
    structured log output.
    """

    def __init__(self) -> None:
        """Initialise the bus and register all Veltix event enums."""
        super().__init__()
        for event_class in _ALL_EVENTS:
            self.register(event_class)
        self._attach_logger()

    # ── Internal ───────────────────────────────────────────────────────────────

    def _attach_logger(self) -> None:
        log = Logger.get_instance()
        self.subscribe(LogEvent.TRACE, lambda e, m: log.trace(m))
        self.subscribe(LogEvent.DEBUG, lambda e, m: log.debug(m))
        self.subscribe(LogEvent.INFO, lambda e, m: log.info(m))
        self.subscribe(LogEvent.SUCCESS, lambda e, m: log.success(m))
        self.subscribe(LogEvent.WARNING, lambda e, m: log.warning(m))
        self.subscribe(LogEvent.ERROR, lambda e, m: log.error(m))
        self.subscribe(LogEvent.CRITICAL, lambda e, m: log.critical(m))

    # ── Sugar emit ─────────────────────────────────────────────────────────────

    def trace(self, msg: str) -> None:
        """Emit a TRACE-level log event.

        Args:
            msg: The log message.
        """
        self.emit(LogEvent.TRACE, msg)

    def debug(self, msg: str) -> None:
        """Emit a DEBUG-level log event.

        Args:
            msg: The log message.
        """
        self.emit(LogEvent.DEBUG, msg)

    def info(self, msg: str) -> None:
        """Emit an INFO-level log event.

        Args:
            msg: The log message.
        """
        self.emit(LogEvent.INFO, msg)

    def success(self, msg: str) -> None:
        """Emit a SUCCESS-level log event.

        Args:
            msg: The log message.
        """
        self.emit(LogEvent.SUCCESS, msg)

    def warning(self, msg: str) -> None:
        """Emit a WARNING-level log event.

        Args:
            msg: The log message.
        """
        self.emit(LogEvent.WARNING, msg)

    def error(self, msg: str) -> None:
        """Emit an ERROR-level log event.

        Args:
            msg: The log message.
        """
        self.emit(LogEvent.ERROR, msg)

    def critical(self, msg: str) -> None:
        """Emit a CRITICAL-level log event.

        Args:
            msg: The log message.
        """
        self.emit(LogEvent.CRITICAL, msg)
