"""Message type system for Veltix protocol."""

from __future__ import annotations

import threading
from typing import Optional

from ..exceptions import MessageTypeError


class MessageTypeRegistry:
    """Registry mapping message codes to MessageType instances."""

    _registry: dict[int, MessageType] = {}
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def register(cls, msg_type: MessageType) -> None:
        with cls._lock:
            if msg_type.code in cls._registry:
                existing = cls._registry[msg_type.code]
                raise MessageTypeError(
                    f"Code {msg_type.code} already registered as '{existing.name}'"
                )
            cls._registry[msg_type.code] = msg_type

    @classmethod
    def get(cls, code: int) -> Optional[MessageType]:
        with cls._lock:
            return cls._registry.get(code)

    @classmethod
    def list_all(cls) -> list[MessageType]:
        with cls._lock:
            return list(cls._registry.values())


class MessageType:
    """
    Defines a message type in the Veltix protocol.

    Code ranges:
    - 0-199:   System messages (reserved)
    - 200-499: User application messages
    - 500+:    Plugin/extension messages
    """

    __slots__ = ("code", "name", "description")

    def __init__(
        self, code: int, name: Optional[str] = None, description: Optional[str] = None
    ) -> None:
        if not (0 <= code <= 65535):
            raise MessageTypeError(f"Code must be between 0 and 65535, got: {code}")

        self.code: int = code
        self.name: str = name or f"type_{code}"
        self.description: Optional[str] = description

        MessageTypeRegistry.register(self)

    def __repr__(self) -> str:
        return f"MessageType(code={self.code}, name='{self.name}')"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MessageType):
            return NotImplemented
        return self.code == other.code

    def __hash__(self) -> int:
        return hash(self.code)
