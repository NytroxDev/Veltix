"""
Veltix exception hierarchy.

All Veltix exceptions inherit from VeltixError for easy catching.
"""


class VeltixError(Exception):
    """Base exception class for all Veltix framework errors."""

    pass


class MessageTypeError(VeltixError):
    """Raised when a message type operation is invalid."""

    pass


class SenderError(VeltixError):
    """Raised when a sender operation fails."""

    pass


class RequestError(VeltixError):
    """Raised when request parsing or compilation fails."""

    pass


class NetworkError(VeltixError):
    """Raised when a network operation fails."""

    pass


class TimeoutError(VeltixError):
    """Raised when an operation times out."""

    pass
