"""Message type system for Veltix protocol."""

from __future__ import annotations

import threading

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
                    f"Code {msg_type.code} already registered as '{existing.name}'. "
                    'Fix: use a different code or MessageType("chat") to '
                    "auto-allocate an unused one."
                )
            cls._registry[msg_type.code] = msg_type

    @classmethod
    def allocate(cls, msg_type: MessageType) -> int:
        """Reserve and register *msg_type* under the next free user code.

        Allocation and registration happen under a single lock acquisition so
        concurrent auto-allocating constructors never race for the same code.

        Args:
            msg_type: MessageType instance to allocate a code for.

        Returns:
            The allocated user code.

        Raises:
            MessageTypeError: If no user code is free in the range.
        """
        with cls._lock:
            for code in range(_USER_CODE_MIN, _USER_CODE_MAX + 1):
                if code not in cls._registry:
                    cls._registry[code] = msg_type
                    msg_type.code = code
                    return code
            raise MessageTypeError(f"No available codes in range {_USER_CODE_MIN}-{_USER_CODE_MAX}")

    @classmethod
    def get(cls, code: int) -> MessageType | None:
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
        code: int | str | None = None,
        name: str | None = None,
        description: str | None = None,
        *,
        _system: bool = False,
    ) -> None:
        # Handle MessageType("chat") - first arg is a string (the name)
        if isinstance(code, str):
            if name is not None:
                raise MessageTypeError(
                    "Cannot pass a name as both first argument and 'name' keyword. "
                    'Fix: use one of MessageType("chat"), MessageType(name="chat") '
                    'or MessageType(code=200, name="chat").'
                )
            name = code
            code = None

        # Auto-allocate code when not provided
        if code is None:
            if _system:
                raise MessageTypeError("System messages must have an explicit code")
            MessageTypeRegistry.allocate(self)
        else:
            if not isinstance(code, int):
                raise MessageTypeError(
                    f"Code must be an int, str, or None, got: {type(code).__name__}. "
                    'Fix: MessageType("chat") auto-allocates a code, or pass an '
                    'explicit int: MessageType(code=200, name="chat").'
                )

            if not (0 <= code <= _PROTOCOL_MAX):
                raise MessageTypeError(
                    f"Code must be between 0 and {_PROTOCOL_MAX}, got: {code}. "
                    'Fix: MessageType("chat") auto-allocates a free user code '
                    "(200-9999), or pass an explicit code in range."
                )

            if code < _USER_CODE_MIN and not _system:
                raise MessageTypeError(
                    f"Code {code} is reserved for system messages "
                    f"(0-{_USER_CODE_MIN - 1}). Use a code between "
                    f"{_USER_CODE_MIN} and {_USER_CODE_MAX} for user messages. "
                    'Fix: MessageType("chat") auto-allocates a free user code.'
                )

            self.code: int = code
            MessageTypeRegistry.register(self)

        self.name: str = name or f"type_{self.code}"
        self.description: str | None = description

    def __repr__(self) -> str:
        return f"MessageType(code={self.code}, name='{self.name}')"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MessageType):
            return NotImplemented
        return self.code == other.code

    def __hash__(self) -> int:
        return hash(self.code)
