"""Request and Response for the Veltix protocol."""

from __future__ import annotations

import dataclasses
import json
from typing import TYPE_CHECKING, Any, Optional

from exceptions import InvalidContentError

from ..utils.encoding import decode_json, decode_utf8

if TYPE_CHECKING:
    from .types import MessageType

_UNSET = object()
_INVALID = object()


@dataclasses.dataclass
class Response:
    """Represents a received message with its metadata."""

    type: MessageType
    content: bytes
    _hash: bytes = dataclasses.field(repr=False)
    _request_id: int = dataclasses.field(repr=False)

    def __init__(
        self,
        _type: MessageType,
        content: bytes,
        _hash: bytes = b"",
        _request_id: int = 0,
        request_id: Optional[int] = None,
    ) -> None:
        self.type = _type
        self.content = content
        self._hash = _hash
        self._request_id = request_id if request_id is not None else _request_id
        self._text_cached = _UNSET
        self._json_cached = _UNSET

    @property
    def request_id(self) -> int:
        """Request ID for correlation (uint16, 0–65535)."""
        return self._request_id

    @property
    def json(self) -> Any:
        """Decode and return the content as a JSON object.

        Raises:
            InvalidContentError: If the content is not valid JSON.
        """
        if self._json_cached is _UNSET:
            try:
                self._json_cached = decode_json(self.content)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._json_cached = _INVALID

        if self._json_cached is _INVALID:
            raise InvalidContentError("Content is not valid JSON")

        return self._json_cached

    @property
    def is_json(self) -> bool:
        """Return True if the content can be decoded as JSON."""
        if self._json_cached is _UNSET:
            try:
                self._json_cached = decode_json(self.content)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._json_cached = _INVALID

        return self._json_cached is not _UNSET and self._json_cached is not _INVALID

    @property
    def text(self) -> str:
        """Decode and return the content as UTF-8 text.

        Raises:
            InvalidContentError: If the content is not valid UTF-8.
        """
        if self._text_cached is _UNSET:
            try:
                self._text_cached = decode_utf8(self.content)
            except UnicodeDecodeError:
                self._text_cached = _INVALID

        if self._text_cached is _INVALID:
            raise InvalidContentError("Content is not valid UTF-8")

        return self._text_cached

    @property
    def is_text(self) -> bool:
        """Return True if the content can be decoded as UTF-8 text."""
        if self._text_cached is _UNSET:
            try:
                self._text_cached = decode_utf8(self.content)
            except UnicodeDecodeError:
                self._text_cached = _INVALID

        return self._text_cached is not _UNSET and self._text_cached is not _INVALID
