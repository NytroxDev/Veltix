from __future__ import annotations

from enum import Enum, auto


class VeltixEvent(Enum):
    # ── Lifecycle ──────────────────────────────────────────────────────────────
    ON_CONNECT = auto()
    ON_DISCONNECT = auto()
    ON_RECV = auto()

    # ── Messages ───────────────────────────────────────────────────────────────
    MESSAGE = auto()

    # ── Protocol ───────────────────────────────────────────────────────────────
    PING = auto()
    PONG = auto()
    HANDSHAKE_START = auto()
    HANDSHAKE_DONE = auto()
    HANDSHAKE_FAIL = auto()

    # ── Logging ────────────────────────────────────────────────────────────────
    LOG_TRACE = auto()
    LOG_DEBUG = auto()
    LOG_INFO = auto()
    LOG_SUCCESS = auto()
    LOG_WARNING = auto()
    LOG_ERROR = auto()
    LOG_CRITICAL = auto()

    # ── Reconnection ───────────────────────────────────────────────────────────
    RECONNECT_ATTEMPT = auto()
    RECONNECT_FAIL = auto()
    RECONNECT_SUCCESS = auto()
    RECONNECT_CANCELLED = auto()
