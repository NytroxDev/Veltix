"""Request and Response for the Veltix protocol."""

from __future__ import annotations

import dataclasses
import random
import struct
import threading
import zlib
from typing import Optional, Union

from ..exceptions import RequestError
from ..logger.core import Logger
from .types import MessageType, MessageTypeRegistry

MAGIC = b"VX"
MAGIC_SIZE = len(MAGIC)
HEADER_SIZE = 16
_HEADER_STRUCT = struct.Struct(">2sHI4s4s")

_id_lock = threading.Lock()


def generate_random_id() -> int:
    with _id_lock:
        return random.randint(0, 2**32 - 1)


@dataclasses.dataclass
class Response:
    """Represents a received message with its metadata."""

    type: MessageType
    content: bytes
    hash: bytes
    request_id: bytes


class Request:
    """Represents a message to be sent over the network."""

    def __init__(
        self, _type: MessageType, content: bytes, request_id: Optional[bytes] = None
    ) -> None:
        self.type = _type
        self.content = content
        self.request_id: bytes = request_id or generate_random_id().to_bytes(4, "big")
        self._logger = Logger.get_instance()

    def respond(self, response: Response) -> None:
        """Align this request's ID with a received response for correlation."""
        self.request_id = response.request_id

    @staticmethod
    def parse(data: Union[bytes, bytearray], max_message_size: int = 10 * 1024 * 1024) -> Response:
        """Parse raw bytes into a Response. Raises RequestError on invalid data."""
        if len(data) < HEADER_SIZE:
            raise RequestError(f"Data too short: {len(data)} bytes (minimum {HEADER_SIZE})")

        if len(data) > max_message_size:
            raise RequestError(f"Message too large: {len(data)} bytes (maximum {max_message_size})")

        header = data[:HEADER_SIZE]
        content = data[HEADER_SIZE:]

        magic, code, size, hash_received, request_id = _HEADER_STRUCT.unpack(header)

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
            content=content,
            hash=hash_received,
            request_id=request_id,
        )

    def compile(self) -> bytes:
        """Compile request into wire format. Raises RequestError if content exceeds 4GB."""
        max_size = 2**32 - 1
        size = len(self.content)

        if size > max_size:
            raise RequestError(f"Content too large: {size} bytes (max: {max_size})")

        hash_value = zlib.crc32(self.content).to_bytes(4, "big")

        header = _HEADER_STRUCT.pack(
            MAGIC,
            self.type.code,
            size,
            hash_value,
            self.request_id,
        )

        return header + self.content

    def __repr__(self) -> str:
        preview = self.content[:20] + b"..." if len(self.content) > 20 else self.content
        return f"Request(type={self.type.name}, content={preview!r}, id={self.request_id!r})"
