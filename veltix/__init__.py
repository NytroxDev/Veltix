"""
Veltix - The networking library you always wanted.

A simple, zero-dependency TCP networking library with message integrity
and request/response patterns.
"""

from .client.client import Client, ClientConfig, DisconnectReason
from .client.disconnect import DisconnectState
from .exceptions import MessageTypeError, RequestError, SenderError, VeltixError
from .internal.buffer_size import BufferSize
from .internal.events import Events
from .internal.performance_mode import PerformanceMode
from .logger.config import LoggerConfig
from .logger.core import Logger
from .logger.levels import LogLevel
from .network.request import Request, Response
from .network.sender import Mode, Sender
from .network.system_types import HELLO, HELLO_ACK, PING, PONG
from .network.types import MessageType
from .server.server import ClientInfo, Server, ServerConfig
from .socket.core import SocketCore
from .utils.encoding import decode_json, decode_utf8, encode_json, encode_utf8
from .utils.format_size import format_bytes
from .version import __version__

__all__ = [
    # Version
    "__version__",
    # Client
    "Client",
    "ClientConfig",
    "DisconnectState",
    "DisconnectReason",
    # Server
    "Server",
    "ServerConfig",
    "ClientInfo",
    # Network
    "Request",
    "Response",
    "Sender",
    "Mode",
    "MessageType",
    # Socket
    "SocketCore",
    # System types
    "PING",
    "PONG",
    "HELLO",
    "HELLO_ACK",
    # Utils
    "decode_json",
    "decode_utf8",
    "encode_json",
    "encode_utf8",
    "format_bytes",
    "Events",
    "PerformanceMode",
    "BufferSize",
    # Logger
    "Logger",
    "LoggerConfig",
    "LogLevel",
    # Exceptions
    "VeltixError",
    "MessageTypeError",
    "RequestError",
    "SenderError",
]
