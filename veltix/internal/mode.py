from enum import Enum


class Mode(Enum):
    """
    Sender operating mode.

    Attributes:
        SERVER: Can send to multiple clients (broadcast)
        CLIENT: Can only send to server
    """

    SERVER = "server"
    CLIENT = "client"
