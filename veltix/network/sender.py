"""Message sending for Veltix."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from ..exceptions import SenderError
from ..internal.mode import Mode
from ..logger.core import Logger

if TYPE_CHECKING:
    from ..socket_core.base_socket import BaseSocket
    from .request import Request


class Sender:
    """
    Sends messages over TCP in CLIENT or SERVER mode.

    CLIENT: single server connection.
    SERVER: sends to individual clients or broadcasts.
    """

    def __init__(self, mode: Union[Mode, str], conn: Optional[BaseSocket] = None) -> None:
        """Initialise l'expéditeur avec un mode et une connexion optionnelle.

        Args:
            mode: Mode CLIENT ou SERVER.
            conn: Socket de connexion (obligatoire en mode CLIENT).

        Raises:
            SenderError: Si le mode est CLIENT sans connexion fournie.
        """
        self._logger = Logger.get_instance()

        if isinstance(mode, str):
            mode = Mode(mode)

        if mode == Mode.CLIENT and conn is None:
            raise SenderError("CLIENT mode requires a socket connection")

        self.mode = mode
        self.is_client = mode == Mode.CLIENT
        self.conn: Optional[BaseSocket] = conn

    def send(self, data: Request, client: Optional[BaseSocket] = None) -> bool:
        """Envoie une requête sur le réseau.

        En mode CLIENT, utilise la connexion interne.
        En mode SERVER, utilise le socket client fourni.

        Args:
            data: Requête à envoyer.
            client: Socket client destinataire (obligatoire en mode SERVER).

        Returns:
            True si l'envoi a réussi, False sinon.
        """
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
        """Envoie une requête à plusieurs clients (mode SERVER uniquement).

        Args:
            data: Requête à diffuser.
            list_of_client: Liste des sockets clients destinataires.
            except_clients: Liste optionnelle de clients à exclure.

        Returns:
            True si tous les envois ont réussi, False sinon.
        """
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
