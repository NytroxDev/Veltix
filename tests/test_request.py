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

    def test_text_must_be_str_or_bytes(self, test_message_type):
        with pytest.raises(RequestError):
            Request(test_message_type, text=123)


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

    def test_request_id_valid_range(self, test_message_type):
        request = Request(test_message_type, b"test", request_id=65535)

        assert request.compile()

    def test_request_id_too_large_raises(self, test_message_type):
        with pytest.raises(RequestError, match="request_id"):
            Request(test_message_type, b"test", request_id=65536)

    def test_request_id_negative_raises(self, test_message_type):
        with pytest.raises(RequestError, match="request_id"):
            Request(test_message_type, b"test", request_id=-1)

    def test_request_id_non_int_raises(self, test_message_type):
        with pytest.raises(RequestError, match="request_id"):
            Request(test_message_type, b"test", request_id=70000.0)

    def test_request_id_invalid_after_mutation_raises_at_compile(self, test_message_type):
        request = Request(test_message_type, b"test", request_id=42)
        request.request_id = 70000

        with pytest.raises(RequestError, match="request_id"):
            request.compile()


class TestRequestGuidingErrors:
    def test_missing_payload_guides_with_example(self, test_message_type):
        with pytest.raises(RequestError) as exc:
            Request(test_message_type)

        text = str(exc.value)
        assert "exactly one" in text
        assert "content" in text and "text" in text and "json" in text
        assert "Fix:" in text
        assert "Request(" in text  # exemple concret

    def test_multiple_payloads_list_them(self, test_message_type):
        with pytest.raises(RequestError) as exc:
            Request(test_message_type, content=b"hi", text="hi")

        text = str(exc.value)
        assert "2 payloads" in text
        assert "'content'" in text and "'text'" in text
        assert "Fix:" in text

    def test_content_non_bytes_guides(self, test_message_type):
        with pytest.raises(RequestError) as exc:
            Request(test_message_type, content="hello")  # type: ignore[arg-type]

        text = str(exc.value)
        assert "must be bytes" in text
        assert "text=" in text  # alternative suggérée
        assert "Fix:" in text

    def test_text_wrong_type_guides(self, test_message_type):
        with pytest.raises(RequestError) as exc:
            Request(test_message_type, text=123)

        text = str(exc.value)
        assert "str or bytes" in text and "int" in text
        assert "Fix:" in text

    def test_json_non_serializable_guides(self, test_message_type):
        with pytest.raises(RequestError) as exc:
            Request(test_message_type, json=complex(1, 2))

        text = str(exc.value)
        assert "JSON-serializable" in text
        assert "Fix:" in text

    def test_json_circular_reference_guides(self, test_message_type):
        payload: dict = {}
        payload["self"] = payload

        with pytest.raises(RequestError, match="JSON-serializable"):
            Request(test_message_type, json=payload)
