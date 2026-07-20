from __future__ import annotations

from threading import Lock
from typing import TYPE_CHECKING, Any, Optional

from ...network.message_buffer import MessageBuffer

if TYPE_CHECKING:
    from collections.abc import Callable

    from ...internal.bus import VeltixBus
    from ...server.client_info import ClientInfo
    from ...socket_core.base_socket import BaseSocket


class ClientEntry:
    """A single entry in the :class:`ClientsManager` registry.

    Bundles the client's unique ID, metadata, and message buffer together.

    Attributes:
        id: Unique server-assigned identifier for this client.
        info: The :class:`ClientInfo` holding connection and tag data.
        buffer: Per-client message buffer for TCP stream reassembly.
    """

    __slots__ = ("id", "info", "buffer")

    def __init__(self, id: int, info: ClientInfo, buffer: MessageBuffer):
        """Initialise a ClientEntry.

        Args:
            id: Unique server-assigned identifier.
            info: The client's metadata.
            buffer: The message buffer for this client.
        """
        self.id = id
        self.info = info
        self.buffer = buffer


class ClientsManager:
    """Thread-safe registry that tracks all connected clients.

    Each client is stored as a :class:`ClientEntry` keyed by a monotonically
    increasing integer ID. All public methods acquire an internal lock, making
    the manager safe for concurrent use from accept and receive threads.

    Attributes:
        max_message_size: Maximum allowed message size in bytes per client buffer.
        clients: Mapping of client IDs to their :class:`ClientEntry`.
        id_count: Counter for the next client ID to assign.
    """

    def __init__(self, max_message_size: Optional[int] = None, bus: Optional[VeltixBus] = None):
        """Initialise the ClientsManager.

        Args:
            max_message_size: Maximum message size in bytes (default 10 MB).
            bus: Optional event bus for structured logging.
        """
        self.max_message_size = max_message_size or (10 * 1024 * 1024)
        self.clients: dict[int, ClientEntry] = {}
        self._clients_lock = Lock()
        self.id_count = 0
        self._bus = bus

    def add_client(self, client_info: ClientInfo) -> int:
        """Register a new client and return its assigned ID.

        Args:
            client_info: The client's metadata to store.

        Returns:
            The unique integer ID assigned to this client.
        """
        with self._clients_lock:
            self.id_count += 1
            self.clients[self.id_count] = ClientEntry(
                id=self.id_count,
                info=client_info,
                buffer=MessageBuffer(self.max_message_size, bus=self._bus),
            )
            return self.id_count

    def remove_client(self, id_client: int) -> bool:
        """Remove a client from the registry.

        Args:
            id_client: The ID of the client to remove.

        Returns:
            True if the client was found and removed, False otherwise.
        """
        with self._clients_lock:
            entry = self.clients.pop(id_client, None)
            return entry is not None

    def get_client(self, id_client: int) -> Optional[ClientEntry]:
        """Look up a client by its ID.

        Args:
            id_client: The client ID to search for.

        Returns:
            The matching :class:`ClientEntry`, or ``None`` if not found.
        """
        with self._clients_lock:
            return self.clients.get(id_client)

    def has_client_id(self, client_id: int) -> bool:
        """Check whether a client with the given ID is registered.

        Args:
            client_id: The client ID to check.

        Returns:
            True if the client exists in the registry.
        """
        with self._clients_lock:
            return client_id in self.clients

    def has_client_info(self, client_info: ClientInfo) -> bool:
        """Check whether a :class:`ClientInfo` is registered.

        Args:
            client_info: The client info instance to search for.

        Returns:
            True if a matching entry exists.
        """
        with self._clients_lock:
            return any(client.info == client_info for client in self.clients.values())

    def get_all_clients(self) -> list[ClientEntry]:
        """Return a snapshot list of all registered clients.

        Returns:
            A new list containing every :class:`ClientEntry` in the registry.
        """
        with self._clients_lock:
            return list(self.clients.values())

    def iter_on_clients(self, func: Callable[[ClientEntry], None]) -> None:
        """Apply *func* to every registered client.

        A snapshot of the client list is taken under the lock so the
        callback may safely call methods that acquire the lock itself.

        Args:
            func: A callable that receives each :class:`ClientEntry`.
        """
        with self._clients_lock:
            clients_copy = self.clients.copy()
        for client in clients_copy.values():
            func(client)

    def count(self) -> int:
        """Return the number of registered clients.

        Returns:
            The current client count.
        """
        with self._clients_lock:
            return len(self.clients)

    def get_clients_by_tag(self, tag: str, value: Any = None) -> list[ClientEntry]:
        """Return clients that have a specific tag, optionally matching a value.

        Args:
            tag: The tag name to filter on.
            value: If provided, only clients whose tag value equals this are
                returned. If ``None``, any client possessing the tag matches.

        Returns:
            A list of matching :class:`ClientEntry` instances.
        """
        with self._clients_lock:
            if value is None:
                return [e for e in self.clients.values() if e.info.has_tag(tag)]
            return [e for e in self.clients.values() if e.info.get_tag(tag) == value]

    @staticmethod
    def to_sockets(entries: list[ClientEntry]) -> list[BaseSocket]:
        """Extract the raw socket from each client entry.

        Args:
            entries: A list of :class:`ClientEntry` instances.

        Returns:
            A list of :class:`BaseSocket` objects corresponding to each entry.
        """
        return [e.info.conn for e in entries]
