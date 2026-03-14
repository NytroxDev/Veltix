"""Encoding utilities for message serialization."""

import json
from typing import Any


def encode_utf8(data: str | bytes) -> bytes:
    """Encode string or bytes to UTF-8."""
    if isinstance(data, str):
        return data.encode("utf-8")
    return data


def decode_utf8(data: bytes) -> str:
    """Decode UTF-8 bytes to string."""
    return data.decode("utf-8")


def encode_json(data: Any) -> bytes:
    """Encode data to JSON bytes."""
    return json.dumps(data).encode("utf-8")


def decode_json(data: bytes) -> Any:
    """Decode JSON bytes to Python object."""
    return json.loads(data.decode("utf-8"))
