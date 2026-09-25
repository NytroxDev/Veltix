"""Message buffer for handling TCP stream framing with protocol hardening."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import _rust
from .constants import CODE_OFFSET, HEADER_SIZE, MAGIC, SIZE_PREFIX_STRUCT
from .parser import MessageParser
from .response import Response
from .types import MessageTypeRegistry

if TYPE_CHECKING:
    from ..internal.bus import VeltixBus

MAX_BUFFER_SIZE = 20 * 1024 * 1024


class MessageBuffer:
    """
    Accumulates TCP stream data and extracts complete framed messages.

    Uses the compiled Rust engine when available (see ``network._rust``);
    otherwise falls back to a pure-Python implementation with identical
    observable behaviour.

    Features:
    - Stream resynchronization via MAGIC byte search on parse failure
    - Hard buffer limit (MAX_BUFFER_SIZE) to prevent memory exhaustion
    - Handles partial reads and concatenated messages transparently
    - Thread-safe when used with a single reader thread per instance
    """

    __slots__ = ("_bus", "_engine", "_max_buffer_size", "_max_message_size", "_use_rust")

    def __init__(
        self,
        max_message_size: int = 10 * 1024 * 1024,
        max_buffer_size: int = MAX_BUFFER_SIZE,
        bus: VeltixBus | None = None,
        use_rust: bool | None = None,
    ) -> None:
        """Initialise the message buffer.

        Args:
            max_message_size: Maximum allowed size of a single message in bytes.
            max_buffer_size: Hard limit on total buffer growth in bytes.
            bus: Optional event bus for error and debug logging.
            use_rust: Pin the protocol engine for this buffer. ``None``
                (default) captures the process-wide engine at construction.
        """
        self._max_message_size = max_message_size
        self._max_buffer_size = max_buffer_size
        self._bus = bus
        self._use_rust = _rust.rust_enabled() if use_rust is None else use_rust
        self._engine: Any = (
            _rust.RustMessageBuffer(max_message_size, max_buffer_size)
            if self._use_rust
            else bytearray()
        )

    def add_data(self, data: bytes) -> None:
        """Append raw bytes to the internal buffer.

        If adding *data* would exceed ``max_buffer_size``, the entire
        buffer is cleared and the data is discarded.

        Args:
            data: Raw bytes received from the TCP stream.
        """
        if self._use_rust:
            accepted, detail = self._engine.add_data(data)
            if not accepted and self._bus:
                self._bus.error(detail)
            return
        if len(self._engine) + len(data) > self._max_buffer_size:
            if self._bus:
                self._bus.error(
                    f"Buffer size {len(self._engine) + len(data)} exceeds maximum "
                    f"{self._max_buffer_size} - clearing buffer."
                )
            self.clear()
            return
        self._engine.extend(data)

    def extract_messages(self) -> list[Response]:
        """Parse and return all complete framed messages currently in the buffer.

        The method consumes as many complete messages as possible. Partial
        messages remain in the buffer for the next call. If the MAGIC header
        is not found where expected, the buffer is resynchronized by scanning
        forward for the next MAGIC occurrence.

        Frames carrying an unknown message type are dropped with a warning
        and do NOT trigger a resynchronization.

        Returns:
            A list of :class:`Response` objects parsed from the buffer.
        """
        if self._use_rust:
            return self._extract_rust()
        return self._extract_python()

    def _extract_rust(self) -> list[Response]:
        messages: list[Response] = []
        for kind, payload in self._engine.extract_messages():
            if kind == "message":
                type_code, content, request_id, _flags, _hash = payload
                msg_type = MessageTypeRegistry.get(type_code)
                if msg_type is None:
                    if self._bus:
                        self._bus.warning(
                            f"Unknown message type code: {type_code} - message dropped"
                        )
                    continue
                messages.append(
                    Response(
                        _type=msg_type,
                        content=content,
                        _hash=_hash,
                        _request_id=request_id,
                    )
                )
            elif kind == "dropped":
                drop_kind, detail = payload
                suffix = (
                    " - possible corruption. Resyncing."
                    if drop_kind == "too_large"
                    else " - Resyncing."
                )
                if self._bus:
                    self._bus.error(f"{detail}{suffix}")
            elif kind == "resynced" and self._bus:
                self._bus.debug(
                    f"Resynced: discarded {payload} bytes, found MAGIC at offset {payload}"
                )
        return messages

    def _extract_python(self) -> list[Response]:
        messages = []
        buffer = self._engine

        while True:
            if len(buffer) < HEADER_SIZE:
                break

            magic, content_size = SIZE_PREFIX_STRUCT.unpack_from(buffer, 0)
            if magic != MAGIC:
                self._resync()
                continue

            total_size = HEADER_SIZE + content_size

            if total_size > self._max_message_size:
                if self._bus:
                    self._bus.error(
                        f"Message size {total_size} exceeds maximum {self._max_message_size} - "
                        f"possible corruption. Resyncing."
                    )
                self._resync()
                continue

            if len(buffer) < total_size:
                break

            type_code = int.from_bytes(buffer[CODE_OFFSET : CODE_OFFSET + 2], "big")
            if MessageTypeRegistry.get(type_code) is None:
                if self._bus:
                    self._bus.warning(f"Unknown message type code: {type_code} - message dropped")
                del buffer[:total_size]
                continue

            message_data = bytes(buffer[:total_size])

            try:
                response = MessageParser.parse(message_data, use_rust=self._use_rust)
                del buffer[:total_size]
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
        idx = self._engine.find(MAGIC, 1)
        if idx == -1:
            self.clear()
        else:
            discarded = idx
            del self._engine[:idx]
            if self._bus:
                self._bus.debug(
                    f"Resynced: discarded {discarded} bytes, found MAGIC at offset {idx}"
                )

    def clear(self) -> None:
        """Discard all data currently held in the buffer."""
        self._engine.clear()

    def __len__(self) -> int:
        """Return the number of bytes currently in the buffer.

        Returns:
            The buffer length in bytes.
        """
        return len(self._engine)

    def __repr__(self) -> str:
        """Return a concise string representation of the buffer state.

        Returns:
            A string showing current size and configured limits.
        """
        return (
            f"MessageBuffer(size={len(self)}, "
            f"max_msg={self._max_message_size}, max_buf={self._max_buffer_size})"
        )
