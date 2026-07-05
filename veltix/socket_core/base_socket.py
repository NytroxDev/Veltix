"""Base socket protocol for Veltix."""

from enum import Enum
from typing import Callable, Protocol, Union, runtime_checkable

from .managers.clients_manager import ClientEntry, ClientsManager


class SocketEvents(Enum):
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    RECV = "recv"


@runtime_checkable
class BaseSocket(Protocol):
    client_manager: ClientsManager
    handshake_timeout: float

    def set_callback(self, event: SocketEvents, callback: Callable) -> bool: ...
    def send(self, data: bytes) -> bool: ...
    def close(self) -> bool: ...
    def bind(
        self, host: str, port: int, max_client: int, buffer_size: int, timeout: float
    ) -> bool: ...
    def connect(self, host: str, port: int, buffer_size: int, timeout: float) -> bool: ...
    def settimeout(self, timeout: float) -> bool: ...
    def close_client(self, client: Union[ClientEntry, int]) -> bool: ...
    def disconnect(self, timeout: float) -> bool: ...
    def recv(self, buf_size: int) -> bytes: ...
