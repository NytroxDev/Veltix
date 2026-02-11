"""Event binding types for Veltix clients and servers."""

from enum import Enum


class Events(Enum):
    """
    Event types that can be bound to callbacks.

    Attributes:
        ON_RECV: Triggered when a message is received
        ON_CONNECT: Triggered when a client connects (server only)
    """

    ON_RECV = "on_recv"
    ON_CONNECT = "on_connect"
