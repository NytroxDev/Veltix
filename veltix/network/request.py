"""Request and Response for the Veltix protocol."""

from __future__ import annotations

import zlib
from typing import TYPE_CHECKING, Optional

from ..exceptions import RequestError
from .constants import HEADER_STRUCT, MAGIC, REQUEST_ID_SIZE
from .flags import MessageFlag

if TYPE_CHECKING:
    from .response import Response
    from .types import MessageType


class Request:
    """Represents a message to be sent over the network."""

    def __init__(
        self,
        _type: MessageType,
        content: bytes,
        request_id: Optional[int] = None,
    ) -> None:
        self.type = _type
        self.content = content
        self.request_id: Optional[int] = request_id
        self.flags = MessageFlag.NONE

    def respond(self, response: Response) -> None:
        """Align this request's ID with a received response for correlation."""
        self.request_id = response.request_id

    def compile(self) -> bytes:
        """Compile request into wire format. Raises RequestError if content exceeds 4GB."""
        max_size = 2**32 - 1
        size = len(self.content)

        if size > max_size:
            raise RequestError(f"Content too large: {size} bytes (max: {max_size})")

        hash_value = zlib.crc32(self.content).to_bytes(4, "big")
        request_id_bytes = (
            self.request_id.to_bytes(REQUEST_ID_SIZE, "big")
            if self.request_id is not None
            else b"\x00" * REQUEST_ID_SIZE
        )

        header = HEADER_STRUCT.pack(
            MAGIC,
            int(self.flags),
            self.type.code,
            size,
            hash_value,
            request_id_bytes,
        )

        return header + self.content

    def __repr__(self) -> str:
        preview = self.content[:20] + b"..." if len(self.content) > 20 else self.content
        return f"Request(type={self.type.name}, content={preview!r}, id={self.request_id!r})"
