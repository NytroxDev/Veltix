"""Message type system for Veltix protocol."""

from __future__ import annotations

from typing import Optional

from ..exceptions import MessageTypeError


class MessageTypeRegistry:
    """
    Registry for managing message types.

    Maintains a singleton mapping between message codes and MessageType instances.
    All MessageType instances are automatically registered on creation.
    """

    _registry: dict[int, MessageType] = {}

    @classmethod
    def register(cls, msg_type: MessageType) -> None:
        """
        Register a message type.

        Args:
            msg_type: MessageType instance to register

        Raises:
            MessageTypeError: If code is already registered
        """
        if msg_type.code in cls._registry:
            existing = cls._registry[msg_type.code]
            raise MessageTypeError(
                f"Code {msg_type.code} already registered as '{existing.name}'"
            )
        cls._registry[msg_type.code] = msg_type

    @classmethod
    def get(cls, code: int) -> Optional[MessageType]:
        """
        Get a message type by its code.

        Args:
            code: Message type code to look up

        Returns:
            MessageType instance or None if not found
        """
        return cls._registry.get(code)

    @classmethod
    def list_all(cls) -> list[MessageType]:
        """Get all registered message types."""
        return list(cls._registry.values())


class MessageType:
    """
    Defines a message type in the Veltix protocol.

    Message codes are organized in ranges:
    - 0-199: System messages (reserved)
    - 200-499: User application messages
    - 500+: Plugin/extension messages

    Args:
        code: Unique type code (0-65535)
        name: Human-readable type name
        description: Optional detailed description

    Raises:
        MessageTypeError: If code is out of range or already registered
    """

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
        """Return string representation of MessageType."""
        return f"MessageType(code={self.code}, name='{self.name}')"

    def __eq__(self, other: object) -> bool:
        """Check equality based on code."""
        if not isinstance(other, MessageType):
            return NotImplemented
        return self.code == other.code

    def __hash__(self) -> int:
        """Make MessageType hashable."""
        return hash(self.code)
