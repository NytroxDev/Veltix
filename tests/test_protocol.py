"""Tests for Request/Response binary protocol (v2 — magic bytes)."""

import pytest

from veltix import MessageType, Request, RequestError
from veltix.network.request import HEADER_SIZE, MAGIC, generate_random_id


class TestProtocol:
    def test_request_compile(self, test_message_type):
        content = b"Hello World"
        request = Request(test_message_type, content)
        compiled = request.compile()
        assert len(compiled) == HEADER_SIZE + len(content)
        assert isinstance(compiled, bytes)
        assert compiled[:2] == MAGIC

    def test_request_parse_roundtrip(self, test_message_type):
        content = b"Test Content 123"
        request = Request(test_message_type, content)
        request_id = request.request_id
        compiled = request.compile()
        response = Request.parse(compiled)
        assert response.type.code == test_message_type.code
        assert response.content == content
        assert response.request_id == request_id

    def test_request_id_auto_generation(self, test_message_type):
        request = Request(test_message_type, b"test")
        assert request.request_id is not None
        assert isinstance(request.request_id, bytes)
        assert len(request.request_id) == 4

    def test_request_id_custom(self, test_message_type):
        custom_id = b"\x01\x02\x03\x04"
        request = Request(test_message_type, b"test", request_id=custom_id)
        assert request.request_id == custom_id

    def test_request_id_preservation(self, test_message_type):
        custom_id = generate_random_id().to_bytes(4, "big")
        request = Request(test_message_type, b"test", request_id=custom_id)
        compiled = request.compile()
        response = Request.parse(compiled)
        assert response.request_id == custom_id

    def test_hash_integrity_valid(self, test_message_type):
        request = Request(test_message_type, b"Valid content")
        compiled = request.compile()
        response = Request.parse(compiled)
        assert response.content == b"Valid content"

    def test_hash_integrity_corrupted(self, test_message_type):
        request = Request(test_message_type, b"Hello")
        compiled = request.compile()
        corrupted = bytearray(compiled)
        corrupted[HEADER_SIZE] = (corrupted[HEADER_SIZE] + 1) % 256
        with pytest.raises(RequestError) as exc_info:
            Request.parse(bytes(corrupted))
        assert "Hash mismatch" in str(exc_info.value)

    def test_size_mismatch_detection(self, test_message_type):
        request = Request(test_message_type, b"Test")
        compiled = request.compile()
        corrupted = compiled + b"EXTRA"
        with pytest.raises(RequestError) as exc_info:
            Request.parse(corrupted)
        assert "mismatch" in str(exc_info.value)

    def test_unknown_message_type(self):
        msg_type = MessageType(code=1255, name="temp")
        request = Request(msg_type, b"test")
        compiled = request.compile()
        corrupted = bytearray(compiled)
        corrupted[2] = 0xFF  # type code high byte (offset 2 after 2 magic bytes)
        corrupted[3] = 0xFE  # type code low byte
        with pytest.raises(RequestError) as exc_info:
            Request.parse(bytes(corrupted))
        assert "Unknown message type" in str(exc_info.value)

    def test_invalid_magic_bytes(self, test_message_type):
        request = Request(test_message_type, b"test")
        compiled = request.compile()
        corrupted = bytearray(compiled)
        corrupted[0] = 0x00
        corrupted[1] = 0x00
        with pytest.raises(RequestError) as exc_info:
            Request.parse(bytes(corrupted))
        assert "Invalid magic bytes" in str(exc_info.value)

    def test_large_content(self, test_message_type):
        large_content = b"X" * 10000
        request = Request(test_message_type, large_content)
        compiled = request.compile()
        response = Request.parse(compiled)
        assert response.content == large_content

    def test_empty_content(self, test_message_type):
        request = Request(test_message_type, b"")
        compiled = request.compile()
        response = Request.parse(compiled)
        assert response.content == b""
