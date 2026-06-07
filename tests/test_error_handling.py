"""Tests for error handling and exception hierarchy."""

import pytest

from veltix import (
    Client,
    ClientConfig,
    MessageType,
    MessageTypeError,
    Request,
    RequestError,
    SenderError,
    VeltixError,
)
from veltix.network.request import HEADER_SIZE, Request as Req


# ── Exception hierarchy ───────────────────────────────────────────────────────

class TestExceptionHierarchy:
    def test_veltix_error_is_base(self):
        assert issubclass(MessageTypeError, VeltixError)
        assert issubclass(RequestError, VeltixError)
        assert issubclass(SenderError, VeltixError)

    def test_veltix_error_is_exception(self):
        assert issubclass(VeltixError, Exception)

    def test_can_catch_all_with_veltix_error(self):
        with pytest.raises(VeltixError):
            raise MessageTypeError("test")

        with pytest.raises(VeltixError):
            raise RequestError("test")

        with pytest.raises(VeltixError):
            raise SenderError("test")

    def test_error_messages(self):
        err = VeltixError("something went wrong")
        assert "something went wrong" in str(err)


# ── MessageTypeError ──────────────────────────────────────────────────────────

class TestMessageTypeError:
    def test_duplicate_code_raises(self):
        MessageType(code=3200, name="err_test_1")
        with pytest.raises(MessageTypeError):
            MessageType(code=3200, name="err_test_duplicate")

    def test_invalid_code_negative(self):
        with pytest.raises(MessageTypeError):
            MessageType(code=-1, name="negative")

    def test_invalid_code_too_large(self):
        with pytest.raises(MessageTypeError):
            MessageType(code=70000, name="too_large")

    def test_invalid_code_boundary(self):
        # 65535 is valid, 65536 is not
        MessageType(code=3201, name="boundary_valid")
        with pytest.raises(MessageTypeError):
            MessageType(code=65536, name="boundary_invalid")


# ── RequestError ──────────────────────────────────────────────────────────────

class TestRequestError:
    def test_parse_too_short(self):
        with pytest.raises(RequestError) as exc:
            Req.parse(b"short")
        assert "too short" in str(exc.value)

    def test_parse_hash_mismatch(self):
        msg_type = MessageType(code=3202, name="hash_err_test")
        request = Request(msg_type, b"hello")
        compiled = bytearray(request.compile())
        compiled[HEADER_SIZE] = (compiled[HEADER_SIZE] + 1) % 256  # corrupt content
        with pytest.raises(RequestError) as exc:
            Req.parse(bytes(compiled))
        assert "Hash mismatch" in str(exc.value)

    def test_parse_unknown_message_type(self):
        msg_type = MessageType(code=3203, name="unknown_type_test")
        request = Request(msg_type, b"hello")
        compiled = bytearray(request.compile())
        compiled[0] = 0xFF
        compiled[1] = 0xFE
        with pytest.raises(RequestError) as exc:
            Req.parse(bytes(compiled))
        assert "Unknown message type" in str(exc.value)

    def test_parse_size_mismatch(self):
        msg_type = MessageType(code=3204, name="size_mismatch_test")
        request = Request(msg_type, b"hello")
        compiled = request.compile()
        with pytest.raises(RequestError) as exc:
            Req.parse(compiled + b"EXTRA")
        assert "mismatch" in str(exc.value)


# ── SenderError ───────────────────────────────────────────────────────────────

class TestSenderError:
    def test_client_mode_without_socket(self):
        from veltix import Mode, Sender
        with pytest.raises(SenderError):
            Sender(mode=Mode.CLIENT, conn=None)


# ── Network errors ────────────────────────────────────────────────────────────

class TestNetworkErrors:
    def test_connection_refused_returns_false(self):
        client = Client(ClientConfig(server_addr="127.0.0.1", port=11111))
        result = client.connect()
        assert result is False
        assert not client.is_connected

    def test_connection_refused_does_not_raise(self):
        """connect() should never raise — always return False on failure."""
        client = Client(ClientConfig(server_addr="127.0.0.1", port=11113))
        try:
            client.connect()
        except Exception as e:
            pytest.fail(f"connect() raised unexpectedly: {e}")

    def test_invalid_host_returns_false(self):
        client = Client(ClientConfig(server_addr="999.999.999.999", port=8080))
        result = client.connect()
        assert result is False
