from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, Optional

from ..internal.events import ClientEvent

if TYPE_CHECKING:
    from ..internal.bus import VeltixBus
    from ..socket_core.base_socket import BaseSocket

_id_lock = threading.Lock()
_next_id = 0


def _generate_id() -> int:
    global _next_id
    with _id_lock:
        _next_id += 1
        return _next_id


class ClientInfo:
    """Represents a connected client on the server side.

    Holds the socket connection, address, metadata, and a thread-safe tag store.
    Each instance is assigned a unique auto-incrementing ID and is comparable
    by identity (``==`` and ``hash`` are based on that ID).

    Attributes:
        conn: The underlying socket connection for this client.
        addr: A ``(host, port)`` tuple representing the client address.
        thread_id: The identifier of the thread managing this client.
        handshake_done: Whether the handshake has been completed.
        id_offset: Offset applied to request IDs for this client.
    """

    __slots__ = (
        "_id",
        "conn",
        "addr",
        "thread_id",
        "handshake_done",
        "id_offset",
        "_tags",
        "_tags_lock",
        "_bus",
    )

    def __init__(
        self,
        conn: BaseSocket,
        addr: tuple[str, int],
        thread_id: int,
        handshake_done: bool = False,
        bus: Optional[VeltixBus] = None,
        id_offset: int = 0,
    ) -> None:
        """Initialise a new ClientInfo.

        Args:
            conn: The socket connection for this client.
            addr: ``(host, port)`` tuple of the remote address.
            thread_id: Identifier of the thread managing this client.
            handshake_done: Whether the handshake is already complete.
            bus: Optional event bus for emitting client events.
            id_offset: Offset applied to request IDs for this client.
        """
        self._id = _generate_id()
        self.conn = conn
        self.addr = addr
        self.thread_id = thread_id
        self.handshake_done = handshake_done
        self.id_offset = id_offset
        self._tags: dict[str, Any] = {}
        self._tags_lock = threading.Lock()
        self._bus = bus

    @property
    def tags(self) -> dict[str, Any]:
        """Return a copy of all tags attached to this client.

        Returns:
            A dictionary of tag names to their values.
        """
        with self._tags_lock:
            return dict(self._tags)

    def __eq__(self, other: object) -> bool:
        """Check equality by unique client ID.

        Args:
            other: The object to compare against.

        Returns:
            True if both instances share the same client ID.
        """
        if not isinstance(other, ClientInfo):
            return NotImplemented
        return self._id == other._id

    def __hash__(self) -> int:
        """Return the hash based on the unique client ID.

        Returns:
            An integer hash value.
        """
        return hash(self._id)

    @property
    def ip(self) -> str:
        """Return the client's IP address.

        Returns:
            The IP address as a string.
        """
        return self.addr[0]

    @property
    def port(self) -> int:
        """Return the client's port number.

        Returns:
            The port as an integer.
        """
        return self.addr[1]

    def add_tag(self, name: str, value: Optional[Any] = None) -> bool:
        """Add a tag to this client.

        Tags are key-value pairs used for filtering and grouping clients
        (e.g., channel membership, role, etc.). Adding a tag that already
        exists will silently fail and return ``False``.

        Args:
            name: The tag name.
            value: The tag value (defaults to ``None``).

        Returns:
            True if the tag was added, False if it already existed.
        """
        with self._tags_lock:
            if name in self._tags:
                return False
            self._tags[name] = value
        if self._bus:
            self._bus.emit(
                ClientEvent.TAG_ADDED,
                {
                    "client": self.addr,
                    "tag": name,
                    "value": value,
                },
            )
        return True

    def has_tag(self, name: str) -> bool:
        """Check whether this client has a specific tag.

        Args:
            name: The tag name to look up.

        Returns:
            True if the tag exists on this client.
        """
        with self._tags_lock:
            return name in self._tags

    def has_all_tags(self, names: list[str]) -> bool:
        """Check whether this client has all of the given tags.

        Args:
            names: A list of tag names to check.

        Returns:
            True if every name in *names* is present as a tag.
        """
        with self._tags_lock:
            return all(name in self._tags for name in names)

    def has_any_tags(self, names: list[str]) -> bool:
        """Check whether this client has at least one of the given tags.

        Args:
            names: A list of tag names to check.

        Returns:
            True if at least one name in *names* is present as a tag.
        """
        with self._tags_lock:
            return any(name in self._tags for name in names)

    def get_tag(self, name: str) -> Optional[Any]:
        """Return the value of a tag, or ``None`` if it does not exist.

        Args:
            name: The tag name to retrieve.

        Returns:
            The tag's value, or ``None`` if the tag is not set.
        """
        with self._tags_lock:
            return self._tags.get(name)

    def remove_tag(self, name: str) -> bool:
        """Remove a tag from this client.

        Args:
            name: The tag name to remove.

        Returns:
            True if the tag was removed, False if it did not exist.
        """
        with self._tags_lock:
            if name not in self._tags:
                return False
            self._tags.pop(name)
        if self._bus:
            self._bus.emit(
                ClientEvent.TAG_REMOVED,
                {
                    "client": self.addr,
                    "tag": name,
                },
            )
        return True

    def clear_tags(self) -> None:
        """Remove all tags from this client."""
        with self._tags_lock:
            self._tags.clear()
        if self._bus:
            self._bus.emit(
                ClientEvent.TAG_CLEARED,
                {
                    "client": self.addr,
                },
            )
