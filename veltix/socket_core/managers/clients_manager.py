from __future__ import annotations

from threading import Lock
from typing import TYPE_CHECKING, Optional

from ...network.message_buffer import MessageBuffer

if TYPE_CHECKING:
    import socket
    from collections.abc import Callable

    from ...server.client_info import ClientInfo


class ClientEntry:
    __slots__ = ("id", "info", "buffer")

    def __init__(self, id: int, info: ClientInfo, buffer: MessageBuffer):
        self.id = id
        self.info = info
        self.buffer = buffer


class ClientsManager:
    def __init__(self, max_message_size: Optional[int] = None):
        self.max_message_size = max_message_size or (10 * 1024 * 1024)
        self.clients: dict[int, ClientEntry] = {}
        self._clients_lock = Lock()
        self.id_count = 0

    def add_client(self, client_info: ClientInfo) -> int:
        with self._clients_lock:
            self.id_count += 1
            self.clients[self.id_count] = ClientEntry(
                id=self.id_count, info=client_info, buffer=MessageBuffer(self.max_message_size)
            )
            return self.id_count

    def remove_client(self, id_client: int) -> bool:
        with self._clients_lock:
            entry = self.clients.pop(id_client, None)
            return entry is not None

    def get_client(self, id_client: int) -> Optional[ClientEntry]:
        with self._clients_lock:
            return self.clients.get(id_client)

    def has_client_id(self, client_id: int) -> bool:
        with self._clients_lock:
            return client_id in self.clients

    def has_client_info(self, client_info: ClientInfo) -> bool:
        with self._clients_lock:
            return any(client.info == client_info for client in self.clients.values())

    def get_all_clients(self) -> list[ClientEntry]:
        with self._clients_lock:
            return list(self.clients.values())

    def iter_on_clients(self, func: Callable[[ClientEntry], None]):
        with self._clients_lock:
            clients_copy = self.clients.copy()
        for client in clients_copy.values():
            func(client)

    def count(self) -> int:
        with self._clients_lock:
            return len(self.clients)

    def get_clients_by_tag(self, tag: str, value=None) -> list[ClientEntry]:
        """Get all clients that have a specific tag, optionally matching a value."""
        with self._clients_lock:
            if value is None:
                return [e for e in self.clients.values() if e.info.has_tag(tag)]
            return [e for e in self.clients.values() if e.info.get_tag(tag) == value]

    @staticmethod
    def to_sockets(entries: list[ClientEntry]) -> list[socket.socket]:
        """Convert a list of ClientEntry to a list of sockets (entry.info.conn)."""
        return [e.info.conn for e in entries]
