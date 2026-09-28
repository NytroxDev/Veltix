"""
Veltix exception hierarchy.

All Veltix exceptions inherit from VeltixError for easy catching.
"""


class VeltixError(Exception):
    """Base exception class for all Veltix framework errors."""


class MessageTypeError(VeltixError):
    """Raised when a message type operation is invalid."""


class SenderError(VeltixError):
    """Raised when a sender operation fails."""


class RequestError(VeltixError):
    """Raised when request parsing or compilation fails."""


class NetworkError(VeltixError):
    """Raised when a network operation fails."""


class TimeoutError(VeltixError):
    """Raised when an operation times out."""


class InvalidContentError(VeltixError):
    """Raised when message content cannot be decoded or converted to the requested format."""


class ServerFullError(VeltixError):
    """Raised when the server rejects a connection because it is at capacity."""


class IDsExhaustedError(VeltixError):
    """Raised when all request IDs in the window are currently pending."""
