# network.py
"""Network utility functions."""

from enum import Enum, auto
from typing import Optional

from ..logger.core import Logger
from ..socket.base_socket import BaseSocket


class RecvStatus(Enum):
    """
    Status of a recv() call.

    Attributes:
        OK:      Data received normally.
        TIMEOUT: Socket timed out — connection still alive, caller should loop again.
        CLOSED:  Peer closed the connection cleanly (TCP FIN received).
        ERROR:   Fatal connection error (reset, aborted, OS error, etc.).
    """

    OK = auto()
    TIMEOUT = auto()
    CLOSED = auto()
    ERROR = auto()


class RecvResult:
    """
    Result of a recv() call.

    Attributes:
        status: The outcome of the recv call.
        data:   Received bytes if status is OK, None otherwise.
    """

    __slots__ = ("status", "data")

    def __init__(self, status: RecvStatus, data: Optional[bytes] = None) -> None:
        self.status = status
        self.data = data

    @property
    def ok(self) -> bool:
        """True if data was received normally."""
        return self.status == RecvStatus.OK

    @property
    def timed_out(self) -> bool:
        """True if the socket timed out — connection is still alive."""
        return self.status == RecvStatus.TIMEOUT

    @property
    def disconnected(self) -> bool:
        """True if the connection is gone (closed cleanly or fatal error)."""
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

    The socket MUST have a timeout set via settimeout() for TIMEOUT
    to be returned correctly. Without a timeout, this call blocks indefinitely.

    Usage in a recv loop::

        while running:
            result = recv(conn, buf_size)

            if result.timed_out:
                continue

            if result.disconnected:
                handle_disconnect()
                break

            process(result.data)

    Args:
        conn:     Socket to receive from. Must have settimeout() set.
        buf_size: Maximum number of bytes to read per call (default: 1024).

    Returns:
        RecvResult with one of:
            OK      — data received, result.data contains the bytes.
            TIMEOUT — timed out, connection still alive, loop again.
            CLOSED  — peer closed the connection cleanly.
            ERROR   — fatal error, connection is gone.
    """
    logger = Logger.get_instance()

    try:
        data = conn.recv(buf_size)

        if not data:
            logger.debug("Connection closed cleanly by peer")
            return _CLOSED_RESULT

        logger.debug(f"Received {len(data)} bytes")
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
