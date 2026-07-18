"""Base socket abstract class for Veltix."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    from ..internal.bus import VeltixBus
    from ..network.id_allocator import ClientAllocator
    from .managers.clients_manager import ClientEntry, ClientsManager


class SocketEvents(Enum):
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    RECV = "recv"


class BaseSocket(ABC):
    client_manager: ClientsManager
    handshake_timeout: float
    bus: VeltixBus
    client_allocator: Optional[ClientAllocator]

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
