from __future__ import annotations

import inspect
from pathlib import Path
from typing import Optional

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

    Attributes:
        _SKIP: Substrings of filenames to skip when resolving the caller.
    """

    _SKIP = ("logger", "bus", "avyra")

    def __init__(self) -> None:
        """Initialise the bus and register all Veltix event enums."""
        super().__init__()
        for event_class in _ALL_EVENTS:
            self.register(event_class)
        self._attach_logger()

    # ── Internal ───────────────────────────────────────────────────────────────

    def _attach_logger(self) -> None:
        log = Logger.get_instance()
        self.subscribe(LogEvent.TRACE, lambda e, p: log.trace(p[0], caller=p[1]))
        self.subscribe(LogEvent.DEBUG, lambda e, p: log.debug(p[0], caller=p[1]))
        self.subscribe(LogEvent.INFO, lambda e, p: log.info(p[0], caller=p[1]))
        self.subscribe(LogEvent.SUCCESS, lambda e, p: log.success(p[0], caller=p[1]))
        self.subscribe(LogEvent.WARNING, lambda e, p: log.warning(p[0], caller=p[1]))
        self.subscribe(LogEvent.ERROR, lambda e, p: log.error(p[0], caller=p[1]))
        self.subscribe(LogEvent.CRITICAL, lambda e, p: log.critical(p[0], caller=p[1]))

    @staticmethod
    def _get_caller_info() -> Optional[str]:
        try:
            frame = inspect.currentframe()
            while frame:
                name = frame.f_code.co_filename.lower()
                if not any(pat in name for pat in VeltixBus._SKIP):
                    break
                frame = frame.f_back
            if frame:
                return f"{Path(frame.f_code.co_filename).name}:{frame.f_lineno}"
        except Exception:
            pass
        return None

    # ── Sugar emit ─────────────────────────────────────────────────────────────

    def trace(self, msg: str) -> None:
        """Emit a TRACE-level log event.

        Args:
            msg: The log message.
        """
        self.emit(LogEvent.TRACE, (msg, self._get_caller_info()))

    def debug(self, msg: str) -> None:
        """Emit a DEBUG-level log event.

        Args:
            msg: The log message.
        """
        self.emit(LogEvent.DEBUG, (msg, self._get_caller_info()))

    def info(self, msg: str) -> None:
        """Emit an INFO-level log event.

        Args:
            msg: The log message.
        """
        self.emit(LogEvent.INFO, (msg, self._get_caller_info()))

    def success(self, msg: str) -> None:
        """Emit a SUCCESS-level log event.

        Args:
            msg: The log message.
        """
        self.emit(LogEvent.SUCCESS, (msg, self._get_caller_info()))

    def warning(self, msg: str) -> None:
        """Emit a WARNING-level log event.

        Args:
            msg: The log message.
        """
        self.emit(LogEvent.WARNING, (msg, self._get_caller_info()))

    def error(self, msg: str) -> None:
        """Emit an ERROR-level log event.

        Args:
            msg: The log message.
        """
        self.emit(LogEvent.ERROR, (msg, self._get_caller_info()))

    def critical(self, msg: str) -> None:
        """Emit a CRITICAL-level log event.

        Args:
            msg: The log message.
        """
        self.emit(LogEvent.CRITICAL, (msg, self._get_caller_info()))
