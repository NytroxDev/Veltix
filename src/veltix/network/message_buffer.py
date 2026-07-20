"""Message buffer for handling TCP stream framing with protocol hardening."""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING, Optional

from .constants import HEADER_SIZE, MAGIC
from .parser import MessageParser

if TYPE_CHECKING:
    from ..internal.bus import VeltixBus
    from .response import Response

_MAGIC_SIZE = len(MAGIC)
_MAGIC_AND_SIZE = struct.Struct(">2s3xI")

MAX_BUFFER_SIZE = 20 * 1024 * 1024


class MessageBuffer:
    """
    Accumulates TCP stream data and extracts complete framed messages.

    Features:
    - Stream resynchronization via MAGIC byte search on parse failure
    - Hard buffer limit (MAX_BUFFER_SIZE) to prevent memory exhaustion
    - Handles partial reads and concatenated messages transparently
    - Thread-safe when used with a single reader thread per instance
    """

    __slots__ = ("_buffer", "_max_message_size", "_bus", "_max_buffer_size")

    def __init__(
        self,
        max_message_size: int = 10 * 1024 * 1024,
        max_buffer_size: int = MAX_BUFFER_SIZE,
        bus: Optional[VeltixBus] = None,
    ) -> None:
        """Initialise the message buffer.

        Args:
            max_message_size: Maximum allowed size of a single message in bytes.
            max_buffer_size: Hard limit on total buffer growth in bytes.
            bus: Optional event bus for error and debug logging.
        """
        self._buffer = bytearray()
        self._max_message_size = max_message_size
        self._max_buffer_size = max_buffer_size
        self._bus = bus

    def add_data(self, data: bytes) -> None:
        """Append raw bytes to the internal buffer.

        If adding *data* would exceed ``max_buffer_size``, the entire
        buffer is cleared and the data is discarded.

        Args:
            data: Raw bytes received from the TCP stream.
        """
        if len(self._buffer) + len(data) > self._max_buffer_size:
            if self._bus:
                self._bus.error(
                    f"Buffer size {len(self._buffer) + len(data)} exceeds maximum "
                    f"{self._max_buffer_size} — clearing buffer."
                )
            self.clear()
            return
        self._buffer.extend(data)

    def extract_messages(self) -> list[Response]:
        """Parse and return all complete framed messages currently in the buffer.

        The method consumes as many complete messages as possible. Partial
        messages remain in the buffer for the next call. If the MAGIC header
        is not found where expected, the buffer is resynchronized by scanning
        forward for the next MAGIC occurrence.

        Returns:
            A list of :class:`Response` objects parsed from the buffer.
        """
        messages = []

        while True:
            if len(self._buffer) < HEADER_SIZE:
                break

            magic, content_size = _MAGIC_AND_SIZE.unpack_from(self._buffer, 0)
            if magic != MAGIC:
                self._resync()
                continue

            total_size = HEADER_SIZE + content_size

            if total_size > self._max_message_size:
                if self._bus:
                    self._bus.error(
                        f"Message size {total_size} exceeds maximum {self._max_message_size} — "
                        f"possible corruption. Resyncing."
                    )
                self._resync()
                continue

            if len(self._buffer) < total_size:
                break

            message_data = self._buffer[:total_size]

            try:
                response = MessageParser.parse(message_data)
                self._buffer = self._buffer[total_size:]
                messages.append(response)
            except Exception as e:
                if self._bus:
                    self._bus.error(
                        f"Failed to parse message ({len(message_data)} bytes): {type(e).__name__}: {e}. "
                        f"Resyncing."
                    )
                self._resync()

        return messages

    def _resync(self) -> None:
        idx = self._buffer.find(MAGIC, 1)
        if idx == -1:
            self.clear()
        else:
            discarded = idx
            self._buffer = self._buffer[idx:]
            if self._bus:
                self._bus.debug(
                    f"Resynced: discarded {discarded} bytes, found MAGIC at offset {idx}"
                )

    def clear(self) -> None:
        """Discard all data currently held in the buffer."""
        self._buffer.clear()

    def __len__(self) -> int:
        """Return the number of bytes currently in the buffer.

        Returns:
            The buffer length in bytes.
        """
        return len(self._buffer)

    def __repr__(self) -> str:
        """Return a concise string representation of the buffer state.

        Returns:
            A string showing current size and configured limits.
        """
        return (
            f"MessageBuffer(size={len(self._buffer)}, "
            f"max_msg={self._max_message_size}, max_buf={self._max_buffer_size})"
        )
