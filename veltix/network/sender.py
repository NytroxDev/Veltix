"""Message sending for Veltix."""

from __future__ import annotations

from typing import Optional, Union

from ..exceptions import SenderError
from ..internal.mode import Mode
from ..logger.core import Logger
from ..socket_core.base_socket import BaseSocket
from .request import Request


class Sender:
    """
    Sends messages over TCP in CLIENT or SERVER mode.

    CLIENT: single server connection.
    SERVER: sends to individual clients or broadcasts.
    """

    def __init__(self, mode: Union[Mode, str], conn: Optional[BaseSocket] = None) -> None:
        self._logger = Logger.get_instance()

        if mode == Mode.CLIENT and conn is None:
            raise SenderError("CLIENT mode requires a socket connection")

        self.mode = mode
        self.is_client = mode == Mode.CLIENT
        self.conn: Optional[BaseSocket] = conn

    def send(self, data: Request, client: Optional[BaseSocket] = None) -> bool:
        target = self.conn if self.is_client else client

        if target is None:
            self._logger.error(
                "No connection available" if self.is_client else "No client socket provided"
            )
            return False

        try:
            target.send(data.compile())
            return True
        except (ConnectionResetError, BrokenPipeError) as e:
            self._logger.warning(f"Connection error during send: {type(e).__name__}")
            return False
        except Exception as e:
            self._logger.error(f"Unexpected send error: {type(e).__name__}: {e}")
            return False

    def broadcast(
        self,
        data: Request,
        list_of_client: list[BaseSocket],
        except_clients: Optional[list[BaseSocket]] = None,
    ) -> bool:
        if self.is_client:
            self._logger.error("Broadcast not available in CLIENT mode")
            return False

        if not list_of_client:
            return True

        except_set = set(except_clients) if except_clients else set()
        all_ok = True

        for client in list_of_client:
            if client in except_set:
                continue
            if not self.send(data=data, client=client):
                all_ok = False

        return all_ok
