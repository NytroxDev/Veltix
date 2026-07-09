from __future__ import annotations

from .._vendor.avyra import EventBus
from ..internal.events import VeltixEvent
from ..logger.core import Logger


class VeltixBus(EventBus):
    """Veltix event bus — wraps Avyra EventBus with sugar + auto-log subscriber.

    Each Server and Client owns its own ``VeltixBus`` instance.
    """

    def __init__(self) -> None:
        super().__init__()
        self.register(VeltixEvent)
        self._attach_logger()

    # ── Internal ───────────────────────────────────────────────────────────────

    def _attach_logger(self) -> None:
        """Subscribe the Logger singleton to all LOG_* events."""
        log = Logger.get_instance()
        self.subscribe(VeltixEvent.LOG_TRACE, lambda e, m: log.trace(m))
        self.subscribe(VeltixEvent.LOG_DEBUG, lambda e, m: log.debug(m))
        self.subscribe(VeltixEvent.LOG_INFO, lambda e, m: log.info(m))
        self.subscribe(VeltixEvent.LOG_SUCCESS, lambda e, m: log.success(m))
        self.subscribe(VeltixEvent.LOG_WARNING, lambda e, m: log.warning(m))
        self.subscribe(VeltixEvent.LOG_ERROR, lambda e, m: log.error(m))
        self.subscribe(VeltixEvent.LOG_CRITICAL, lambda e, m: log.critical(m))

    # ── Sugar emit ─────────────────────────────────────────────────────────────

    def trace(self, msg: str) -> None:
        self.emit(VeltixEvent.LOG_TRACE, msg)

    def debug(self, msg: str) -> None:
        self.emit(VeltixEvent.LOG_DEBUG, msg)

    def info(self, msg: str) -> None:
        self.emit(VeltixEvent.LOG_INFO, msg)

    def success(self, msg: str) -> None:
        self.emit(VeltixEvent.LOG_SUCCESS, msg)

    def warning(self, msg: str) -> None:
        self.emit(VeltixEvent.LOG_WARNING, msg)

    def error(self, msg: str) -> None:
        self.emit(VeltixEvent.LOG_ERROR, msg)

    def critical(self, msg: str) -> None:
        self.emit(VeltixEvent.LOG_CRITICAL, msg)
