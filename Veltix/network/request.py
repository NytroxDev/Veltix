import dataclasses
import hashlib
import struct
import time
import uuid

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
        request_id: Unique request identifier
    """

    type: MessageType
    content: bytes
    timestamp: int
    hash: bytes
    received_at: int
    request_id: str

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
        request_id: Unique request identifier (auto-generated if not provided)
    """

    def __init__(
        self, _type: MessageType, content: bytes, request_id: str = None
    ) -> None:
        self.type = _type
        self.content: bytes = content
        self.request_id: str = request_id or str(uuid.uuid4())

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
        header = data[:62]
        content = data[62:]

        # Step 2: Unpack header
        code, size, hash_received, timestamp_ms, request_id_bytes = struct.unpack(
            ">HI32sQ16s", header
        )

        # CORRECTION ICI : reformater en UUID avec tirets
        request_id_hex = request_id_bytes.hex()
        request_id = f"{request_id_hex[:8]}-{request_id_hex[8:12]}-{request_id_hex[12:16]}-{request_id_hex[16:20]}-{request_id_hex[20:]}"

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
            request_id=request_id,
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

        # Request ID as bytes
        try:
            # Si c'est un UUID valide (avec ou sans tirets)
            clean_id = self.request_id.replace("-", "")
            if len(clean_id) == 32 and all(
                c in "0123456789abcdefABCDEF" for c in clean_id
            ):
                request_id_bytes = bytes.fromhex(clean_id)
            else:
                # Sinon, hash la string pour obtenir 16 bytes
                request_id_bytes = hashlib.md5(self.request_id.encode()).digest()
        except:
            # Fallback: hash l'ID
            request_id_bytes = hashlib.md5(self.request_id.encode()).digest()

        header = struct.pack(
            ">HI32sQ16s", code, size, hash_value, timestamp_ms, request_id_bytes
        )

        return header + self.content
