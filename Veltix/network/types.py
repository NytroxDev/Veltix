from __future__ import annotations

from typing import Optional

from ..exceptions import MessageTypeError


class MessageTypeRegistry:
    """
    Registry for managing message types.
    
    Maintains a mapping between message codes and MessageType instances.
    """
    _registry = {}

    @classmethod
    def register(cls, msg_type: MessageType):
        """Register a message type."""
        cls._registry[msg_type.code] = msg_type

    @classmethod
    def get(cls, code: int) -> Optional[MessageType]:
        """Get a message type by its code."""
        return cls._registry.get(code)


class MessageType:
    """
    Defines a message type in the Veltix protocol.
    
    Args:
        code: Unique type code (0-199: system, 200-499: user, 500+: plugins)
        name: Type name (optional)
        description: Type description (optional)
    """

    def __init__(self, code: int, name: Optional[str] = None, description: Optional[str] = None) -> None:
        if not (0 <= code <= 65535):
            raise MessageTypeError(f"Code must be between 0 and 65535, received: {code}")

        self.code: int = code
        self.name: Optional[str] = name
        self.description: Optional[str] = description
        MessageTypeRegistry.register(self)

    def __repr__(self) -> str:
        """Return string representation of MessageType."""
        return f"MessageType(code={self.code}, name={self.name})"
