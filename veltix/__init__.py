"""
Veltix - The networking library you always wanted.

A simple, zero-dependency TCP networking library with message integrity
and request/response patterns.
"""

__version__ = "1.2.1"

from .client.client import Client, ClientConfig
from .exceptions import MessageTypeError, RequestError, SenderError, VeltixError
from .logger.config import LoggerConfig
from .logger.core import Logger
from .logger.levels import LogLevel
from .network.request import Request, Response
from .network.sender import Mode, Sender
from .network.system_types import PING, PONG
from .network.types import MessageType
from .server.server import ClientInfo, Server, ServerConfig
from .utils.events import Events

__all__ = [
    # Version
    "__version__",
    # Client
    "Client",
    "ClientConfig",
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
    # System types
    "PING",
    "PONG",
    # Utils
    "Events",
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
