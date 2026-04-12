"""Event types for Veltix clients and servers."""

from enum import Enum


class Events(Enum):
    ON_RECV = "on_recv"
    ON_CONNECT = "on_connect"
    ON_DISCONNECT = "on_disconnect"


events = [Events.ON_RECV, Events.ON_CONNECT, Events.ON_DISCONNECT]
