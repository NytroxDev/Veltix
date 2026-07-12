"""Message sending for Veltix."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional, Union

from ..exceptions import SenderError
from ..internal.events import ErrorEvent, MessageEvent
from ..internal.mode import Mode

if TYPE_CHECKING:
    from ..internal.bus import VeltixBus
    from ..socket_core.base_socket import BaseSocket
    from .id_allocator import IDAllocator
    from .request import Request


class Sender:
    """
    Sends messages over TCP in CLIENT or SERVER mode.

    CLIENT: single server connection.
    SERVER: sends to individual clients or broadcasts.
    """

    def __init__(
        self,
        mode: Union[Mode, str],
        conn: Optional[BaseSocket] = None,
        bus: Optional[VeltixBus] = None,
        get_all_clients: Optional[Callable[[], list]] = None,
        id_allocator: Optional[IDAllocator] = None,
    ) -> None:
        """Initialize the sender with a mode and an optional connection.

        Args:
            mode: CLIENT or SERVER mode.
            conn: Connection socket (required in CLIENT mode).
            bus: Event bus instance.
            get_all_clients: Callable returning all connected client sockets (SERVER mode).
            id_allocator: ID allocator for auto-assigning request IDs.
        """
        self.bus = bus
        self._id_allocator = id_allocator

        if isinstance(mode, str):
            mode = Mode(mode)

        if mode == Mode.CLIENT and conn is None:
            raise SenderError("CLIENT mode requires a socket connection")

        self.mode = mode
        self.is_client = mode == Mode.CLIENT
        self.conn: Optional[BaseSocket] = conn
        self._get_all_clients = get_all_clients

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

        if data.request_id is None and self._id_allocator is not None:
            data.request_id = self._id_allocator.allocate()

        try:
            target.send(data.compile())
            if self.bus:
                self.bus.emit(
                    MessageEvent.SENT,
                    {
                        "type": data.type,
                        "length": len(data.content),
                        "mode": "client" if self.is_client else "server",
                    },
                )
            return True
        except (ConnectionResetError, BrokenPipeError) as e:
            if self.bus:
                self.bus.emit(
                    ErrorEvent.SEND,
                    {"error": str(e), "mode": self.mode.value if self.mode else "unknown"},
                )
                self.bus.warning(f"Connection error during send: {type(e).__name__}")
            if self.is_client:
                self.conn = None
            return False
        except Exception as e:
            if self.bus:
                self.bus.emit(
                    ErrorEvent.SEND,
                    {"error": str(e), "mode": self.mode.value if self.mode else "unknown"},
                )
                self.bus.error(f"Unexpected send error: {type(e).__name__}: {e}")
            return False

    @staticmethod
    def _resolve_socket(client: BaseSocket) -> BaseSocket:
        """Extract the socket from a BaseSocket or ClientInfo."""
        from ..server.client_info import ClientInfo

        return client.conn if isinstance(client, ClientInfo) else client

    def broadcast(
        self,
        data: Request,
        list_of_client: Optional[list] = None,
        except_clients: Optional[list] = None,
    ) -> bool:
        """Send a request to multiple clients (SERVER mode only).

        Args:
            data: Request to broadcast.
            list_of_client: Target clients. Accepts BaseSocket or ClientInfo. Defaults to all connected clients.
            except_clients: Clients to exclude. Accepts BaseSocket or ClientInfo.

        Returns:
            True if all sends succeeded, False otherwise.
        """
        if self.is_client:
            if self.bus:
                self.bus.error("Broadcast not available in CLIENT mode")
            return False

        if list_of_client is None:
            if self._get_all_clients is None:
                if self.bus:
                    self.bus.error("No client list provided and no get_all_clients callback")
                return False
            list_of_client = self._get_all_clients()

        if not list_of_client:
            return True

        except_set = {self._resolve_socket(c) for c in except_clients} if except_clients else set()
        compiled = data.compile()
        all_ok = True

        for client in list_of_client:
            socket = self._resolve_socket(client)
            if socket in except_set:
                continue
            try:
                socket.send(compiled)
                if self.bus:
                    self.bus.emit(
                        MessageEvent.SENT,
                        {
                            "type": data.type,
                            "length": len(data.content),
                            "mode": "broadcast",
                        },
                    )
            except (ConnectionResetError, BrokenPipeError):
                all_ok = False
            except Exception:
                all_ok = False

        return all_ok
