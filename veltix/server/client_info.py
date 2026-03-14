import dataclasses
from typing import Any, Optional

from ..socket.base_socket import BaseSocket


@dataclasses.dataclass(slots=False)
class ClientInfo:
    """
    Information about a connected client.

    Attributes:
        conn:           Socket connection to the client.
        addr:           Client address tuple (host, port).
        ip:             Client IP address (property).
        port:           Client port (property).
        thread_id:      Internal thread identifier.
        handshake_done: Whether the handshake has been completed.
        tags:           Key-value store for arbitrary client metadata.
                        Values default to None when added without an explicit value.
    """

    conn: BaseSocket
    addr: tuple[str, int]
    thread_id: int
    handshake_done: bool
    tags: dict[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def ip(self) -> str:
        """Client IP address."""
        return self.addr[0]

    @property
    def port(self) -> int:
        """Client port."""
        return self.addr[1]

    def add_tag(self, name: str, value: Optional[Any] = None) -> bool:
        """
        Add a tag to the client.

        Does nothing if the tag already exists.

        Args:
            name:  Tag name.
            value: Optional value associated with the tag (default: None).

        Returns:
            True if the tag was added, False if it already existed.
        """
        if name in self.tags:
            return False
        self.tags[name] = value
        return True

    def has_tag(self, name: str) -> bool:
        """
        Check whether the client has a specific tag.

        Args:
            name: Tag name to look up.

        Returns:
            True if the tag exists, False otherwise.
        """
        return name in self.tags

    def has_all_tags(self, names: list[str]) -> bool:
        """
        Check whether the client has all the specified tags.

        Args:
            names: List of tag names that must all be present.

        Returns:
            True if every tag in the list exists, False otherwise.
        """
        res = []
        for name in names:
            res.append(self.has_tag(name))
        return all(res)

    def has_any_tags(self, names: list[str]) -> bool:
        """
        Check whether the client has at least one of the specified tags.

        Args:
            names: List of tag names to check.

        Returns:
            True if at least one tag in the list exists, False otherwise.
        """
        res = []
        for name in names:
            res.append(self.has_tag(name))
        return any(res)

    def get_tag(self, name: str) -> Optional[Any]:
        """
        Retrieve the value associated with a tag.

        Args:
            name: Tag name to look up.

        Returns:
            The tag value, or None if the tag does not exist.
        """
        return self.tags.get(name)

    def remove_tag(self, name: str) -> bool:
        """
        Remove a tag from the client.

        Does nothing if the tag does not exist.

        Args:
            name: Tag name to remove.

        Returns:
            True if the tag was removed, False if it did not exist.
        """
        if not self.has_tag(name):
            return False
        self.tags.pop(name)
        return True

    def clear_tags(self) -> None:
        """Remove all tags from the client."""
        self.tags.clear()
