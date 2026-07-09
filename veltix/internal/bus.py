from __future__ import annotations

from .._vendor.avyra import EventBus
from .events import (
    ClientEvent,
    LogEvent,
    MessageEvent,
    ProtocolEvent,
    ReconnectEvent,
    ServerEvent,
)
from ..logger.core import Logger

_ALL_EVENTS = [ServerEvent, ClientEvent, MessageEvent, ProtocolEvent, LogEvent, ReconnectEvent]


class VeltixBus(EventBus):
    """Veltix event bus — wraps Avyra EventBus with sugar + auto-log subscriber.

    Each Server and Client owns its own ``VeltixBus`` instance.
    """

    def __init__(self) -> None:
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
        self.emit(LogEvent.TRACE, msg)

    def debug(self, msg: str) -> None:
        self.emit(LogEvent.DEBUG, msg)

    def info(self, msg: str) -> None:
        self.emit(LogEvent.INFO, msg)

    def success(self, msg: str) -> None:
        self.emit(LogEvent.SUCCESS, msg)

    def warning(self, msg: str) -> None:
        self.emit(LogEvent.WARNING, msg)

    def error(self, msg: str) -> None:
        self.emit(LogEvent.ERROR, msg)

    def critical(self, msg: str) -> None:
        self.emit(LogEvent.CRITICAL, msg)
