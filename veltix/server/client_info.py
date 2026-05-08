from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ..socket_core.base_socket import BaseSocket


class ClientInfo:
    __slots__ = ("conn", "addr", "thread_id", "handshake_done", "tags")

    def __init__(
        self,
        conn: BaseSocket,
        addr: tuple[str, int],
        thread_id: int,
        handshake_done: bool = False,
    ) -> None:
        self.conn = conn
        self.addr = addr
        self.thread_id = thread_id
        self.handshake_done = handshake_done
        self.tags: dict[str, Any] = {}

    @property
    def ip(self) -> str:
        return self.addr[0]

    @property
    def port(self) -> int:
        return self.addr[1]

    def add_tag(self, name: str, value: Optional[Any] = None) -> bool:
        if name in self.tags:
            return False
        self.tags[name] = value
        return True

    def has_tag(self, name: str) -> bool:
        return name in self.tags

    def has_all_tags(self, names: list[str]) -> bool:
        return all(self.has_tag(name) for name in names)

    def has_any_tags(self, names: list[str]) -> bool:
        return any(self.has_tag(name) for name in names)

    def get_tag(self, name: str) -> Optional[Any]:
        return self.tags.get(name)

    def remove_tag(self, name: str) -> bool:
        if not self.has_tag(name):
            return False
        self.tags.pop(name)
        return True

    def clear_tags(self) -> None:
        self.tags.clear()
