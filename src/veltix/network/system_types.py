"""System-level message types for Veltix protocol."""

from .types import MessageType

# Core system messages (0-9)
PING = MessageType(0, "ping", "Request latency measurement", _system=True)
PONG = MessageType(1, "pong", "Response to PING request", _system=True)

# Error system messages (20-49)
ERROR = MessageType(20, "error", "Generic error response", _system=True)
INVALID_REQUEST = MessageType(21, "invalid_request", "Request validation failure", _system=True)
