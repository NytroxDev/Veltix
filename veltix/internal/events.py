from enum import Enum, auto


class ServerEvent(Enum):
    ON_CONNECT = auto()
    ON_DISCONNECT = auto()
    STARTED = auto()
    STOPPED = auto()
    CLIENT_REJECTED = auto()


class ClientEvent(Enum):
    ON_CONNECT = auto()
    ON_DISCONNECT = auto()
    SOCKET_DISCONNECTED = auto()
    CONNECTING = auto()
    DISCONNECTING = auto()
    TAG_ADDED = auto()
    TAG_REMOVED = auto()
    TAG_CLEARED = auto()


class MessageEvent(Enum):
    RECEIVED = auto()
    SENT = auto()
    ROUTED = auto()
    UNHANDLED = auto()
    PENDING_REGISTERED = auto()
    PENDING_SATISFIED = auto()
    PENDING_TIMEOUT = auto()
    ROUTE_REGISTERED = auto()
    ROUTE_UNREGISTERED = auto()


class ProtocolEvent(Enum):
    PING = auto()
    PONG = auto()
    HANDSHAKE_START = auto()
    HANDSHAKE_DONE = auto()
    HANDSHAKE_FAIL = auto()


class ErrorEvent(Enum):
    NETWORK = auto()
    HANDLER = auto()
    CALLBACK = auto()
    SEND = auto()
    ACCEPT = auto()
    CONNECTION_REFUSED = auto()


class LogEvent(Enum):
    TRACE = auto()
    DEBUG = auto()
    INFO = auto()
    SUCCESS = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()


class ReconnectEvent(Enum):
    ATTEMPT = auto()
    FAIL = auto()
    SUCCESS = auto()
    CANCELLED = auto()


# ── Backward compat (to remove once migration is done) ─────────────────────

class Events(Enum):
    ON_RECV = "on_recv"
    ON_CONNECT = "on_connect"
    ON_DISCONNECT = "on_disconnect"


events = [Events.ON_RECV, Events.ON_CONNECT, Events.ON_DISCONNECT]
