"""Tests for veltix.utils — encoding helpers and format_bytes."""

import json

import pytest

from veltix import decode_json, decode_utf8, encode_json, encode_utf8, format_bytes


class TestFormatBytes:
    def test_bytes(self):
        assert format_bytes(0) == "0 B"
        assert format_bytes(512) == "512 B"
        assert format_bytes(1023) == "1023 B"

    def test_kilobytes(self):
        assert format_bytes(1024) == "1 KB"
        assert format_bytes(1536) == "1.5 KB"
        assert format_bytes(148_000) == "144.5 KB"

    def test_megabytes(self):
        assert format_bytes(1024 * 1024) == "1 MB"
        assert format_bytes(3_000_000) == "2.861 MB"  # 4 significant figures

    def test_gigabytes(self):
        assert format_bytes(1024**3) == "1 GB"

    def test_returns_string(self):
        assert isinstance(format_bytes(100), str)


class TestEncodeUtf8:
    def test_encode_string(self):
        assert encode_utf8("hello") == b"hello"

    def test_encode_bytes_passthrough(self):
        assert encode_utf8(b"hello") == b"hello"

    def test_encode_unicode(self):
        assert encode_utf8("héllo") == "héllo".encode()

    def test_encode_empty_string(self):
        assert encode_utf8("") == b""


class TestDecodeUtf8:
    def test_decode_bytes(self):
        assert decode_utf8(b"hello") == "hello"

    def test_decode_unicode(self):
        assert decode_utf8("héllo".encode()) == "héllo"

    def test_decode_empty(self):
        assert decode_utf8(b"") == ""

    def test_roundtrip(self):
        original = "hello world"
        assert decode_utf8(encode_utf8(original)) == original


class TestEncodeJson:
    def test_encode_dict(self):
        result = encode_json({"key": "value"})
        assert isinstance(result, bytes)
        assert b"key" in result

    def test_encode_list(self):
        result = encode_json([1, 2, 3])
        assert isinstance(result, bytes)

    def test_encode_primitives(self):
        assert encode_json(42) == b"42"
        assert encode_json(True) == b"true"
        assert encode_json(None) == b"null"

    def test_encode_empty(self):
        assert encode_json({}) == b"{}"


class TestDecodeJson:
    def test_decode_dict(self):
        result = decode_json(b'{"key": "value"}')
        assert result == {"key": "value"}

    def test_decode_list(self):
        result = decode_json(b"[1, 2, 3]")
        assert result == [1, 2, 3]

    def test_roundtrip(self):
        original = {"name": "veltix", "version": "1.6.6", "active": True}
        assert decode_json(encode_json(original)) == original

    def test_decode_invalid_raises(self):
        with pytest.raises(json.JSONDecodeError):
            decode_json(b"not json")
