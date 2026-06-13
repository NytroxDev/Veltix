"""Network utility functions."""

from __future__ import annotations

import socket
from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

from ..logger.core import Logger

if TYPE_CHECKING:
    from ..socket_core.base_socket import BaseSocket


class RecvStatus(Enum):
    """Status of a recv() call."""

    OK = auto()
    TIMEOUT = auto()
    CLOSED = auto()
    ERROR = auto()


class RecvResult:
    """Result of a recv() call."""

    __slots__ = ("status", "data")

    def __init__(self, status: RecvStatus, data: Optional[bytes] = None) -> None:
        self.status = status
        self.data = data

    @property
    def ok(self) -> bool:
        return self.status == RecvStatus.OK

    @property
    def timed_out(self) -> bool:
        return self.status == RecvStatus.TIMEOUT

    @property
    def disconnected(self) -> bool:
        return self.status in (RecvStatus.CLOSED, RecvStatus.ERROR)

    def __repr__(self) -> str:
        if self.ok:
            return f"RecvResult(OK, {len(self.data)} bytes)"
        return f"RecvResult({self.status.name})"


def recv(conn: BaseSocket, buf_size: int = 1024) -> RecvResult:
    """
    Receive data from a socket with explicit status reporting.

    Works with both blocking (settimeout) and non-blocking sockets.
    For non-blocking sockets, BlockingIOError is reported as TIMEOUT.
    """
    logger = Logger.get_instance()

    try:
        data = conn.recv(buf_size)

        if not data:
            return RecvResult(RecvStatus.CLOSED)

        return RecvResult(RecvStatus.OK, data)

    except socket.timeout:
        return RecvResult(RecvStatus.TIMEOUT)

    except BlockingIOError:
        return RecvResult(RecvStatus.TIMEOUT)

    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
        logger.warning("Connection reset by peer")
        return RecvResult(RecvStatus.ERROR)

    except OSError as e:
        logger.debug(f"OSError on recv: {e}")
        return RecvResult(RecvStatus.ERROR)

    except Exception as e:
        logger.error(f"Unexpected recv error: {type(e).__name__}: {e}")
        return RecvResult(RecvStatus.ERROR)
