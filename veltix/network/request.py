"""Request and Response for the Veltix protocol."""

from __future__ import annotations

import dataclasses
import random
import struct
import threading
import time
import zlib

from ..exceptions import RequestError
from ..logger.core import Logger
from .types import MessageType, MessageTypeRegistry

_HEADER_STRUCT = struct.Struct(">HI4sQ4s")

_id_lock = threading.Lock()


def generate_random_id() -> int:
    with _id_lock:
        return random.randint(0, 2**32 - 1)


@dataclasses.dataclass
class Response:
    """Represents a received message with its metadata."""

    type: MessageType
    content: bytes
    timestamp: int
    hash: bytes
    received_at: int
    request_id: bytes

    @property
    def latency(self) -> int:
        """Round-trip latency in ms. Assumes synchronized clocks."""
        return self.received_at - self.timestamp


class Request:
    """Represents a message to be sent over the network."""

    def __init__(self, _type: MessageType, content: bytes, request_id: bytes | None = None) -> None:
        self.type = _type
        self.content = content
        self.request_id: bytes = request_id or generate_random_id().to_bytes(4, "big")
        self._logger = Logger.get_instance()

    def respond(self, response: Response) -> None:
        """Align this request's ID with a received response for correlation."""
        self.request_id = response.request_id

    @staticmethod
    def parse(data: bytes, max_message_size: int = 10 * 1024 * 1024) -> Response:
        """Parse raw bytes into a Response. Raises RequestError on invalid data."""
        if len(data) < 22:
            raise RequestError(f"Data too short: {len(data)} bytes (minimum 22)")

        if len(data) > max_message_size:
            raise RequestError(f"Message too large: {len(data)} bytes (maximum {max_message_size})")

        received_at = int(time.monotonic() * 1000)

        header = data[:22]
        content = data[22:]

        code, size, hash_received, timestamp_ms, request_id = _HEADER_STRUCT.unpack(header)

        if len(content) != size:
            raise RequestError(f"Size mismatch: expected {size} bytes, got {len(content)}")

        hash_content = zlib.crc32(content).to_bytes(4, "big")
        if hash_received != hash_content:
            raise RequestError("Hash mismatch — corrupted data")

        msg_type = MessageTypeRegistry.get(code)
        if not msg_type:
            raise RequestError(f"Unknown message type code: {code}")

        return Response(
            type=msg_type,
            content=content,
            timestamp=timestamp_ms,
            hash=hash_received,
            received_at=received_at,
            request_id=request_id,
        )

    def compile(self) -> bytes:
        """Compile request into wire format. Raises RequestError if content exceeds 4GB."""
        max_size = 2**32 - 1
        size = len(self.content)

        if size > max_size:
            raise RequestError(f"Content too large: {size} bytes (max: {max_size})")

        hash_value = zlib.crc32(self.content).to_bytes(4, "big")
        timestamp_ms = int(time.monotonic() * 1000)

        header = _HEADER_STRUCT.pack(
            self.type.code,
            size,
            hash_value,
            timestamp_ms,
            self.request_id,
        )

        return header + self.content

    def __repr__(self) -> str:
        preview = self.content[:20] + b"..." if len(self.content) > 20 else self.content
        return f"Request(type={self.type.name}, content={preview!r}, id={self.request_id!r})"
