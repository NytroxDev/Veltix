"""Tests for the optional Rust protocol backend and its pure-Python fallback.

The compiled ``veltix._rust`` extension is optional (absent from sdists and
foreign platforms): when missing, everything runs on the pure-Python
implementation. These tests verify backend selection, the
``VELTIX_DISABLE_RUST`` escape hatch, and that both backends behave
identically.
"""

from __future__ import annotations

import importlib
import os
import zlib

import pytest

from veltix import Request
from veltix.exceptions import RequestError
from veltix.internal.bus import VeltixBus
from veltix.internal.events import LogEvent
from veltix.network import _rust
from veltix.network.constants import HEADER_STRUCT, MAGIC
from veltix.network.message_buffer import MessageBuffer
from veltix.network.parser import MessageParser

RUST_AVAILABLE = _rust._EXTENSION_LOADED


def _make_frame(type_code: int, content: bytes, request_id: int = 0) -> bytes:
    """Build a valid wire frame for *type_code* without touching the registry."""
    header = HEADER_STRUCT.pack(
        MAGIC,
        0,
        type_code,
        len(content),
        zlib.crc32(content).to_bytes(4, "big"),
        request_id.to_bytes(2, "big"),
    )
    return header + content


def _reload(module) -> None:
    """Re-evaluate the module-level Rust availability decision."""
    importlib.reload(module)


@pytest.fixture(params=["rust", "fallback"])
def backend(request):
    """Parametrize over both protocol backends (Rust only when available)."""
    previous = os.environ.get("VELTIX_DISABLE_RUST")
    if request.param == "rust":
        if not RUST_AVAILABLE:
            pytest.skip("Rust extension not installed")
        os.environ.pop("VELTIX_DISABLE_RUST", None)
    else:
        os.environ["VELTIX_DISABLE_RUST"] = "1"
    _reload(_rust)
    try:
        yield request.param
    finally:
        if previous is None:
            os.environ.pop("VELTIX_DISABLE_RUST", None)
        else:
            os.environ["VELTIX_DISABLE_RUST"] = previous
        _reload(_rust)


class TestBackendSelection:
    def test_rust_enabled_matches_extension_presence(self):
        """Without env overrides, rust_enabled() mirrors extension availability."""
        previous = os.environ.get("VELTIX_DISABLE_RUST")
        os.environ.pop("VELTIX_DISABLE_RUST", None)
        _reload(_rust)
        try:
            assert _rust.rust_enabled() is RUST_AVAILABLE
        finally:
            if previous is not None:
                os.environ["VELTIX_DISABLE_RUST"] = previous
            _reload(_rust)

    def test_env_var_disables_rust(self):
        """VELTIX_DISABLE_RUST=1 forces the fallback even with the extension."""
        previous = os.environ.get("VELTIX_DISABLE_RUST")
        os.environ["VELTIX_DISABLE_RUST"] = "1"
        _reload(_rust)
        try:
            assert not _rust.rust_enabled()
        finally:
            if previous is None:
                os.environ.pop("VELTIX_DISABLE_RUST", None)
            else:
                os.environ["VELTIX_DISABLE_RUST"] = previous
            _reload(_rust)

    @pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust extension not installed")
    def test_falsy_env_value_keeps_rust(self):
        """VELTIX_DISABLE_RUST=0 does not disable the extension."""
        previous = os.environ.get("VELTIX_DISABLE_RUST")
        os.environ["VELTIX_DISABLE_RUST"] = "0"
        _reload(_rust)
        try:
            assert _rust.rust_enabled()
        finally:
            if previous is None:
                os.environ.pop("VELTIX_DISABLE_RUST", None)
            else:
                os.environ["VELTIX_DISABLE_RUST"] = previous
            _reload(_rust)

    @pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust extension not installed")
    def test_clean_env_enables_rust(self):
        """With the env var unset, rust_enabled() is True when installed."""
        previous = os.environ.get("VELTIX_DISABLE_RUST")
        os.environ.pop("VELTIX_DISABLE_RUST", None)
        _reload(_rust)
        try:
            assert _rust.rust_enabled()
        finally:
            if previous is not None:
                os.environ["VELTIX_DISABLE_RUST"] = previous
            _reload(_rust)


class TestMessageBufferBackend:
    def test_engine_selection(self, backend):
        """The buffer picks the engine matching the current backend."""
        buf = MessageBuffer()
        assert buf._use_rust is (backend == "rust")

    def test_extracts_message(self, backend, test_message_type):
        """A complete frame is extracted identically on both backends."""
        buf = MessageBuffer()
        wire = Request(test_message_type, b"Hello Rust?", request_id=42).compile()
        buf.add_data(wire)
        messages = buf.extract_messages()

        assert len(messages) == 1
        assert messages[0].type.code == test_message_type.code
        assert messages[0].content == b"Hello Rust?"
        assert messages[0].request_id == 42
        assert messages[0]._hash == zlib.crc32(b"Hello Rust?").to_bytes(4, "big")
        assert len(buf) == 0

    def test_partial_then_complete(self, backend, test_message_type):
        """Partial data produces nothing until the frame is complete."""
        buf = MessageBuffer()
        wire = Request(test_message_type, b"Split me").compile()

        buf.add_data(wire[:7])
        assert buf.extract_messages() == []
        buf.add_data(wire[7:])
        messages = buf.extract_messages()

        assert len(messages) == 1
        assert messages[0].content == b"Split me"

    def test_corrupt_frame_then_valid(self, backend, test_message_type):
        """A corrupted frame is resynced away and the next frame extracted."""
        buf = MessageBuffer()
        wire = Request(test_message_type, b"good").compile()
        corrupt = bytearray(wire)
        corrupt[-1] ^= 0xFF

        buf.add_data(bytes(corrupt) + wire)
        messages = buf.extract_messages()

        assert len(messages) == 1
        assert messages[0].content == b"good"

    def test_unknown_type_dropped_without_resync(self, backend, test_message_type):
        """Unknown-type frames are dropped with a warning and consume exactly
        one frame - the following message is parsed without resyncing."""
        bus = VeltixBus()
        warnings: list[str] = []
        bus.subscribe(LogEvent.WARNING, lambda _event, msg: warnings.append(msg))
        buf = MessageBuffer(bus=bus)

        unknown = _make_frame(60000, b"who dis")
        following = Request(test_message_type, b"still here").compile()

        buf.add_data(unknown + following)
        messages = buf.extract_messages()

        assert len(messages) == 1
        assert messages[0].content == b"still here"
        assert len(warnings) == 1
        assert "Unknown message type code: 60000" in warnings[0]

    def test_overflow_clears_and_logs(self, backend):
        """Exceeding max_buffer_size clears the buffer and logs an error."""
        bus = VeltixBus()
        errors: list[str] = []
        bus.subscribe(LogEvent.ERROR, lambda _event, msg: errors.append(msg))
        buf = MessageBuffer(max_message_size=100, max_buffer_size=100, bus=bus)

        buf.add_data(b"x" * 50)
        assert len(buf) == 50
        buf.add_data(b"y" * 200)

        assert len(buf) == 0
        assert any("exceeds maximum 100" in msg for msg in errors)

    def test_resync_logs_debug(self, backend, test_message_type):
        """Garbage before a valid frame triggers a debug resync log."""
        bus = VeltixBus()
        debugs: list[str] = []
        bus.subscribe(LogEvent.DEBUG, lambda _event, msg: debugs.append(msg))
        buf = MessageBuffer(bus=bus)

        wire = Request(test_message_type, b"ok").compile()
        buf.add_data(b"\x00\x01\x02" + wire)
        messages = buf.extract_messages()

        assert len(messages) == 1
        assert messages[0].content == b"ok"
        assert any(msg.startswith("Resynced: discarded 3 bytes") for msg in debugs)


class TestParserBackend:
    def test_parse_parity(self, backend, test_message_type):
        """Parsing a valid frame yields identical fields on both backends."""
        wire = Request(test_message_type, b"hash me", request_id=777).compile()
        response = MessageParser.parse(wire)

        assert response.type.code == test_message_type.code
        assert response.content == b"hash me"
        assert response.request_id == 777
        assert response._hash == zlib.crc32(b"hash me").to_bytes(4, "big")

    def test_parse_accepts_memoryview(self, backend, test_message_type):
        """memoryview input is accepted on both backends."""
        wire = Request(test_message_type, b"view").compile()
        response = MessageParser.parse(memoryview(wire))
        assert response.content == b"view"

    def test_parse_corrupted_hash_raises(self, backend, test_message_type):
        """A tampered payload raises RequestError on both backends."""
        wire = bytearray(Request(test_message_type, b"tampered").compile())
        wire[-1] ^= 0xFF
        with pytest.raises(RequestError, match="Hash mismatch"):
            MessageParser.parse(bytes(wire))

    def test_parse_unknown_type_raises(self, backend):
        """Direct parse() calls keep raising on unknown type codes."""
        with pytest.raises(RequestError, match="Unknown message type code: 60000"):
            MessageParser.parse(_make_frame(60000, b"x"))

    def test_parse_too_short_raises(self, backend):
        """Frames below the header size raise on both backends."""
        with pytest.raises(RequestError, match="Data too short"):
            MessageParser.parse(b"VX")


class TestCompileBackend:
    def test_compile_matches_reference_frame(self, backend, test_message_type):
        """Compiled output matches the pure-Python reference frame bytes."""
        wire = Request(test_message_type, b"packed", request_id=99).compile()
        assert wire == _make_frame(test_message_type.code, b"packed", 99)

    def test_compile_without_request_id(self, backend, test_message_type):
        """request_id=None serializes as two zero bytes on both backends."""
        wire = Request(test_message_type, b"no id").compile()
        assert wire == _make_frame(test_message_type.code, b"no id", 0)

    def test_compile_invalid_request_id_raises(self, backend, test_message_type):
        """Out-of-range request_id raises RequestError before compilation."""
        with pytest.raises(RequestError, match="request_id must be an int between"):
            Request(test_message_type, b"x", request_id=70000).compile()
