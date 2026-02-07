from enum import Enum
from socket import socket
from typing import Optional

from .request import Request
from ..exceptions import SenderError


class Mode(Enum):
    """
    Sender mode enumeration.
    
    Attributes:
        SERVER: Server mode (can broadcast to multiple clients)
        CLIENT: Client mode (can only send to server)
    """
    SERVER = "server"
    CLIENT = "client"


class Sender:
    """
    Handles sending data over TCP connections.
    
    Can operate in client mode (single connection) or server mode (multiple connections).
    """
    def __init__(self, mode: Mode, conn: Optional[socket] = None) -> None:
        """
        Initialize the sender.
        
        Args:
            mode: Operating mode (SERVER or CLIENT)
            conn: Socket connection (required for CLIENT mode)
            
        Raises:
            SenderError: If mode is CLIENT and no connection provided
        """
        if mode == Mode.CLIENT and not conn:
            raise SenderError("You must provide conn argument if mode = CLIENT")

        self.mode = mode
        self.is_client = mode == Mode.CLIENT
        self.conn: Optional[socket] = conn

    def send(self, data: Request, client: Optional[socket] = None) -> bool:
        """
        Send data to a client or server.
        
        Args:
            data: Request object to send
            client: Target client socket (required for SERVER mode)
            
        Returns:
            True if send succeeded, False otherwise
        """
        if self.is_client:
            if not self.conn:
                return False
            try:
                self.conn.sendall(data.compile())
                return True
            except:
                return False
        else:
            if not client:
                return False
            try:
                client.sendall(data.compile())
                return True
            except:
                return False

    def broadcast(self, data: Request, list_of_client: list[socket]) -> bool:
        """
        Broadcast data to multiple clients (SERVER mode only).
        
        Args:
            data: Request object to broadcast
            list_of_client: List of client sockets to send to
            
        Returns:
            True if all sends succeeded, False if any failed
        """
        if self.is_client:
            return False

        result = []

        for client in list_of_client:
            res = self.send(data=data, client=client)
            result.append(res[0] if isinstance(res, tuple) else res)

        return all(result)
