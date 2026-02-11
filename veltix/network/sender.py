"""Message sending functionality for Veltix."""

from enum import Enum
from socket import error as socket_error
from socket import socket
from typing import Optional

from ..exceptions import SenderError
from ..logger.core import Logger
from .request import Request


class Mode(Enum):
    """
    Sender operating mode.

    Attributes:
        SERVER: Can send to multiple clients (broadcast)
        CLIENT: Can only send to server
    """

    SERVER = "server"
    CLIENT = "client"


class Sender:
    """
    Handles sending data over TCP connections.

    Can operate in CLIENT mode (single server connection) or
    SERVER mode (multiple client connections).
    """

    def __init__(self, mode: Mode, conn: Optional[socket] = None) -> None:
        """
        Initialize the sender.

        Args:
            mode: Operating mode (SERVER or CLIENT)
            conn: Socket connection (required for CLIENT mode)

        Raises:
            SenderError: If CLIENT mode without connection
        """
        # Logger setup
        self._logger = Logger.get_instance()

        if mode == Mode.CLIENT and conn is None:
            self._logger.error("CLIENT mode requires a socket connection")
            raise SenderError("CLIENT mode requires a socket connection")

        self.mode = mode
        self.is_client = mode == Mode.CLIENT
        self.conn: Optional[socket] = conn

        self._logger.debug(f"Sender initialized in {mode.value} mode")

    def send(self, data: Request, client: Optional[socket] = None) -> bool:
        """
        Send a request to a client or server.

        Args:
            data: Request object to send
            client: Target client socket (required for SERVER mode, ignored for CLIENT)

        Returns:
            True if send succeeded, False otherwise
        """
        target = self.conn if self.is_client else client

        if target is None:
            if self.is_client:
                self._logger.error("No connection available in CLIENT mode")
            else:
                self._logger.error("No client socket provided in SERVER mode")
            return False

        try:
            compiled_data = data.compile()
            target.sendall(compiled_data)
            self._logger.debug(
                f"Sent {len(compiled_data)} bytes via {self.mode.value} (request_id: {data.request_id})"
            )
            return True
        except (ConnectionResetError, BrokenPipeError) as e:
            self._logger.warning(f"Connection error during send: {type(e).__name__}")
            return False
        except Exception as e:
            self._logger.error(f"Unexpected error during send: {type(e).__name__}: {e}")
            return False

    def broadcast(
        self,
        data: Request,
        list_of_client: list[socket],
        except_clients: list[socket] = None,
    ) -> bool:
        """
        Broadcast data to multiple clients (SERVER mode only).

        Args:
            data: Request object to broadcast
            list_of_client: List of client sockets
            except_clients: List of client sockets to exclude from broadcast

        Returns:
            True if ALL sends succeeded, False if ANY failed
        """
        if self.is_client:
            self._logger.error("Broadcast not available in CLIENT mode")
            return False

        if not list_of_client:
            self._logger.debug("Broadcast called with empty client list")
            return True  # No clients = vacuous success

        self._logger.debug(
            f"Broadcasting to {len(list_of_client)} clients (request_id: {data.request_id})"
        )

        # Convert except_clients to set for O(1) lookup

        except_set = set(except_clients) if except_clients else set()
        results = []
        failed_count = 0
        except_count = 0

        for i, client in enumerate(list_of_client):
            if client in except_set:
                except_count += 1
                try:
                    peer = client.getpeername()
                    self._logger.debug(f"Excluding client {peer} from broadcast")
                except (OSError, socket_error):
                    self._logger.debug("Excluding client from broadcast")
                continue

            success = self.send(data=data, client=client)
            results.append(success)
            if not success:
                failed_count += 1
                self._logger.warning(
                    f"Failed to send to client {i + 1}/{len(list_of_client)}"
                )

        total_sent = len(list_of_client) - except_count
        if total_sent > 0:
            success_rate = (total_sent - failed_count) / total_sent
        else:
            success_rate = 1.0  # All clients excluded = 100% success

        self._logger.info(
            f"Broadcast completed: {total_sent - failed_count}/{total_sent} successful ({success_rate:.1%}) - {except_count} excluded"
        )

        return all(results)
