"""Message buffer for handling TCP stream framing."""

from __future__ import annotations

from ..logger.core import Logger
from .request import HEADER_SIZE, Request, Response


class MessageBuffer:
    """
    Accumulates TCP stream data and extracts complete framed messages.

    Handles partial reads and concatenated messages transparently.
    Thread-safe when used with a single reader thread per instance.
    """

    __slots__ = ("_buffer", "_max_message_size", "_logger", "_header_size")

    def __init__(self, max_message_size: int = 10 * 1024 * 1024) -> None:
        self._buffer = bytearray()
        self._max_message_size = max_message_size
        self._logger = Logger.get_instance()
        self._header_size = HEADER_SIZE

    def add_data(self, data: bytes) -> None:
        self._buffer.extend(data)

    def extract_messages(self) -> list[Response]:
        messages = []

        while True:
            if len(self._buffer) < self._header_size:
                break

            content_size = int.from_bytes(self._buffer[2:6], byteorder="big")
            total_size = self._header_size + content_size

            if total_size > self._max_message_size:
                self._logger.error(
                    f"Message size {total_size} exceeds maximum {self._max_message_size} — "
                    f"possible corruption. Clearing buffer."
                )
                self.clear()
                break

            if len(self._buffer) < total_size:
                break

            message_data = bytes(self._buffer[:total_size])

            try:
                response = Request.parse(message_data)
                self._buffer = self._buffer[total_size:]
                messages.append(response)
            except Exception as e:
                self._logger.error(
                    f"Failed to parse message ({len(message_data)} bytes): {type(e).__name__}: {e}. "
                    f"Advancing buffer past corrupted message to resync."
                )
                self._buffer = self._buffer[total_size:]

        return messages

    def clear(self) -> None:
        self._buffer.clear()

    def __len__(self) -> int:
        return len(self._buffer)

    def __repr__(self) -> str:
        return f"MessageBuffer(size={len(self._buffer)}, max_size={self._max_message_size})"
