"""Message buffer for handling TCP stream framing."""

from ..logger.core import Logger
from .request import Request, Response


class MessageBuffer:
    """
    Buffer for accumulating TCP stream data and extracting complete messages.

    Handles the case where recv() returns partial messages or multiple messages
    concatenated together in the TCP stream.

    Thread-safe when used with a single reader thread per buffer instance.
    """

    __slots__ = (
        "_buffer",
        "_max_message_size",
        "_logger",
        "_header_size",
    )

    def __init__(self, max_message_size: int = 10 * 1024 * 1024):
        """
        Initialize message buffer.

        Args:
            max_message_size: Maximum allowed message size in bytes (default: 10MB)
        """
        self._buffer = bytearray()
        self._max_message_size = max_message_size
        self._logger = Logger.get_instance()
        self._header_size = 62  # Size of Veltix message header
        self._logger.debug(
            f"Created message buffer with max message size: {self._max_message_size}"
        )

    def add_data(self, data: bytes) -> None:
        """
        Add received data to the buffer.

        Args:
            data: Raw bytes received from socket
        """
        self._buffer.extend(data)
        self._logger.trace(f"Added {len(data)} bytes to buffer (total: {len(self._buffer)})")

    def extract_messages(self) -> list[Response]:
        """
        Extract all complete messages from the buffer.

        Parses the buffer and returns all complete messages that can be extracted.
        Incomplete messages remain in the buffer for future data.

        Returns:
            List of parsed Response objects
        """
        messages = []

        while True:
            # Need at least header to determine message size
            if len(self._buffer) < self._header_size:
                self._logger.trace(
                    f"Buffer too small for header ({len(self._buffer)} < {self._header_size})"
                )
                break

            content_size = int.from_bytes(self._buffer[2:6], byteorder="big")
            total_size = self._header_size + content_size

            self._logger.trace(f"Message size: {total_size} bytes (content: {content_size})")

            # Check if message size is valid
            if total_size > self._max_message_size:
                self._logger.error(
                    f"Message size {total_size} exceeds maximum {self._max_message_size}. "
                    f"Possible corruption or attack. Clearing buffer."
                )
                self.clear()
                break

            # Not enough data for complete message
            if len(self._buffer) < total_size:
                self._logger.trace(f"Incomplete message ({len(self._buffer)} < {total_size})")
                break

            # Extract complete message
            message_data = bytes(self._buffer[:total_size])
            self._buffer = self._buffer[total_size:]

            self._logger.trace(
                f"Extracted message ({total_size} bytes), buffer remaining: {len(self._buffer)}"
            )

            # Parse message
            try:
                response = Request.parse(message_data)
                messages.append(response)
                self._logger.trace(f"Successfully parsed message type {response.type.code}")
            except Exception as e:
                # Log error and skip corrupted message
                self._logger.error(
                    f"Failed to parse message ({len(message_data)} bytes): {type(e).__name__}: {e}"
                )
                # Continue processing remaining buffer
                continue

        return messages

    def clear(self) -> None:
        """Clear the buffer, discarding all data."""
        self._logger.debug(f"Clearing buffer ({len(self._buffer)} bytes discarded)")
        self._buffer.clear()

    def __len__(self) -> int:
        """Return current buffer size in bytes."""
        return len(self._buffer)

    def __repr__(self) -> str:
        """Return string representation of buffer."""
        return f"MessageBuffer(size={len(self._buffer)}, max_size={self._max_message_size})"
