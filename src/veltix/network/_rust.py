"""Optional Rust backend for the protocol layer.

Loads the compiled ``veltix._rust`` extension when it is installed and not
explicitly disabled, so the hot paths (framing, parsing, compiling) run in
Rust. When the extension is unavailable — or ``VELTIX_DISABLE_RUST`` is set
to a truthy value (``1``, ``true``, ``yes``) — the pure-Python
implementations are used instead.

The availability decision is taken once at module import time; change the
environment variable and ``importlib.reload`` this module to re-evaluate.
"""

from __future__ import annotations

import os

from ..exceptions import RequestError

try:
    from veltix._rust import MessageBuffer as RustMessageBuffer
    from veltix._rust import compile as _compile
    from veltix._rust import parse as _parse
except ImportError:  # pragma: no cover - extension not installed on this platform
    RustMessageBuffer = None  # type: ignore[assignment, misc]
    _compile = None  # type: ignore[assignment]
    _parse = None  # type: ignore[assignment]

_EXTENSION_LOADED: bool = _parse is not None
_EXTENSION_DISABLED: bool = os.environ.get("VELTIX_DISABLE_RUST", "").lower() in (
    "1",
    "true",
    "yes",
)


def rust_enabled() -> bool:
    """Return True when the compiled Rust extension should be used.

    Returns:
        True when the extension is installed and ``VELTIX_DISABLE_RUST`` is
        not set to a truthy value.
    """
    return _EXTENSION_LOADED and not _EXTENSION_DISABLED


def parse(data: bytes | bytearray, max_message_size: int) -> tuple[int, bytes, int, int, bytes]:
    """Validate a wire frame through the Rust parser.

    Only call when :func:`rust_enabled` is True.

    Args:
        data: Raw frame bytes (header + content).
        max_message_size: Maximum accepted message size in bytes.

    Returns:
        A ``(type_code, content, request_id, flags, hash)`` tuple.

    Raises:
        RequestError: If the frame fails wire validation.
    """
    assert _parse is not None
    try:
        return _parse(data, max_message_size)
    except ValueError as exc:
        raise RequestError(str(exc)) from None


def compile(type_code: int, content: bytes, request_id: int, flags: int) -> bytes:
    """Serialize a frame through the Rust compiler.

    Only call when :func:`rust_enabled` is True.

    Args:
        type_code: Message type code from the header.
        content: Raw payload bytes.
        request_id: Request correlation ID (0 when unset).
        flags: Protocol flags byte.

    Returns:
        The serialized frame (15-byte header + content).

    Raises:
        RequestError: If the content exceeds the protocol size limit.
    """
    assert _compile is not None
    try:
        return _compile(type_code, content, request_id, flags)
    except ValueError as exc:
        raise RequestError(str(exc)) from None
