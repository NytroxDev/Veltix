"""System-level message types for Veltix protocol."""

from .types import MessageType

# Core system messages (0-9)
PING = MessageType(0, "ping", "Request latency measurement")
PONG = MessageType(1, "pong", "Response to PING request")
HEARTBEAT = MessageType(2, "heartbeat", "Keep-alive message")

# Connection management (10-19)
HELLO = MessageType(10, "hello", "Initial handshake")

# Error messages (20-29)
ERROR = MessageType(20, "error", "Generic error message")
INVALID_REQUEST = MessageType(21, "invalid_request", "Malformed request")
