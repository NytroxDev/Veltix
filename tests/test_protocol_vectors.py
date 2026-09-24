"""Validate the shared protocol vectors against the reference implementation."""

from __future__ import annotations

import zlib

from protocol_vectors import VECTORS, ProtocolVector
from veltix import MessageType, Request
from veltix.network.constants import HEADER_SIZE
from veltix.network.parser import MessageParser
from veltix.network.types import MessageTypeRegistry


def _register_vector_type(vec: ProtocolVector) -> MessageType:
    """Return the MessageType matching a vector's type code, registering if needed."""
    existing = MessageTypeRegistry.get(vec.type_code)
    if existing is not None:
        return existing
    return MessageType(
        vec.type_code,
        name=f"vec_{vec.name}",
        _system=vec.type_code < 200,
    )


def test_vectors_frame_roundtrip() -> None:
    """Compiling a Request from each vector reproduces its exact frame."""
    for vec in VECTORS:
        msg_type = _register_vector_type(vec)
        request = Request(msg_type, vec.content, request_id=vec.request_id)
        assert request.compile() == vec.frame_bytes, f"mismatch for vector '{vec.name}'"


def test_vectors_parse_parity() -> None:
    """Parsing each vector yields its decoded fields."""
    for vec in VECTORS:
        _register_vector_type(vec)
        response = MessageParser.parse(vec.frame_bytes)
        assert response.type.code == vec.type_code, f"type code mismatch for '{vec.name}'"
        assert response.content == vec.content, f"content mismatch for '{vec.name}'"
        assert response.request_id == vec.request_id, f"request id mismatch for '{vec.name}'"


def test_vectors_hex_consistency() -> None:
    """Header fields and CRC32 in each vector are internally consistent."""
    for vec in VECTORS:
        raw = vec.frame_bytes
        assert len(vec.hex_frame) % 2 == 0
        assert len(raw) == HEADER_SIZE + len(vec.content), f"length mismatch for '{vec.name}'"
        assert int.from_bytes(raw[5:9], "big") == len(vec.content), (
            f"size field mismatch for '{vec.name}'"
        )
        assert raw[9:13] == zlib.crc32(vec.content).to_bytes(4, "big"), (
            f"crc32 mismatch for '{vec.name}'"
        )
