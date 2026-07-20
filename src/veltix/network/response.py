"""Response object for the Veltix protocol.

Provides the response container used to represent received messages and
decode content payloads.
"""

from __future__ import annotations

import dataclasses
import json
from typing import TYPE_CHECKING, Any, Optional

from ..exceptions import InvalidContentError
from ..utils.encoding import decode_json, decode_utf8

if TYPE_CHECKING:
    from .types import MessageType

_UNSET = object()
_INVALID = object()


@dataclasses.dataclass
class Response:
    """Represents a response received through the Veltix protocol.

    A response contains the message type, raw content bytes, integrity hash,
    and request ID used to correlate it with the original request.

    Content decoding is performed lazily and cached after the first access
    through the :attr:`text` and :attr:`json` properties.
    """

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
        """Initialize a response object.

        Args:
            _type: Message type associated with this response.
            content: Raw response payload as bytes.
            _hash: Integrity hash generated from the payload.
            _request_id: Internal request identifier used for correlation.
            request_id: Optional public request ID override.

        """
        self.type = _type
        self.content = content
        self._hash = _hash
        self._request_id = request_id if request_id is not None else _request_id

        self._text_cached: Any = _UNSET
        self._json_cached: Any = _UNSET

    @property
    def request_id(self) -> int:
        """Return the request ID associated with this response.

        The request ID is used to match a response with the request that
        generated it.

        Returns:
            The request ID as an unsigned 16-bit integer.
        """
        return self._request_id

    @property
    def json(self) -> Any:
        """Return the response content decoded as JSON.

        The decoded value is cached after the first successful decoding.

        Raises:
            InvalidContentError: If the response content is not valid JSON.

        Returns:
            The decoded JSON value.
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
        """Check whether the response content is valid JSON.

        This method attempts to decode the content if it has not already
        been decoded. The result is cached for future accesses.

        Returns:
            True if the content contains valid JSON, otherwise False.
        """
        if self._json_cached is _UNSET:
            try:
                self._json_cached = decode_json(self.content)
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._json_cached = _INVALID

        return self._json_cached is not _UNSET and self._json_cached is not _INVALID

    @property
    def text(self) -> str:
        """Return the response content decoded as UTF-8 text.

        The decoded string is cached after the first successful decoding.

        Raises:
            InvalidContentError: If the response content is not valid UTF-8.

        Returns:
            The decoded text content.
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
        """Check whether the response content is valid UTF-8 text.

        This method attempts to decode the content if it has not already
        been decoded. The result is cached for future accesses.

        Returns:
            True if the content can be decoded as UTF-8 text, otherwise False.
        """
        if self._text_cached is _UNSET:
            try:
                self._text_cached = decode_utf8(self.content)
            except UnicodeDecodeError:
                self._text_cached = _INVALID

        return self._text_cached is not _UNSET and self._text_cached is not _INVALID
