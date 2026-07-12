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
        with self._tags_lock:
            return dict(self._tags)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ClientInfo):
            return NotImplemented
        return self._id == other._id

    def __hash__(self) -> int:
        return hash(self._id)

    @property
    def ip(self) -> str:
        return self.addr[0]

    @property
    def port(self) -> int:
        return self.addr[1]

    def add_tag(self, name: str, value: Optional[Any] = None) -> bool:
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
        with self._tags_lock:
            return name in self._tags

    def has_all_tags(self, names: list[str]) -> bool:
        with self._tags_lock:
            return all(name in self._tags for name in names)

    def has_any_tags(self, names: list[str]) -> bool:
        with self._tags_lock:
            return any(name in self._tags for name in names)

    def get_tag(self, name: str) -> Optional[Any]:
        with self._tags_lock:
            return self._tags.get(name)

    def remove_tag(self, name: str) -> bool:
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
        with self._tags_lock:
            self._tags.clear()
        if self._bus:
            self._bus.emit(
                ClientEvent.TAG_CLEARED,
                {
                    "client": self.addr,
                },
            )
