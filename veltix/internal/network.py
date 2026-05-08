"""Network utility functions."""

from __future__ import annotations

from enum import Enum, auto
from typing import Optional

from ..logger.core import Logger
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


_TIMEOUT_RESULT = RecvResult(RecvStatus.TIMEOUT)
_CLOSED_RESULT = RecvResult(RecvStatus.CLOSED)
_ERROR_RESULT = RecvResult(RecvStatus.ERROR)


def recv(conn: BaseSocket, buf_size: int = 1024) -> RecvResult:
    """
    Receive data from a socket with explicit status reporting.

    The socket must have a timeout set via settimeout() — without one,
    this call blocks indefinitely and TIMEOUT is never returned.
    """
    logger = Logger.get_instance()

    try:
        data = conn.recv(buf_size)

        if not data:
            return _CLOSED_RESULT

        return RecvResult(RecvStatus.OK, data)

    except TimeoutError:
        return _TIMEOUT_RESULT

    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
        logger.warning("Connection reset by peer")
        return _ERROR_RESULT

    except OSError as e:
        logger.debug(f"OSError on recv: {e}")
        return _ERROR_RESULT

    except Exception as e:
        logger.error(f"Unexpected recv error: {type(e).__name__}: {e}")
        return _ERROR_RESULT
