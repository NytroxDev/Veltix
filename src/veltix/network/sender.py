"""Message sending for Veltix."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Optional, Set, Union

from ..exceptions import SenderError
from ..internal.events import ErrorEvent, MessageEvent
from ..internal.mode import Mode

if TYPE_CHECKING:
    from enum import Enum

    from ..internal.bus import VeltixBus
    from ..server.client_info import ClientInfo
    from ..socket_core.base_socket import BaseSocket
    from .id_allocator import IDAllocator
    from .request import Request

_ClientLike = Union["BaseSocket", "ClientInfo"]


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
        get_all_clients: Optional[Callable[[], list[_ClientLike]]] = None,
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

    def _emit(self, event: Enum, data: dict) -> None:
        if self.bus:
            self.bus.emit(event, data)

    def _log_error(self, message: str) -> None:
        if self.bus:
            self.bus.error(message)

    def _resolve_target(self, client: Optional[BaseSocket]) -> Optional[BaseSocket]:
        return self.conn if self.is_client else client

    def _log_send_error(self, error: Exception, context: str = "send") -> None:
        self._emit(
            ErrorEvent.SEND,
            {"error": str(error), "mode": self.mode.value if self.mode else "unknown"},
        )
        if self.bus:
            self.bus.warning(f"Connection error during {context}: {type(error).__name__}")

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
        target = self._resolve_target(client)

        if target is None:
            self._log_error(
                "No connection available" if self.is_client else "No client socket provided"
            )
            return False

        if data.request_id is None and self._id_allocator is not None:
            data.request_id = self._id_allocator.allocate()

        try:
            target.send(data.compile())
            self._emit(
                MessageEvent.SENT,
                {
                    "type": data.type,
                    "length": len(data.content),
                    "mode": "client" if self.is_client else "server",
                },
            )
            return True
        except (ConnectionResetError, BrokenPipeError) as e:
            self._log_send_error(e)
            if self.is_client:
                self.conn = None
            return False
        except Exception as e:
            self._log_error(f"Unexpected send error: {type(e).__name__}: {e}")
            return False

    @staticmethod
    def _resolve_socket(client: _ClientLike) -> BaseSocket:
        from ..server.client_info import ClientInfo

        return client.conn if isinstance(client, ClientInfo) else client

    def _build_exclude_set(self, except_clients: Optional[list[_ClientLike]]) -> set[BaseSocket]:
        if not except_clients:
            return set()
        return {self._resolve_socket(c) for c in except_clients}

    def broadcast(
        self,
        data: Request,
        list_of_client: Optional[list[_ClientLike]] = None,
        except_clients: Optional[list[_ClientLike]] = None,
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
            self._log_error("Broadcast not available in CLIENT mode")
            return False

        if list_of_client is None and self._get_all_clients is None:
            self._log_error("No client list provided and no get_all_clients callback")
            return False

        if list_of_client is None:
            list_of_client = self._get_all_clients()  # type: ignore[misc]

        if not list_of_client:
            return True

        exclude = self._build_exclude_set(except_clients)
        compiled = data.compile()
        all_ok = True

        for client in list_of_client:
            socket = self._resolve_socket(client)
            if socket in exclude:
                continue
            try:
                socket.send(compiled)
                self._emit(
                    MessageEvent.SENT,
                    {
                        "type": data.type,
                        "length": len(data.content),
                        "mode": "broadcast",
                    },
                )
            except (ConnectionResetError, BrokenPipeError) as e:
                self._log_send_error(e, context="broadcast")
                all_ok = False
            except Exception as e:
                self._log_error(f"Unexpected broadcast error: {type(e).__name__}: {e}")
                all_ok = False

        return all_ok
