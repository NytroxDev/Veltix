"""Request and Response handling for Veltix protocol."""

import dataclasses
import hashlib
import struct
import time
import uuid

from ..exceptions import RequestError
from ..logger.core import Logger
from .types import MessageType, MessageTypeRegistry


@dataclasses.dataclass
class Response:
    """
    Represents a received message with all its metadata.

    Attributes:
        type: Message type
        content: Message content as bytes
        timestamp: Send timestamp in milliseconds (from sender's clock)
        hash: SHA256 hash of content for integrity verification
        received_at: Receive timestamp in milliseconds (local clock)
        request_id: Unique request identifier (UUID format)
    """

    type: MessageType
    content: bytes
    timestamp: int
    hash: bytes
    received_at: int
    request_id: str

    @property
    def latency(self) -> int:
        """
        Calculate round-trip latency in milliseconds.

        Note: Assumes sender and receiver clocks are synchronized.
        For accurate latency, use PING/PONG with send_and_wait.
        """
        return self.received_at - self.timestamp


class Request:
    """
    Represents a message to be sent over the network.

    Attributes:
        type: Message type defining the purpose
        content: Message payload as bytes
        request_id: Unique identifier (auto-generated UUID if not provided)
    """

    def __init__(self, _type: MessageType, content: bytes, request_id: str | None = None) -> None:
        self.type = _type
        self.content: bytes = content
        self.request_id: str = request_id or str(uuid.uuid4())

        # Logger setup
        self._logger = Logger.get_instance()
        self._logger.debug(
            f"Created request: type={_type.name}, size={len(content)} bytes, id={self.request_id[:8]}..."
        )

    def respond(self, response: Response):
        """
        Update this request's ID to match a received response.
        
        This method is used to correlate a sent request with its corresponding
        response by updating the request_id to match the response's request_id.
        
        Args:
            response: The Response object received from the network
        """
        self.request_id = response.request_id
        self._logger.debug(f"Request {self.request_id[:8]}... responded with matching ID")

    @staticmethod
    def parse(data: bytes) -> Response:
        """
        Parse raw bytes into a Response object.

        Protocol format (62 byte header + N byte content):
        - 2 bytes: message type code (unsigned short, big-endian)
        - 4 bytes: content size (unsigned int, big-endian)
        - 32 bytes: SHA256 hash of content
        - 8 bytes: timestamp in milliseconds (unsigned long long, big-endian)
        - 16 bytes: request UUID (raw bytes)
        - N bytes: actual content

        Args:
            data: Raw bytes received from network

        Returns:
            Parsed Response object

        Raises:
            RequestError: If hash mismatch, size mismatch, or unknown type code
        """
        logger = Logger.get_instance()

        # Capture receive time as early as possible
        received_at = int(time.time() * 1000)

        # Validate minimum size
        if len(data) < 62:
            logger.error(f"Parse error: Data too short: {len(data)} bytes (minimum 62)")
            raise RequestError(f"Data too short: {len(data)} bytes (minimum 62)")

        # Split header and content
        header = data[:62]
        content = data[62:]

        # Unpack header
        code, size, hash_received, timestamp_ms, request_id_bytes = struct.unpack(
            ">HI32sQ16s", header
        )

        # Reconstruct UUID with hyphens
        request_id_hex = request_id_bytes.hex()
        request_id = (
            f"{request_id_hex[:8]}-{request_id_hex[8:12]}-"
            f"{request_id_hex[12:16]}-{request_id_hex[16:20]}-{request_id_hex[20:]}"
        )

        # Verify integrity
        hash_content = hashlib.sha256(content).digest()
        if hash_received != hash_content:
            logger.error(
                f"Parse error: Hash mismatch for request {request_id[:8]}... - corrupted data detected"
            )
            raise RequestError("Hash mismatch - corrupted data detected")

        if len(content) != size:
            logger.error(
                f"Parse error: Size mismatch for request {request_id[:8]}... - expected {size} bytes, got {len(content)}"
            )
            raise RequestError(f"Size mismatch: expected {size} bytes, got {len(content)}")

        # Lookup message type
        msg_type = MessageTypeRegistry.get(code)
        if not msg_type:
            logger.error(
                f"Parse error: Unknown message type code {code} for request {request_id[:8]}..."
            )
            raise RequestError(f"Unknown message type code: {code}")

        response = Response(
            type=msg_type,
            content=content,
            timestamp=timestamp_ms,
            hash=hash_received,
            received_at=received_at,
            request_id=request_id,
        )

        logger.debug(
            f"Parsed request: type={msg_type.name}, size={len(content)} bytes, id={request_id[:8]}..., latency={response.latency}ms"
        )
        return response

    def compile(self) -> bytes:
        """
        Compile Request into wire format for transmission.

        Returns:
            Complete message as bytes (header + content)

        Raises:
            RequestError: If content exceeds maximum size (4GB)
        """
        max_size = 2**32 - 1

        # Validate size
        size = len(self.content)
        if size > max_size:
            self._logger.error(
                f"Compile error: Content too large for request {self.request_id[:8]}...: {size} bytes (max: {max_size})"
            )
            raise RequestError(f"Content too large: {size} bytes (max: {max_size})")

        # Calculate hash
        hash_value = hashlib.sha256(self.content).digest()

        # Current timestamp
        timestamp_ms = int(time.time() * 1000)

        # Convert request_id to 16 bytes
        try:
            # Parse as UUID (with or without hyphens)
            clean_id = self.request_id.replace("-", "")
            if len(clean_id) == 32 and all(c in "0123456789abcdefABCDEF" for c in clean_id):
                request_id_bytes = bytes.fromhex(clean_id)
            else:
                # Not a hex UUID, hash the string
                request_id_bytes = hashlib.md5(self.request_id.encode()).digest()
        except ValueError:
            # Invalid hex, hash it
            request_id_bytes = hashlib.md5(self.request_id.encode()).digest()

        # Pack header
        header = struct.pack(
            ">HI32sQ16s",
            self.type.code,
            size,
            hash_value,
            timestamp_ms,
            request_id_bytes,
        )

        compiled_data = header + self.content
        self._logger.debug(
            f"Compiled request: type={self.type.name}, total_size={len(compiled_data)} bytes, id={self.request_id[:8]}..."
        )

        return compiled_data

    def __repr__(self) -> str:
        """String representation of Request."""
        content_preview = self.content[:20] + b"..." if len(self.content) > 20 else self.content
        return (
            f"Request(type={self.type.name}, "
            f"content={content_preview!r}, "
            f"request_id='{self.request_id[:8]}...')"
        )
