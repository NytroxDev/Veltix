import zlib
from typing import Union

from ..exceptions import RequestError
from .constants import HEADER_SIZE, HEADER_STRUCT, MAGIC
from .request import Response
from .types import MessageTypeRegistry


class MessageParser:
    @staticmethod
    def parse(data: Union[bytes, bytearray], max_message_size: int = 10 * 1024 * 1024) -> Response:
        """Parse raw bytes into a Response. Raises RequestError on invalid data."""
        if len(data) < HEADER_SIZE:
            raise RequestError(f"Data too short: {len(data)} bytes (minimum {HEADER_SIZE})")

        if len(data) > max_message_size:
            raise RequestError(f"Message too large: {len(data)} bytes (maximum {max_message_size})")

        header = data[:HEADER_SIZE]
        content = data[HEADER_SIZE:]

        magic, _flags, code, size, hash_received, request_id_raw = HEADER_STRUCT.unpack(header)
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
            _type=msg_type,
            content=bytes(content),
            _hash=hash_received,
            _request_id=request_id,
        )
