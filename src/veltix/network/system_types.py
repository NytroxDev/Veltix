"""System-level message types for Veltix protocol."""

from .types import MessageType

# Core system messages (0-9)
PING = MessageType(0, "ping", "Request latency measurement", _system=True)
PONG = MessageType(1, "pong", "Response to PING request", _system=True)
