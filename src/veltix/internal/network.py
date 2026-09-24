"""Network utility functions."""

from __future__ import annotations

import contextlib
import socket
from enum import Enum, auto
from typing import TYPE_CHECKING

from ..logger.core import Logger
from .events import ErrorEvent, MessageEvent

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..network.message_buffer import MessageBuffer
    from ..network.response import Response
    from ..socket_core.base_socket import BaseSocket
    from .bus import VeltixBus


def apply_tcp_tunings(sock: socket.socket) -> None:
    """Apply latency-focused TCP options.

    Turns on ``TCP_NODELAY`` (already default elsewhere), ``TCP_QUICKACK``
    and lowers ``TCP_NOTSENT_LOWAT`` to reduce ACK latency and outbound
    buffering. Options are Linux-only and silently skipped when
    unavailable.
    """
    with contextlib.suppress(AttributeError, OSError):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    with contextlib.suppress(AttributeError, OSError):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
    with contextlib.suppress(AttributeError, OSError):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NOTSENT_LOWAT, 16 * 1024)


class RecvStatus(Enum):
    """Status of a recv() call."""

    OK = auto()
    TIMEOUT = auto()
    CLOSED = auto()
    ERROR = auto()


class RecvResult:
    """Result of a recv() call."""

    __slots__ = ("status", "data")

    def __init__(self, status: RecvStatus, data: bytes | None = None) -> None:
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

    except TimeoutError:
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
    client_addr: tuple[str, int] | None = None,
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
            if bus._has_subscribers(MessageEvent.RECEIVED):
                bus.emit(
                    MessageEvent.RECEIVED,
                    {
                        "type": message.type,
                        "length": len(message.content),
                        **(
                            {"client": client_addr}
                            if client_addr is not None
                            else {"from": "server"}
                        ),
                    },
                )
            handler(message)
    except Exception as e:
        source = str(client_addr) if client_addr is not None else "server"
        bus.emit(ErrorEvent.HANDLER, {"error": str(e), "source": source})
        bus.error(f"Error dispatching message from {source}: {type(e).__name__}: {e}")
