"""Request object for the Veltix protocol.

Provides the request container used to build outgoing messages and serialize
them into the Veltix wire format.
"""

from __future__ import annotations

import zlib
from typing import TYPE_CHECKING, Any, Optional

from ..exceptions import RequestError
from ..utils.encoding import encode_json, encode_utf8
from .constants import HEADER_STRUCT, MAGIC, REQUEST_ID_SIZE
from .flags import MessageFlag

if TYPE_CHECKING:
    from .response import Response
    from .types import MessageType


_UNSET = object()


class Request:
    """Represents a message request to be sent over the network.

    A request contains a message type, payload content, optional request ID,
    and protocol flags used during serialization.
    """

    def __init__(
        self,
        _type: MessageType,
        content: Any = _UNSET,
        *,
        text: Any = _UNSET,
        json: Any = _UNSET,
        request_id: Optional[int] = None,
    ) -> None:
        """Initialize a new request.

        Args:
            _type: Message type associated with this request.
            content: Raw payload bytes.
            text: UTF-8 text to encode as the payload.
            json: Python object to serialize as JSON.
            request_id: Optional identifier used to correlate the request with a response.

        Raises:
            RequestError:
                If no payload, multiple payloads, or an invalid payload type is provided.
        """

        provided = sum(x is not _UNSET for x in (content, text, json))

        if provided != 1:
            raise RequestError("Provide exactly one of 'content', 'text', or 'json'.")

        self.content: bytes

        if content is not _UNSET:
            if not isinstance(content, bytes):
                raise RequestError("'content' must be bytes")
            self.content = content
        elif text is not _UNSET:
            self.content = encode_utf8(text)
        else:
            self.content = encode_json(json)

        self.request_id: Optional[int] = request_id
        self.flags = MessageFlag.NONE
        self.type = _type

    def respond(self, response: Response) -> None:
        """Associate this request with a received response.

        Updates the request ID using the ID from the provided response,
        allowing request/response correlation.

        Args:
            response: Response object associated with this request.
        """
        self.request_id = response.request_id

    def compile(self) -> bytes:
        """Serialize the request into the Veltix wire format.

        Builds the protocol header, calculates the content integrity hash,
        and appends the raw payload.

        Raises:
            RequestError: If the payload exceeds the maximum supported size.

        Returns:
            The serialized request as bytes.
        """
        max_size = 2**32 - 1
        size = len(self.content)

        if size > max_size:
            raise RequestError(f"Content too large: {size} bytes (max: {max_size})")

        hash_value = zlib.crc32(self.content).to_bytes(4, "big")
        request_id_bytes = (
            self.request_id.to_bytes(REQUEST_ID_SIZE, "big")
            if self.request_id is not None
            else b"\x00" * REQUEST_ID_SIZE
        )

        header = HEADER_STRUCT.pack(
            MAGIC,
            int(self.flags),
            self.type.code,
            size,
            hash_value,
            request_id_bytes,
        )

        return header + self.content

    def __repr__(self) -> str:
        """Return a debug representation of the request."""
        preview = self.content[:20] + b"..." if len(self.content) > 20 else self.content
        return f"Request(type={self.type.name}, content={preview!r}, id={self.request_id!r})"
