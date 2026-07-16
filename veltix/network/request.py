"""Request object for the Veltix protocol.

Provides the request container used to build outgoing messages and serialize
them into the Veltix wire format.
"""

from __future__ import annotations

import zlib
from typing import TYPE_CHECKING, Optional

from ..exceptions import RequestError
from .constants import HEADER_STRUCT, MAGIC, REQUEST_ID_SIZE
from .flags import MessageFlag

if TYPE_CHECKING:
    from .response import Response
    from .types import MessageType


class Request:
    """Represents a message request to be sent over the network.

    A request contains a message type, payload content, optional request ID,
    and protocol flags used during serialization.
    """

    def __init__(
        self,
        _type: MessageType,
        content: bytes,
        request_id: Optional[int] = None,
    ) -> None:
        """Initialize a new request.

        Args:
            _type: Message type associated with this request.
            content: Raw payload content as bytes.
            request_id: Optional identifier used to correlate the request
                with a response.
        """
        self.type = _type
        self.content = content
        self.request_id: Optional[int] = request_id
        self.flags = MessageFlag.NONE

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
