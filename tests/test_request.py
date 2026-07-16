"""Tests for Request payload initialization."""

import pytest

from veltix import Request, RequestError


class TestRequestPayloads:
    def test_content_payload(self, test_message_type):
        request = Request(test_message_type, content=b"hello")

        assert request.content == b"hello"

    def test_text_payload(self, test_message_type):
        request = Request(test_message_type, text="hello")

        assert request.content == b"hello"

    def test_json_payload(self, test_message_type):
        request = Request(test_message_type, json={"hello": "world"})

        assert request.content == b'{"hello": "world"}'

    def test_text_payload_roundtrip(self, test_message_type):
        request = Request(test_message_type, text="hello")

        assert request.content.decode("utf-8") == "hello"

    def test_json_payload_roundtrip(self, test_message_type):
        request = Request(test_message_type, json={"value": 42})

        assert request.content.decode("utf-8") == '{"value": 42}'


class TestRequestPayloadValidation:
    def test_missing_payload(self, test_message_type):
        with pytest.raises(RequestError):
            Request(test_message_type)

    def test_multiple_payloads_content_text(self, test_message_type):
        with pytest.raises(RequestError):
            Request(
                test_message_type,
                content=b"hello",
                text="hello",
            )

    def test_multiple_payloads_content_json(self, test_message_type):
        with pytest.raises(RequestError):
            Request(
                test_message_type,
                content=b"hello",
                json={"hello": "world"},
            )

    def test_multiple_payloads_text_json(self, test_message_type):
        with pytest.raises(RequestError):
            Request(
                test_message_type,
                text="hello",
                json={"hello": "world"},
            )

    def test_content_must_be_bytes(self, test_message_type):
        with pytest.raises(RequestError):
            Request(test_message_type, content="hello")  # type: ignore[arg-type]


class TestRequestPayloadEdgeCases:
    def test_empty_bytes_payload(self, test_message_type):
        request = Request(test_message_type, content=b"")

        assert request.content == b""

    def test_empty_text_payload(self, test_message_type):
        request = Request(test_message_type, text="")

        assert request.content == b""

    def test_empty_json_payload(self, test_message_type):
        request = Request(test_message_type, json={})

        assert request.content == b"{}"
