"""Shared wire-protocol test vectors for cross-implementation parity.

Well-known Veltix frames (15-byte big-endian header + content) used by the
Python test suite and mirrored by the Rust crates (``veltix-protocol``,
``veltix-message-buffer``) to verify both implementations agree on the wire
format byte-for-byte.

Header layout (see ``veltix.network.constants``)::

    MAGIC(2) | flags(1) | type code(2) | content size(4) | crc32(4) | request_id(2)

Vectors are generated with ``veltix.network.request.Request.compile`` and
validated by ``tests/test_protocol_vectors.py``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProtocolVector:
    """A well-known Veltix frame with its decoded fields.

    Attributes:
        name: Unique identifier for the vector.
        hex_frame: Full frame (header + content) as hex.
        type_code: Message type code from the header.
        content: Raw content bytes.
        request_id: Request ID from the header.
        flags: Protocol flags from the header (default 0).
    """

    name: str
    hex_frame: str
    type_code: int
    content: bytes
    request_id: int
    flags: int = 0

    @property
    def frame_bytes(self) -> bytes:
        """Return the full frame (header + content) as bytes."""
        return bytes.fromhex(self.hex_frame)

    @property
    def header_hex(self) -> str:
        """Return the 15-byte header portion as hex."""
        return self.hex_frame[:30]

    @property
    def content_hex(self) -> str:
        """Return the content portion as hex."""
        return self.hex_frame[30:]


VECTORS: tuple[ProtocolVector, ...] = (
    ProtocolVector(
        name="hello",
        hex_frame="56580000c8000000053610a686123468656c6c6f",
        type_code=200,
        content=b"hello",
        request_id=0x1234,
    ),
    ProtocolVector(
        name="empty",
        hex_frame="565800000000000000000000000000",
        type_code=0,
        content=b"",
        request_id=0,
    ),
    ProtocolVector(
        name="utf8",
        hex_frame="56580000c90000000b035d5cdeffff56656c74697820f09fa680",
        type_code=201,
        content="Veltix 🦀".encode(),
        request_id=0xFFFF,
    ),
    ProtocolVector(
        name="plugin_json",
        hex_frame="565800271000000010d2e71e5100017b226b223a205b312c20322c20335d7d",
        type_code=10000,
        content=b'{"k": [1, 2, 3]}',
        request_id=1,
    ),
)
