"""Tests for Response content decoding helpers."""

import pytest

from veltix.exceptions import InvalidContentError
from veltix.network.response import Response


class TestResponseText:
    def test_valid_text(self, test_message_type):
        response = Response(
            _type=test_message_type,
            content=b"hello world",
        )

        assert response.is_text is True
        assert response.text == "hello world"

    def test_invalid_text(self, test_message_type):
        response = Response(
            _type=test_message_type,
            content=b"\xff\xfe\xfd",
        )

        assert response.is_text is False

        with pytest.raises(InvalidContentError):
            response.text

    def test_text_cache(self, test_message_type, monkeypatch):
        calls = 0

        def fake_decode(data):
            nonlocal calls
            calls += 1
            return "cached"

        monkeypatch.setattr(
            "veltix.network.response.decode_utf8",
            fake_decode,
        )

        response = Response(
            _type=test_message_type,
            content=b"hello",
        )

        assert response.text == "cached"
        assert response.text == "cached"
        assert calls == 1


class TestResponseJson:
    def test_valid_json(self, test_message_type):
        response = Response(
            _type=test_message_type,
            content=b'{"username": "nytrox"}',
        )

        assert response.is_json is True
        assert response.json == {"username": "nytrox"}

    def test_invalid_json(self, test_message_type):
        response = Response(
            _type=test_message_type,
            content=b"not json",
        )

        assert response.is_json is False

        with pytest.raises(InvalidContentError):
            response.json

    def test_json_cache(self, test_message_type, monkeypatch):
        calls = 0

        def fake_decode(data):
            nonlocal calls
            calls += 1
            return {"cached": True}

        monkeypatch.setattr(
            "veltix.network.response.decode_json",
            fake_decode,
        )

        response = Response(
            _type=test_message_type,
            content=b"{}",
        )

        assert response.json == {"cached": True}
        assert response.json == {"cached": True}
        assert calls == 1


class TestResponseContentDetection:
    def test_json_is_not_text_when_binary(self, test_message_type):
        response = Response(
            _type=test_message_type,
            content=b'{"hello": "world"}',
        )

        assert response.is_json is True
        assert response.is_text is True

    def test_binary_is_neither_json_nor_text(self, test_message_type):
        response = Response(
            _type=test_message_type,
            content=b"\xff\x00\xfe",
        )

        assert response.is_json is False
        assert response.is_text is False

    def test_invalid_content_exception_is_veltix_error(self):
        from veltix.exceptions import VeltixError

        assert issubclass(InvalidContentError, VeltixError)
