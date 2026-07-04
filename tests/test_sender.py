"""Tests for Sender — send and broadcast."""

from unittest.mock import MagicMock

import pytest

from veltix import MessageType, Mode, Request, Sender, SenderError
from veltix.network.request import HEADER_SIZE

# ── Fixture ───────────────────────────────────────────────────────────────────


def make_mock_socket() -> MagicMock:
    """Create a mock socket that behaves like BaseSocket."""
    mock = MagicMock()
    mock.send = MagicMock(return_value=True)
    return mock


MSG_TYPE = MessageType(code=3100, name="sender_test")


# ── Init ──────────────────────────────────────────────────────────────────────


class TestSenderInit:
    def test_client_mode_requires_socket(self):
        with pytest.raises(SenderError):
            Sender(mode=Mode.CLIENT, conn=None)

    def test_server_mode_no_socket_required(self):
        sender = Sender(mode=Mode.SERVER)
        assert sender.mode == Mode.SERVER
        assert not sender.is_client

    def test_client_mode_with_socket(self):
        sock = make_mock_socket()
        sender = Sender(mode=Mode.CLIENT, conn=sock)
        assert sender.is_client
        assert sender.conn is sock


# ── send ──────────────────────────────────────────────────────────────────────


class TestSenderSend:
    def test_client_send_success(self):
        sock = make_mock_socket()
        sender = Sender(mode=Mode.CLIENT, conn=sock)
        request = Request(MSG_TYPE, b"hello")
        result = sender.send(request)
        assert result is True
        sock.send.assert_called_once()

    def test_client_send_calls_compile(self):
        sock = make_mock_socket()
        sender = Sender(mode=Mode.CLIENT, conn=sock)
        request = Request(MSG_TYPE, b"test")
        sender.send(request)
        sent_data = sock.send.call_args[0][0]
        assert isinstance(sent_data, bytes)
        assert len(sent_data) == HEADER_SIZE + len(b"test")

    def test_server_send_no_client_returns_false(self):
        sender = Sender(mode=Mode.SERVER)
        request = Request(MSG_TYPE, b"hello")
        result = sender.send(request, client=None)
        assert result is False

    def test_server_send_with_client(self):
        sock = make_mock_socket()
        sender = Sender(mode=Mode.SERVER)
        request = Request(MSG_TYPE, b"hello")
        result = sender.send(request, client=sock)
        assert result is True
        sock.send.assert_called_once()

    def test_send_connection_reset_returns_false(self):
        sock = make_mock_socket()
        sock.send.side_effect = ConnectionResetError
        sender = Sender(mode=Mode.CLIENT, conn=sock)
        result = sender.send(Request(MSG_TYPE, b"hello"))
        assert result is False

    def test_send_broken_pipe_returns_false(self):
        sock = make_mock_socket()
        sock.send.side_effect = BrokenPipeError
        sender = Sender(mode=Mode.CLIENT, conn=sock)
        result = sender.send(Request(MSG_TYPE, b"hello"))
        assert result is False


# ── broadcast ─────────────────────────────────────────────────────────────────


class TestSenderBroadcast:
    def test_broadcast_to_all(self):
        sockets = [make_mock_socket() for _ in range(3)]
        sender = Sender(mode=Mode.SERVER)
        request = Request(MSG_TYPE, b"broadcast")
        result = sender.broadcast(request, sockets)
        assert result is True
        for sock in sockets:
            sock.send.assert_called_once()

    def test_broadcast_empty_list(self):
        sender = Sender(mode=Mode.SERVER)
        result = sender.broadcast(Request(MSG_TYPE, b"test"), [])
        assert result is True

    def test_broadcast_with_exclusion(self):
        sockets = [make_mock_socket() for _ in range(3)]
        sender = Sender(mode=Mode.SERVER)
        request = Request(MSG_TYPE, b"broadcast")
        result = sender.broadcast(request, sockets, except_clients=[sockets[0]])
        assert result is True
        sockets[0].send.assert_not_called()
        sockets[1].send.assert_called_once()
        sockets[2].send.assert_called_once()

    def test_broadcast_client_mode_returns_false(self):
        sock = make_mock_socket()
        sender = Sender(mode=Mode.CLIENT, conn=sock)
        result = sender.broadcast(Request(MSG_TYPE, b"test"), [sock])
        assert result is False

    def test_broadcast_partial_failure_returns_false(self):
        sockets = [make_mock_socket() for _ in range(3)]
        sockets[1].send.side_effect = ConnectionResetError
        sender = Sender(mode=Mode.SERVER)
        result = sender.broadcast(Request(MSG_TYPE, b"test"), sockets)
        assert result is False
        # Other sockets should still have been called
        sockets[0].send.assert_called_once()
        sockets[2].send.assert_called_once()
