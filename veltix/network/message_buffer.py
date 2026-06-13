"""Message buffer for handling TCP stream framing with protocol hardening."""

from __future__ import annotations

import struct

from ..logger.core import Logger
from .request import HEADER_SIZE, MAGIC, Request, Response

_MAGIC_SIZE = len(MAGIC)
_MAGIC_AND_SIZE = struct.Struct(">2s2xI")

MAX_BUFFER_SIZE = 20 * 1024 * 1024

_HAS_RUST = False

try:
    from veltix._message_buffer import MessageBuffer as _RustBuffer
    _HAS_RUST = True
except ImportError:
    pass


class MessageBuffer:
    """
    Accumulates TCP stream data and extracts complete framed messages.

    Features:
    - Stream resynchronization via MAGIC byte search on parse failure
    - Hard buffer limit (MAX_BUFFER_SIZE) to prevent memory exhaustion
    - Handles partial reads and concatenated messages transparently
    - Thread-safe when used with a single reader thread per instance
    """

    __slots__ = ("_buffer", "_max_message_size", "_logger", "_max_buffer_size")

    def __init__(
        self,
        max_message_size: int = 10 * 1024 * 1024,
        max_buffer_size: int = MAX_BUFFER_SIZE,
    ) -> None:
        self._buffer = bytearray()
        self._max_message_size = max_message_size
        self._max_buffer_size = max_buffer_size
        self._logger = Logger.get_instance()

    def add_data(self, data: bytes) -> None:
        if len(self._buffer) + len(data) > self._max_buffer_size:
            self._logger.error(
                f"Buffer size {len(self._buffer) + len(data)} exceeds maximum "
                f"{self._max_buffer_size} — clearing buffer."
            )
            self.clear()
            return
        self._buffer.extend(data)

    def extract_messages(self) -> list[Response]:
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
                self._logger.error(
                    f"Message size {total_size} exceeds maximum {self._max_message_size} — "
                    f"possible corruption. Resyncing."
                )
                self._resync()
                continue

            if len(self._buffer) < total_size:
                break

            message_data = self._buffer[:total_size]

            try:
                response = Request.parse(message_data)
                self._buffer = self._buffer[total_size:]
                messages.append(response)
            except Exception as e:
                self._logger.error(
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
            self._logger.debug(f"Resynced: discarded {discarded} bytes, found MAGIC at offset {idx}")

    def clear(self) -> None:
        self._buffer.clear()

    def __len__(self) -> int:
        return len(self._buffer)

    def __repr__(self) -> str:
        return (
            f"MessageBuffer(size={len(self._buffer)}, "
            f"max_msg={self._max_message_size}, max_buf={self._max_buffer_size})"
        )


if _HAS_RUST:

    class MessageBuffer:  # type: ignore[no-redef]
        """Message buffer backed by Rust for framing, with Python Response parsing."""

        __slots__ = ("_buf", "_max_message_size", "_max_buffer_size", "_logger")

        def __init__(
            self,
            max_message_size: int = 10 * 1024 * 1024,
            max_buffer_size: int = MAX_BUFFER_SIZE,
        ) -> None:
            self._buf = _RustBuffer(max_message_size, max_buffer_size)
            self._max_message_size = max_message_size
            self._max_buffer_size = max_buffer_size
            self._logger = Logger.get_instance()

        def add_data(self, data: bytes) -> None:
            self._buf.add_data(data)

        def extract_messages(self) -> list[Response]:
            messages: list[Response] = []
            for frame in self._buf.extract_messages():
                try:
                    messages.append(Request.parse(frame))
                except Exception as e:
                    self._logger.error(
                        f"Failed to parse message ({len(frame)} bytes): "
                        f"{type(e).__name__}: {e}."
                    )
            return messages

        def clear(self) -> None:
            self._buf.clear()

        def __len__(self) -> int:
            return len(self._buf)

        def __repr__(self) -> str:
            return (
                f"MessageBuffer(size={len(self._buf)}, "
                f"max_msg={self._max_message_size}, max_buf={self._max_buffer_size})"
            )
