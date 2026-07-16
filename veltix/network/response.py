"""Request and Response for the Veltix protocol."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .types import MessageType


@dataclasses.dataclass
class Response:
    """Represents a received message with its metadata."""

    type: MessageType
    content: bytes
    _hash: bytes = dataclasses.field(repr=False)
    _request_id: int = dataclasses.field(repr=False)

    def __init__(
        self,
        _type: MessageType,
        content: bytes,
        _hash: bytes = b"",
        _request_id: int = 0,
        request_id: Optional[int] = None,
    ) -> None:
        self.type = _type
        self.content = content
        self._hash = _hash
        self._request_id = request_id if request_id is not None else _request_id

    @property
    def request_id(self) -> int:
        """Request ID for correlation (uint16, 0–65535)."""
        return self._request_id
