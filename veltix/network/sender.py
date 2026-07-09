"""Message sending for Veltix."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from ..exceptions import SenderError
from ..internal.events import MessageEvent
from ..internal.mode import Mode

if TYPE_CHECKING:
    from ..internal.bus import VeltixBus
    from ..socket_core.base_socket import BaseSocket
    from .request import Request


class Sender:
    """
    Sends messages over TCP in CLIENT or SERVER mode.

    CLIENT: single server connection.
    SERVER: sends to individual clients or broadcasts.
    """

    def __init__(self, mode: Union[Mode, str], conn: Optional[BaseSocket] = None, bus: VeltixBus = None) -> None:  # type: ignore[assignment]
        """Initialize the sender with a mode and an optional connection.

        Args:
            mode: CLIENT or SERVER mode.
            conn: Connection socket (required in CLIENT mode).
            bus: Event bus instance.

        Raises:
            SenderError: If mode is CLIENT without a connection.
        """
        self.bus = bus

        if isinstance(mode, str):
            mode = Mode(mode)

        if mode == Mode.CLIENT and conn is None:
            raise SenderError("CLIENT mode requires a socket connection")

        self.mode = mode
        self.is_client = mode == Mode.CLIENT
        self.conn: Optional[BaseSocket] = conn

    def send(self, data: Request, client: Optional[BaseSocket] = None) -> bool:
        """Send a request over the network.

        In CLIENT mode, uses the internal connection.
        In SERVER mode, uses the provided client socket.

        Args:
            data: Request to send.
            client: Target client socket (required in SERVER mode).

        Returns:
            True if the send succeeded, False otherwise.
        """
        target = self.conn if self.is_client else client

        if target is None:
            if self.bus:
                self.bus.error(
                    "No connection available" if self.is_client else "No client socket provided"
                )
            return False

        try:
            target.send(data.compile())
            if self.bus:
                self.bus.emit(MessageEvent.SENT, {
                    "type": data.type,
                    "length": len(data.content),
                    "mode": "client" if self.is_client else "server",
                })
            return True
        except (ConnectionResetError, BrokenPipeError) as e:
            if self.bus:
                self.bus.warning(f"Connection error during send: {type(e).__name__}")
            if self.is_client:
                self.conn = None
            return False
        except Exception as e:
            if self.bus:
                self.bus.error(f"Unexpected send error: {type(e).__name__}: {e}")
            return False

    def broadcast(
        self,
        data: Request,
        list_of_client: list[BaseSocket],
        except_clients: Optional[list[BaseSocket]] = None,
    ) -> bool:
        """Send a request to multiple clients (SERVER mode only).

        Args:
            data: Request to broadcast.
            list_of_client: List of target client sockets.
            except_clients: Optional list of clients to exclude.

        Returns:
            True if all sends succeeded, False otherwise.
        """
        if self.is_client:
            if self.bus:
                self.bus.error("Broadcast not available in CLIENT mode")
            return False

        if not list_of_client:
            return True

        except_set = set(except_clients) if except_clients else set()
        compiled = data.compile()
        all_ok = True

        for client in list_of_client:
            if client in except_set:
                continue
            try:
                client.send(compiled)
                if self.bus:
                    self.bus.emit(MessageEvent.SENT, {
                        "type": data.type,
                        "length": len(data.content),
                        "mode": "broadcast",
                    })
            except (ConnectionResetError, BrokenPipeError):
                all_ok = False
            except Exception:
                all_ok = False

        return all_ok
