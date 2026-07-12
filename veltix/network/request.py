"""Request and Response for the Veltix protocol."""

from __future__ import annotations

import dataclasses
import struct
import zlib
from typing import Optional, Union

from ..exceptions import RequestError
from .flags import MessageFlag
from .types import MessageType, MessageTypeRegistry

MAGIC = b"VX"
MAGIC_SIZE = len(MAGIC)

REQUEST_ID_SIZE = 2

_HEADER_STRUCT = struct.Struct(f">2sBHI4s{REQUEST_ID_SIZE}s")
HEADER_SIZE = _HEADER_STRUCT.size


@dataclasses.dataclass
class Response:
    """Represents a received message with its metadata."""

    type: MessageType
    content: bytes
    _hash: bytes = dataclasses.field(repr=False)
    _request_id: int = dataclasses.field(repr=False)
    _flags: int = dataclasses.field(default=0, repr=False)


class Request:
    """Represents a message to be sent over the network."""

    def __init__(
        self,
        _type: MessageType,
        content: bytes,
        request_id: Optional[int] = None,
        flags: MessageFlag = MessageFlag.NONE,
    ) -> None:
        self.type = _type
        self.content = content
        self.request_id: Optional[int] = request_id
        self.flags = flags

    def respond(self, response: Response) -> None:
        """Align this request's ID with a received response for correlation."""
        self.request_id = response._request_id

    @staticmethod
    def parse(data: Union[bytes, bytearray], max_message_size: int = 10 * 1024 * 1024) -> Response:
        """Parse raw bytes into a Response. Raises RequestError on invalid data."""
        if len(data) < HEADER_SIZE:
            raise RequestError(f"Data too short: {len(data)} bytes (minimum {HEADER_SIZE})")

        if len(data) > max_message_size:
            raise RequestError(f"Message too large: {len(data)} bytes (maximum {max_message_size})")

        header = data[:HEADER_SIZE]
        content = data[HEADER_SIZE:]

        magic, flags, code, size, hash_received, request_id_raw = _HEADER_STRUCT.unpack(header)
        request_id = int.from_bytes(request_id_raw, "big")

        if magic != MAGIC:
            raise RequestError(f"Invalid magic bytes: {magic!r}")

        if len(content) != size:
            raise RequestError(f"Size mismatch: expected {size} bytes, got {len(content)}")

        msg_type = MessageTypeRegistry.get(code)
        if not msg_type:
            raise RequestError(f"Unknown message type code: {code}")

        hash_content = zlib.crc32(content).to_bytes(4, "big")
        if hash_received != hash_content:
            raise RequestError("Hash mismatch — corrupted data")

        return Response(
            type=msg_type,
            content=bytes(content),
            _hash=hash_received,
            _request_id=request_id,
            _flags=flags,
        )

    def compile(self) -> bytes:
        """Compile request into wire format. Raises RequestError if content exceeds 4GB."""
        max_size = 2**32 - 1
        size = len(self.content)

        if size > max_size:
            raise RequestError(f"Content too large: {size} bytes (max: {max_size})")

        hash_value = zlib.crc32(self.content).to_bytes(4, "big")
        request_id_bytes = self.request_id.to_bytes(REQUEST_ID_SIZE, "big") if self.request_id is not None else b"\x00" * REQUEST_ID_SIZE

        header = _HEADER_STRUCT.pack(
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
