"""Network utility functions."""

from __future__ import annotations

import socket
from enum import Enum, auto
from typing import TYPE_CHECKING, Callable, Optional

from ..logger.core import Logger
from .events import ErrorEvent, MessageEvent

if TYPE_CHECKING:
    from ..network.message_buffer import MessageBuffer
    from ..network.response import Response
    from ..socket_core.base_socket import BaseSocket
    from .bus import VeltixBus


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
            return f"RecvResult(OK, {len(self.data or b'')} bytes)"
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


def dispatch_messages(
    buffer: MessageBuffer,
    bus: VeltixBus,
    handler: Callable[[Response], object],
    client_addr: Optional[tuple[str, int]] = None,
) -> None:
    """Extract and dispatch all complete messages from a buffer.

    Emits a debug log and MessageEvent.RECEIVED for each parsed message,
    then invokes *handler*. Parsing errors are caught so a malformed
    stream cannot crash the caller.

    Args:
        buffer: The message buffer to consume.
        bus: Event bus used to emit events and log errors.
        handler: Callback invoked with each parsed message.
        client_addr: Server-side client address, or None for the client role.

    Returns:
        None.
    """
    try:
        for message in buffer.extract_messages():
            if client_addr is not None:
                source = str(client_addr)
                payload: dict[str, object] = {
                    "type": message.type,
                    "length": len(message.content),
                    "client": client_addr,
                }
            else:
                source = "server"
                payload = {
                    "type": message.type,
                    "length": len(message.content),
                    "from": "server",
                }
            bus.emit(MessageEvent.RECEIVED, payload)
            handler(message)
    except Exception as e:
        source = str(client_addr) if client_addr is not None else "server"
        bus.emit(ErrorEvent.HANDLER, {"error": str(e), "source": source})
        bus.error(f"Error dispatching message from {source}: {type(e).__name__}: {e}")
