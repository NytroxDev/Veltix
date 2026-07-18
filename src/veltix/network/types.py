"""Message type system for Veltix protocol."""

from __future__ import annotations

import threading
from typing import Optional, Union

from ..exceptions import MessageTypeError

_USER_CODE_MIN = 200
_USER_CODE_MAX = 9999
_PLUGIN_CODE_MIN = 10000
_PROTOCOL_MAX = 65535


class MessageTypeRegistry:
    """Registry mapping message codes to MessageType instances."""

    _registry: dict[int, MessageType] = {}
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def register(cls, msg_type: MessageType) -> None:
        with cls._lock:
            if msg_type.code in cls._registry:
                existing = cls._registry[msg_type.code]
                if msg_type.code < _USER_CODE_MIN:
                    raise MessageTypeError(
                        f"Code {msg_type.code} is reserved for system messages "
                        f"(0-{_USER_CODE_MIN - 1}). "
                        f"'{existing.name}' is already registered there."
                    )
                raise MessageTypeError(
                    f"Code {msg_type.code} already registered as '{existing.name}'"
                )
            cls._registry[msg_type.code] = msg_type

    @classmethod
    def _next_code(cls) -> int:
        """Find the next available user code (200-9999)."""
        for code in range(_USER_CODE_MIN, _USER_CODE_MAX + 1):
            if code not in cls._registry:
                return code
        raise MessageTypeError(f"No available codes in range {_USER_CODE_MIN}-{_USER_CODE_MAX}")

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
    - 0-199:    System messages (reserved)
    - 200-9999: User application messages (auto-allocatable)
    - 10000+:   Plugin/extension messages
    - Max:      65535 (uint16 protocol limit)

    Usage:
        MessageType(200, "chat")        # explicit code
        MessageType("chat")             # auto-allocate code
        MessageType(name="chat")        # auto-allocate code
    """

    __slots__ = ("code", "name", "description")

    def __init__(
        self,
        code: Union[int, str, None] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        *,
        _system: bool = False,
    ) -> None:
        # Handle MessageType("chat") — first arg is a string (the name)
        if isinstance(code, str):
            if name is not None:
                raise MessageTypeError(
                    "Cannot pass a name as both first argument and 'name' keyword"
                )
            name = code
            code = None

        # Auto-allocate code when not provided
        if code is None:
            if _system:
                raise MessageTypeError("System messages must have an explicit code")
            code = MessageTypeRegistry._next_code()

        if not isinstance(code, int):
            raise MessageTypeError(f"Code must be an int, str, or None, got: {type(code).__name__}")

        if not (0 <= code <= _PROTOCOL_MAX):
            raise MessageTypeError(f"Code must be between 0 and {_PROTOCOL_MAX}, got: {code}")

        if code < _USER_CODE_MIN and not _system:
            raise MessageTypeError(
                f"Code {code} is reserved for system messages "
                f"(0-{_USER_CODE_MIN - 1}). "
                f"Use a code between {_USER_CODE_MIN} and {_USER_CODE_MAX} "
                f"for user messages."
            )

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
