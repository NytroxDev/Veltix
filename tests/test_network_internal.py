"""Tests for internal network utilities, BufferSize, events list, and system types."""

import socket

import pytest

from veltix.exceptions import NetworkError, TimeoutError
from veltix.internal.buffer_size import BufferSize
from veltix.internal.network import RecvResult, RecvStatus, recv
from veltix.network.system_types import ERROR, INVALID_REQUEST
from veltix.network.types import MessageTypeRegistry

# ── Exceptions ────────────────────────────────────────────────────────────────


class TestExceptionsCoverage:
    def test_network_error_is_veltix_error(self):
        from veltix.exceptions import VeltixError

        assert issubclass(NetworkError, VeltixError)

    def test_timeout_error_is_veltix_error(self):
        from veltix.exceptions import VeltixError

        assert issubclass(TimeoutError, VeltixError)

    def test_network_error_can_be_raised(self):
        with pytest.raises(NetworkError):
            raise NetworkError("Network failure")

    def test_timeout_error_can_be_raised(self):
        with pytest.raises(TimeoutError):
            raise TimeoutError("Operation timed out")

    def test_network_error_caught_as_veltix_error(self):
        from veltix.exceptions import VeltixError

        with pytest.raises(VeltixError):
            raise NetworkError("test")

    def test_timeout_error_caught_as_veltix_error(self):
        from veltix.exceptions import VeltixError

        with pytest.raises(VeltixError):
            raise TimeoutError("test")


# ── RecvStatus / RecvResult / recv ────────────────────────────────────────────


class TestRecvStatus:
    def test_enum_members(self):
        assert RecvStatus.OK.value == 1
        assert RecvStatus.TIMEOUT.value == 2
        assert RecvStatus.CLOSED.value == 3
        assert RecvStatus.ERROR.value == 4

    def test_enum_distinct(self):
        members = set(RecvStatus)
        assert len(members) == 4


class TestRecvResult:
    def test_ok_result(self):
        r = RecvResult(RecvStatus.OK, b"data")
        assert r.ok is True
        assert r.timed_out is False
        assert r.disconnected is False
        assert r.data == b"data"

    def test_timeout_result(self):
        r = RecvResult(RecvStatus.TIMEOUT)
        assert r.ok is False
        assert r.timed_out is True
        assert r.disconnected is False
        assert r.data is None

    def test_closed_result(self):
        r = RecvResult(RecvStatus.CLOSED)
        assert r.ok is False
        assert r.timed_out is False
        assert r.disconnected is True

    def test_error_result(self):
        r = RecvResult(RecvStatus.ERROR)
        assert r.ok is False
        assert r.timed_out is False
        assert r.disconnected is True

    def test_repr_ok(self):
        r = RecvResult(RecvStatus.OK, b"hello")
        assert "OK" in repr(r)
        assert "5 bytes" in repr(r)

    def test_repr_not_ok(self):
        r = RecvResult(RecvStatus.CLOSED)
        assert "CLOSED" in repr(r)


class TestRecvFunction:
    def test_recv_on_closed_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.close()
        result = recv(sock, 1024)
        assert result.status == RecvStatus.ERROR
        assert result.disconnected is True

    def test_recv_on_unconnected_socket_returns_error(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = recv(sock, 1024)
        # On some platforms unconnected socket may raise OSError
        assert result.status in (RecvStatus.ERROR, RecvStatus.TIMEOUT)


# ── BufferSize ────────────────────────────────────────────────────────────────


class TestBufferSize:
    def test_small_value(self):
        assert BufferSize.SMALL == 1024
        assert BufferSize.SMALL.name == "SMALL"

    def test_medium_value(self):
        assert BufferSize.MEDIUM == 8192

    def test_large_value(self):
        assert BufferSize.LARGE == 65536

    def test_huge_value(self):
        assert BufferSize.HUGE == 1048576

    def test_is_int_enum(self):
        assert isinstance(BufferSize.SMALL, int)
        assert int(BufferSize.MEDIUM) == 8192


# ── System types ──────────────────────────────────────────────────────────────


class TestSystemTypes:
    def test_error_type_code(self):
        assert ERROR.code == 20
        assert ERROR.name == "error"

    def test_invalid_request_type_code(self):
        assert INVALID_REQUEST.code == 21
        assert INVALID_REQUEST.name == "invalid_request"

    def test_error_type_registered(self):
        retrieved = MessageTypeRegistry.get(20)
        assert retrieved is not None
        assert retrieved.code == 20

    def test_invalid_request_registered(self):
        retrieved = MessageTypeRegistry.get(21)
        assert retrieved is not None
        assert retrieved.code == 21


# ── Request.respond ────────────────────────────────────────────────────────────


class TestRequestRespond:
    def test_respond_aligns_request_id(self):
        from veltix import MessageType, Request

        msg_type = MessageType(code=2600, name="respond_test")
        req = Request(msg_type, b"hello")
        original_id = req.request_id

        resp_id = 42
        from veltix.network.request import Response

        response = Response(type=msg_type, content=b"world", _hash=b"\x00" * 4, request_id=resp_id)

        req.respond(response)
        assert req.request_id == resp_id
        assert req.request_id != original_id


# ── MessageTypeRegistry.list_all ──────────────────────────────────────────────


class TestMessageTypeRegistryListAll:
    def test_list_all_returns_list(self):
        all_types = MessageTypeRegistry.list_all()
        assert isinstance(all_types, list)

    def test_list_all_contains_registered_types(self):
        from veltix import MessageType

        all_before = len(MessageTypeRegistry.list_all())
        mt = MessageType(code=2700, name="list_all_test")
        all_after = MessageTypeRegistry.list_all()
        assert len(all_after) == all_before + 1
        assert mt in all_after
