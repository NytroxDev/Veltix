"""Tests for Request/Response binary protocol (v2 — magic bytes + compact IDs)."""

import pytest

from veltix import MessageType, Request, RequestError
from veltix.network.constants import HEADER_SIZE, MAGIC, REQUEST_ID_SIZE
from veltix.network.parser import MessageParser


class TestProtocol:
    def test_request_compile(self, test_message_type):
        content = b"Hello World"
        request = Request(test_message_type, content, request_id=1)
        compiled = request.compile()
        assert len(compiled) == HEADER_SIZE + len(content)
        assert isinstance(compiled, bytes)
        assert compiled[:2] == MAGIC

    def test_request_parse_roundtrip(self, test_message_type):
        content = b"Test Content 123"
        request = Request(test_message_type, content, request_id=42)
        request_id = request.request_id
        compiled = request.compile()
        response = MessageParser.parse(compiled)
        assert response.type.code == test_message_type.code
        assert response.content == content
        assert response.request_id == request_id

    def test_request_id_none_defaults_to_zero(self, test_message_type):
        request = Request(test_message_type, b"test")
        assert request.request_id is None
        compiled = request.compile()
        response = MessageParser.parse(compiled)
        assert response.request_id == 0

    def test_request_id_custom_int(self, test_message_type):
        request = Request(test_message_type, b"test", request_id=12345)
        assert request.request_id == 12345

    def test_request_id_preservation(self, test_message_type):
        request = Request(test_message_type, b"test", request_id=9999)
        compiled = request.compile()
        response = MessageParser.parse(compiled)
        assert response.request_id == 9999

    def test_request_id_compact_size(self, test_message_type):
        assert REQUEST_ID_SIZE == 2

    def test_request_id_zero(self, test_message_type):
        request = Request(test_message_type, b"test", request_id=0)
        compiled = request.compile()
        response = MessageParser.parse(compiled)
        assert response.request_id == 0

    def test_hash_integrity_valid(self, test_message_type):
        request = Request(test_message_type, b"Valid content", request_id=1)
        compiled = request.compile()
        response = MessageParser.parse(compiled)
        assert response.content == b"Valid content"

    def test_hash_integrity_corrupted(self, test_message_type):
        request = Request(test_message_type, b"Hello", request_id=1)
        compiled = request.compile()
        corrupted = bytearray(compiled)
        corrupted[HEADER_SIZE] = (corrupted[HEADER_SIZE] + 1) % 256
        with pytest.raises(RequestError) as exc_info:
            MessageParser.parse(bytes(corrupted))
        assert "Hash mismatch" in str(exc_info.value)

    def test_size_mismatch_detection(self, test_message_type):
        request = Request(test_message_type, b"Test", request_id=1)
        compiled = request.compile()
        corrupted = compiled + b"EXTRA"
        with pytest.raises(RequestError) as exc_info:
            MessageParser.parse(corrupted)
        assert "mismatch" in str(exc_info.value)

    def test_unknown_message_type(self):
        msg_type = MessageType(code=1255, name="temp")
        request = Request(msg_type, b"test", request_id=1)
        compiled = request.compile()
        corrupted = bytearray(compiled)
        corrupted[2] = 0xFF  # type code high byte (offset 2 after 2 magic bytes)
        corrupted[3] = 0xFE  # type code low byte
        with pytest.raises(RequestError) as exc_info:
            MessageParser.parse(bytes(corrupted))
        assert "Unknown message type" in str(exc_info.value)

    def test_invalid_magic_bytes(self, test_message_type):
        request = Request(test_message_type, b"test", request_id=1)
        compiled = request.compile()
        corrupted = bytearray(compiled)
        corrupted[0] = 0x00
        corrupted[1] = 0x00
        with pytest.raises(RequestError) as exc_info:
            MessageParser.parse(bytes(corrupted))
        assert "Invalid magic bytes" in str(exc_info.value)

    def test_large_content(self, test_message_type):
        large_content = b"X" * 10000
        request = Request(test_message_type, large_content, request_id=1)
        compiled = request.compile()
        response = MessageParser.parse(compiled)
        assert response.content == large_content

    def test_empty_content(self, test_message_type):
        request = Request(test_message_type, b"", request_id=1)
        compiled = request.compile()
        response = MessageParser.parse(compiled)
        assert response.content == b""
