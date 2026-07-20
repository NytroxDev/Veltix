from enum import Enum, auto


class ServerEvent(Enum):
    """Events emitted during the server lifecycle.

    Attributes:
        ON_CONNECT: A new client connected and passed the handshake.
        ON_DISCONNECT: A client disconnected.
        STARTED: The server started listening.
        STOPPED: The server stopped listening.
        CLIENT_REJECTED: A client was rejected (e.g. max connections, bad handshake).
    """

    ON_CONNECT = auto()
    ON_DISCONNECT = auto()
    STARTED = auto()
    STOPPED = auto()
    CLIENT_REJECTED = auto()


class ClientEvent(Enum):
    """Events emitted during the client lifecycle.

    Attributes:
        ON_CONNECT: Successfully connected and completed the handshake.
        ON_DISCONNECT: Disconnected from the server.
        SOCKET_DISCONNECTED: The underlying socket was closed unexpectedly.
        CONNECTING: A connection attempt is in progress.
        DISCONNECTING: A disconnection is in progress.
        TAG_ADDED: A tag was added to the client info.
        TAG_REMOVED: A tag was removed from the client info.
        TAG_CLEARED: All tags were cleared from the client info.
    """

    ON_CONNECT = auto()
    ON_DISCONNECT = auto()
    SOCKET_DISCONNECTED = auto()
    CONNECTING = auto()
    DISCONNECTING = auto()
    TAG_ADDED = auto()
    TAG_REMOVED = auto()
    TAG_CLEARED = auto()


class MessageEvent(Enum):
    """Events emitted during message processing.

    Attributes:
        RECEIVED: A message was received from the network.
        SENT: A message was sent successfully.
        ROUTED: A message was dispatched to a registered route handler.
        UNHANDLED: A message had no matching route handler.
        PENDING_REGISTERED: A pending request (send-and-wait) was registered.
        PENDING_SATISFIED: A pending request received its response.
        PENDING_TIMEOUT: A pending request timed out.
        ROUTE_REGISTERED: A new route was registered.
        ROUTE_UNREGISTERED: A route was unregistered.
    """

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
    """Events emitted for protocol-level operations.

    Attributes:
        PING: A ping was sent or received.
        PONG: A pong was sent or received.
        HANDSHAKE_START: A handshake attempt has begun.
        HANDSHAKE_DONE: The handshake completed successfully.
        HANDSHAKE_FAIL: The handshake failed.
    """

    PING = auto()
    PONG = auto()
    HANDSHAKE_START = auto()
    HANDSHAKE_DONE = auto()
    HANDSHAKE_FAIL = auto()


class ErrorEvent(Enum):
    """Events emitted when errors occur.

    Attributes:
        NETWORK: A network-level error (e.g. connection reset).
        HANDLER: An error inside a route handler.
        CALLBACK: An error inside a user callback.
        SEND: A send operation failed.
        ACCEPT: The server accept loop encountered an error.
        CONNECTION_REFUSED: A connection attempt was refused.
    """

    NETWORK = auto()
    HANDLER = auto()
    CALLBACK = auto()
    SEND = auto()
    ACCEPT = auto()
    CONNECTION_REFUSED = auto()


class LogEvent(Enum):
    """Events emitted for structured logging.

    Attributes:
        TRACE: Trace-level log message.
        DEBUG: Debug-level log message.
        INFO: Info-level log message.
        SUCCESS: Success-level log message.
        WARNING: Warning-level log message.
        ERROR: Error-level log message.
        CRITICAL: Critical-level log message.
    """

    TRACE = auto()
    DEBUG = auto()
    INFO = auto()
    SUCCESS = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()


class ReconnectEvent(Enum):
    """Events emitted during reconnection attempts.

    Attributes:
        ATTEMPT: A reconnection attempt is being made.
        FAIL: A reconnection attempt failed.
        SUCCESS: Reconnection succeeded.
        CANCELLED: Reconnection was cancelled (e.g. max retries reached).
    """

    ATTEMPT = auto()
    FAIL = auto()
    SUCCESS = auto()
    CANCELLED = auto()
