"""Unit tests for ThreadingSocket and AsyncSocket error paths."""

import socket
from unittest.mock import MagicMock, patch

import pytest

from veltix.network.message_buffer import MessageBuffer
from veltix.network.sender import Mode, Sender
from veltix.server.client_info import ClientInfo
from veltix.socket_core.managers.clients_manager import ClientEntry


def _make_handler():
    from veltix.handler.request_handler import RequestHandler

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.close()
    sender = Sender(mode=Mode.CLIENT, conn=s)
    return RequestHandler(sender=sender, mode=Mode.CLIENT)


class TestThreadingSocketUnit:
    @pytest.fixture
    def sock(self):
        from veltix.socket_core.threading_socket import ThreadingSocket

        return ThreadingSocket(request_handler=_make_handler(), max_message_size=1024)

    def test_set_callback_unknown_event(self, sock):
        assert sock.set_callback("unknown", lambda: None) is False  # type: ignore

    def test_settimeout_failure(self, sock):
        with patch.object(socket.socket, "settimeout", side_effect=OSError("mock")):
            assert sock.settimeout(1.0) is False

    def test_bind_already_running(self, sock):
        sock.running = True
        assert sock.bind("0.0.0.0", 0, -1, 1024, 0.5) is False

    def test_close_client_invalid_id(self, sock):
        assert sock.close_client(9999) is False

    def test_close_client_with_entry(self, sock):
        info = ClientInfo(conn=MagicMock(), addr=("127.0.0.1", 0), thread_id=1)
        entry = ClientEntry(id=1, info=info, buffer=MessageBuffer(1024))
        assert sock.close_client(entry) is True

    def test_close_client_with_registered_id(self, sock):
        info = ClientInfo(conn=MagicMock(), addr=("127.0.0.1", 0), thread_id=1)
        client_id = sock.client_manager.add_client(info)
        cb = MagicMock()
        sock.on_disconnect = cb
        assert sock.close_client(client_id) is True
        cb.assert_called_once_with(info)

    def test_handle_server_client_not_found(self, sock):
        with pytest.raises(ValueError, match="not found"):
            sock._handle_server_client(9999, 1024, 0.5)

    def test_close_all_not_running(self, sock):
        assert sock.close_all() is True

    def test_close_all_exception(self, sock):
        with patch.object(sock, "_shutdown_socket", side_effect=OSError("mock")):
            assert sock.close_all() is False

    def test_disconnect_not_running(self, sock):
        assert sock.disconnect() is True

    def test_close(self, sock):
        assert sock.close() is True

    def test_send_failure(self, sock):
        with patch.object(socket.socket, "sendall", side_effect=OSError("mock")):
            assert sock.send(b"data") is False

    def test_accept_loop_generic_exception(self, sock):
        sock.running = True
        with patch.object(socket.socket, "accept", side_effect=Exception("mock")), patch.object(
            sock,
            "_logger",
        ):
            sock._accept_loop("0.0.0.0", 8080, -1, 1024, 0.5)
        assert sock.running is False

    def test_connect_handshake_failure(self, sock):
        with patch.object(socket.socket, "connect"), patch.object(
            sock.request_handler.handshake_handler,
            "do_client_handshake",
            return_value=(False, None),
        ):
            assert sock.connect("127.0.0.1", 9999, 1024, 1.0) is False

    def test_connect_unexpected_exception(self, sock):
        with patch.object(socket.socket, "connect"), patch.object(
            sock.request_handler.handshake_handler,
            "do_client_handshake",
            side_effect=RuntimeError("boom"),
        ), patch.object(sock, "_logger"):
            assert sock.connect("127.0.0.1", 9999, 1024, 1.0) is False


class TestAsyncSocketUnit:
    @pytest.fixture
    def sock(self):
        from veltix.socket_core.async_socket import AsyncSocket

        return AsyncSocket(request_handler=_make_handler(), max_message_size=1024)

    def test_set_callback_unknown_event(self, sock):
        assert sock.set_callback("unknown", lambda: None) is False  # type: ignore

    def test_settimeout_failure(self, sock):
        with patch.object(socket.socket, "settimeout", side_effect=OSError("mock")):
            assert sock.settimeout(1.0) is False

    def test_send_failure(self, sock):
        with patch.object(socket.socket, "sendall", side_effect=OSError("mock")):
            assert sock.send(b"data") is False

    def test_send_blockingioerror_fallback(self, sock):
        with patch.object(
            socket.socket,
            "sendall",
            side_effect=BlockingIOError("mock"),
        ), patch.object(socket.socket, "setblocking", side_effect=OSError("mock")):
            assert sock.send(b"data") is False

    def test_send_blockingioerror_fallback_success(self, sock):
        with patch.object(
            socket.socket,
            "sendall",
            side_effect=[BlockingIOError("mock"), None],
        ), patch.object(socket.socket, "setblocking", return_value=None):
            assert sock.send(b"data") is True

    def test_accept_client_max_clients_reached(self, sock):
        sock.client_manager.add_client(sock)  # type: ignore
        with patch.object(sock, "_logger"):
            sock._accept_client(max_client=1)

    def test_accept_client_blockingioerror(self, sock):
        sock.running = True
        with patch.object(socket.socket, "accept", side_effect=BlockingIOError("mock")):
            sock._accept_client(max_client=-1)

    def test_accept_client_oserror(self, sock):
        sock.running = True
        with patch.object(socket.socket, "accept", side_effect=OSError("mock")), patch.object(
            sock,
            "_logger",
        ):
            sock._accept_client(max_client=-1)

    def test_handle_server_client_not_found(self, sock):
        sock._handle_server_client(9999, 1024)

    def test_close_client_invalid_id(self, sock):
        assert sock.close_client(9999) is False

    def test_close_client_with_entry(self, sock):
        cb = MagicMock()
        sock.on_disconnect = cb
        info = ClientInfo(conn=MagicMock(), addr=("127.0.0.1", 0), thread_id=1)
        entry = ClientEntry(id=1, info=info, buffer=MessageBuffer(1024))
        sock.client_manager.add_client(info)
        assert sock.close_client(entry) is True
        cb.assert_called_once_with(info)

    def test_disconnect_not_running(self, sock):
        result = sock.disconnect()
        assert result is False

    def test_close_not_running(self, sock):
        result = sock.close()
        assert result is False

    def test_close_all_not_running(self, sock):
        result = sock.close()
        assert result is False

    def test_connect_handshake_failure(self, sock):
        with patch.object(socket.socket, "connect"), patch.object(
            sock.request_handler.handshake_handler,
            "do_client_handshake",
            return_value=(False, None),
        ), patch.object(sock, "_logger"):
            assert sock.connect("127.0.0.1", 9999, 1024, 1.0) is False
