"""Network utility functions."""

from __future__ import annotations

import contextlib
import socket
from enum import Enum, auto
from typing import TYPE_CHECKING

from ..exceptions import ServerFullError
from ..logger.core import Logger
from .events import ErrorEvent, MessageEvent, ServerEvent

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..handler.handshake_handler import HandshakeHandler
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


def reject_full_connection(
    conn: socket.socket,
    addr: tuple[str, int],
    bus: VeltixBus,
    handshake_handler: HandshakeHandler,
    current: int,
    max_client: int,
) -> None:
    """Reject a freshly accepted connection because the server is at capacity.

    Emits the same observability events on both socket backends, sends the
    rejection payload, then closes the connection.

    Args:
        conn: The accepted raw socket, closed by this call.
        addr: ``(host, port)`` of the rejected peer.
        bus: Event bus used to emit events and log the rejection.
        handshake_handler: Handler able to send the rejection payload.
        current: Number of clients connected when the rejection happened.
        max_client: The server capacity that was reached.
    """
    bus.info(f"Connection rejected: server full ({addr}, {current}/{max_client})")
    bus.emit(
        ErrorEvent.CONNECTION_REFUSED,
        {
            "max_client": max_client,
            "current": current,
            "addr": addr,
        },
    )
    bus.emit(
        ServerEvent.CLIENT_REJECTED,
        {
            "max_client": max_client,
            "current": current,
            "reason": "server_full",
            "addr": addr,
        },
    )
    with contextlib.suppress(OSError):
        handshake_handler.send_rejection(conn, "server_full")
    with contextlib.suppress(OSError):
        conn.close()


def connect_and_handshake(
    sock: socket.socket,
    bus: VeltixBus,
    handshake_handler: HandshakeHandler,
    host: str,
    port: int,
    timeout: float,
) -> bool:
    """Connect a client socket and run the protocol handshake.

    Shared by both socket backends: covers the raw ``connect``, the
    blocking handshake and the error mapping, so each backend only owns
    what happens after (selector registration or receive thread).

    Args:
        sock: The raw socket to connect. Closed by this call on failure.
        bus: Event bus used to emit events and log the attempt.
        handshake_handler: Handler running the client-side handshake.
        host: Server address.
        port: Server port.
        timeout: Handshake timeout, in seconds.

    Returns:
        True when the handshake completed, False otherwise.

    Raises:
        ServerFullError: The server rejected the connection as being full.
            Propagated so the caller can distinguish it from a plain failure.
    """
    try:
        sock.connect((host, port))

        success, _ = handshake_handler.do_client_handshake(sock, timeout=timeout)
        if not success:
            bus.error("Client handshake failed")
            sock.close()
            return False

        return True

    except (TimeoutError, ConnectionRefusedError) as e:
        # The socket may be half-open (connect or handshake in flight):
        # release its fd now instead of leaking it until reconnection.
        sock.close()
        bus.emit(ErrorEvent.NETWORK, {"error": str(e), "host": host, "port": port})
        bus.error(f"Connection failed to {host}:{port}: {type(e).__name__}")
        return False

    except ServerFullError:
        raise

    except Exception as e:
        bus.emit(ErrorEvent.NETWORK, {"error": str(e), "host": host, "port": port})
        bus.error(f"Unexpected connection error: {type(e).__name__}: {e}")
        return False


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
            if bus.has_subscribers(MessageEvent.RECEIVED):
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
