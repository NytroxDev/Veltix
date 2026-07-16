"""Utilities for parsing Veltix protocol messages."""

import zlib
from typing import Union

from ..exceptions import RequestError
from .constants import HEADER_SIZE, HEADER_STRUCT, MAGIC
from .response import Response
from .types import MessageTypeRegistry


class MessageParser:
    """Decode raw Veltix protocol messages into Response objects.

    Handles validation of the protocol header, message size, message type,
    and CRC32 checksum before creating a Response instance.

    This class only performs message decoding. Message serialization is
    handled by Request.compile().
    """

    @staticmethod
    def parse(
        data: Union[bytes, bytearray],
        max_message_size: int = 10 * 1024 * 1024,
    ) -> Response:
        """Parse raw protocol data into a Response object.

        Args:
            data: Raw message bytes received from the network.
            max_message_size: Maximum accepted message size in bytes.

        Returns:
            The decoded Response object.

        Raises:
            RequestError: If the data is too short, too large, has an
                invalid header, contains an unknown message type, has an
                invalid payload size, or fails checksum validation.
        """
        if len(data) < HEADER_SIZE:
            raise RequestError(f"Data too short: {len(data)} bytes (minimum {HEADER_SIZE})")

        if len(data) > max_message_size:
            raise RequestError(f"Message too large: {len(data)} bytes (maximum {max_message_size})")

        header = data[:HEADER_SIZE]
        content = data[HEADER_SIZE:]

        magic, flags, code, size, hash_received, request_id_raw = HEADER_STRUCT.unpack(header)
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
