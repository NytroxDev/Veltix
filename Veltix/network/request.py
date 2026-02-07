import dataclasses
import hashlib
import struct
import time

from ..exceptions import RequestError
from .types import MessageType, MessageTypeRegistry


@dataclasses.dataclass
class Response:
    """
    Represents a received message with all its metadata.

    Attributes:
        type: Message type
        content: Message content (bytes)
        timestamp: Send timestamp (milliseconds)
        hash: SHA256 hash of content
        received_at: Receive timestamp (milliseconds)
    """

    type: MessageType
    content: bytes
    timestamp: int
    hash: bytes
    received_at: int

    @property
    def latency(self) -> int:
        """Calculate latency in milliseconds."""
        return self.received_at - self.timestamp


class Request:
    """
    Represents a message to be sent.

    Attributes:
        type: Message type
        content: Message content (bytes)
    """

    def __init__(self, _type: MessageType, content: bytes) -> None:
        self.type = _type
        self.content: bytes = content

    @staticmethod
    def parse(data: bytes) -> Response:
        """
        Parse bytes into Response.

        Verifies integrity (hash + size) and reconstructs the message.

        Args:
            data: Bytes received from network

        Returns:
            Response with all metadata

        Raises:
            RequestError: If invalid hash, incorrect size, or unknown type
        """
        # Get current time as fast as possible
        received_at = int(time.time() * 1000)

        # Step 1: Separate header and content
        header = data[:46]
        content = data[46:]

        # Step 2: Unpack header
        code, size, hash_received, timestamp_ms = struct.unpack(">HI32sQ", header)

        # Step 3: Verify hash and size
        hash_content = hashlib.sha256(content).digest()
        if hash_received != hash_content:
            raise RequestError("Invalid hash! Corrupted data!")
        if len(content) != size:
            raise RequestError(
                f"Invalid size! Expected {size}, received {len(content)}"
            )

        # Step 4: Verify code
        msg_type = MessageTypeRegistry.get(code)
        if not msg_type:
            raise RequestError(f"Unknown type: {code}")

        # Step 5: Reconstruct Response
        return Response(
            type=msg_type,
            content=content,
            timestamp=timestamp_ms,
            hash=hash_received,
            received_at=received_at,
        )

    def compile(self) -> bytes:
        """
        Compile Request into bytes for sending.

        Returns:
            Message bytes (header + content)

        Raises:
            RequestError: If content is too large (> 4GB)
        """
        max_size = 2**32 - 1

        # Hash calculation
        hash_value = hashlib.sha256(self.content).digest()

        # Message information
        code = self.type.code
        size = len(self.content)

        # Size verification
        if size > max_size:
            raise RequestError(f"Content too large: {size} bytes (max: {max_size})")

        # Current timestamp
        timestamp_ms = int(time.time() * 1000)

        # Header construction (46 bytes)
        header = struct.pack(">HI32sQ", code, size, hash_value, timestamp_ms)

        return header + self.content
