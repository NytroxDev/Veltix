"""Base socket abstract class for Veltix."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable, Union

from .managers.clients_manager import ClientEntry, ClientsManager


class SocketEvents(Enum):
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    RECV = "recv"


class BaseSocket(ABC):
    client_manager: ClientsManager
    handshake_timeout: float

    @abstractmethod
    def set_callback(self, event: SocketEvents, callback: Callable) -> bool: ...

    @abstractmethod
    def send(self, data: bytes) -> bool: ...

    @abstractmethod
    def close(self) -> bool: ...

    @abstractmethod
    def bind(
        self, host: str, port: int, max_client: int, buffer_size: int, timeout: float
    ) -> bool: ...

    @abstractmethod
    def connect(self, host: str, port: int, buffer_size: int, timeout: float) -> bool: ...

    @abstractmethod
    def settimeout(self, timeout: float) -> bool: ...

    @abstractmethod
    def close_client(self, client: Union[ClientEntry, int]) -> bool: ...

    @abstractmethod
    def disconnect(self, timeout: float) -> bool: ...

    @abstractmethod
    def recv(self, buf_size: int) -> bytes: ...
