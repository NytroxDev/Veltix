"""Tests for Request/Response binary protocol."""

import time
import uuid

import pytest

from veltix import MessageType, Request, RequestError


class TestProtocol:
    def test_request_compile(self, test_message_type):
        content = b"Hello World"
        request = Request(test_message_type, content)
        compiled = request.compile()
        assert len(compiled) == 62 + len(content)
        assert isinstance(compiled, bytes)

    def test_request_parse_roundtrip(self, test_message_type):
        content = b"Test Content 123"
        request = Request(test_message_type, content)
        request_id = request.request_id
        compiled = request.compile()
        response = Request.parse(compiled)
        assert response.type.code == test_message_type.code
        assert response.content == content
        assert response.request_id == request_id
        assert response.latency >= 0

    def test_request_id_auto_generation(self, test_message_type):
        request = Request(test_message_type, b"test")
        assert request.request_id is not None
        assert "-" in request.request_id

    def test_request_id_custom(self, test_message_type):
        custom_id = "my-custom-id-12345"
        request = Request(test_message_type, b"test", request_id=custom_id)
        assert request.request_id == custom_id

    def test_request_id_preservation(self, test_message_type):
        request_id = str(uuid.uuid4())
        request = Request(test_message_type, b"test", request_id=request_id)
        compiled = request.compile()
        response = Request.parse(compiled)
        assert response.request_id == request_id

    def test_hash_integrity_valid(self, test_message_type):
        request = Request(test_message_type, b"Valid content")
        compiled = request.compile()
        response = Request.parse(compiled)
        assert response.content == b"Valid content"

    def test_hash_integrity_corrupted(self, test_message_type):
        request = Request(test_message_type, b"Hello")
        compiled = request.compile()
        corrupted = bytearray(compiled)
        corrupted[62] = (corrupted[62] + 1) % 256
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
        corrupted[0] = 0xFF
        corrupted[1] = 0xFE
        with pytest.raises(RequestError) as exc_info:
            Request.parse(bytes(corrupted))
        assert "Unknown message type" in str(exc_info.value)

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

    def test_latency_calculation(self, test_message_type):
        request = Request(test_message_type, b"test")
        compiled = request.compile()
        time.sleep(0.01)
        response = Request.parse(compiled)
        assert response.latency >= 0
