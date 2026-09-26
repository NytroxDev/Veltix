"""Unit tests for ThreadingSocket and AsyncSocket error paths."""

import socket
from unittest.mock import MagicMock, patch

import pytest

from veltix.internal.bus import VeltixBus
from veltix.network.message_buffer import MessageBuffer
from veltix.network.sender import Mode, Sender
from veltix.server.client_info import ClientInfo
from veltix.socket_core.managers.clients_manager import ClientEntry


def _make_handler():
    from veltix.handler.request_handler import RequestHandler
    from veltix.internal.bus import VeltixBus

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.close()
    sender = Sender(mode=Mode.CLIENT, conn=s)
    return RequestHandler(sender=sender, mode=Mode.CLIENT, bus=VeltixBus())


def _make_bus():
    return VeltixBus()


class TestThreadingSocketUnit:
    @pytest.fixture
    def sock(self):
        from veltix.socket_core.threading_socket import ThreadingSocket

        return ThreadingSocket(
            request_handler=_make_handler(), max_message_size=1024, bus=_make_bus()
        )

    def test_settimeout_failure(self, sock):
        with patch.object(socket.socket, "settimeout", side_effect=OSError("mock")):
            assert sock.settimeout(1.0) is False

    def test_bind_already_running(self, sock):
        sock._running_event.set()
        assert sock.bind("0.0.0.0", 0, -1, 1024, 0.5) is False

    def test_close_client_invalid_id(self, sock):
        assert sock.close_client(9999) is False

    def test_close_client_with_entry(self, sock):
        info = ClientInfo(conn=MagicMock(), addr=("127.0.0.1", 0), thread_id=1)
        entry = ClientEntry(id=1, info=info, buffer=MessageBuffer(1024))
        assert sock.close_client(entry) is True

    def test_close_client_with_registered_id(self, sock):
        from veltix.internal.events import ServerEvent

        info = ClientInfo(conn=MagicMock(), addr=("127.0.0.1", 0), thread_id=1)
        client_id = sock.client_manager.add_client(info)

        received = []
        sock.bus.subscribe(ServerEvent.ON_DISCONNECT, lambda e, p: received.append(p))
        assert sock.close_client(client_id) is True
        assert received == [info]

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
        sock._running_event.set()
        with patch.object(socket.socket, "accept", side_effect=Exception("mock")):
            sock._accept_loop("0.0.0.0", 8080, -1, 1024, 0.5)
        assert not sock._running_event.is_set()

    def test_accept_loop_rejects_and_closes_when_full(self, sock):
        from veltix.internal.events import ServerEvent

        conn_mock = MagicMock()
        sock._running_event.set()
        sock.client_manager.add_client(MagicMock())
        with patch.object(
            socket.socket,
            "accept",
            side_effect=[(conn_mock, ("1.2.3.4", 1234)), OSError("stop")],
        ):
            received = []
            sock.bus.subscribe(ServerEvent.CLIENT_REJECTED, lambda e, p: received.append(p))
            sock._accept_loop("0.0.0.0", 8080, 1, 1024, 0.5)

        conn_mock.close.assert_called_once()
        assert len(received) == 1
        assert not sock._running_event.is_set()

    def test_connect_handshake_failure(self, sock):
        with (
            patch.object(socket.socket, "connect"),
            patch.object(
                sock.request_handler.handshake_handler,
                "do_client_handshake",
                return_value=(False, None),
            ),
        ):
            assert sock.connect("127.0.0.1", 9999, 1024, 1.0) is False

    def test_connect_unexpected_exception(self, sock):
        with (
            patch.object(socket.socket, "connect"),
            patch.object(
                sock.request_handler.handshake_handler,
                "do_client_handshake",
                side_effect=RuntimeError("boom"),
            ),
        ):
            assert sock.connect("127.0.0.1", 9999, 1024, 1.0) is False

    def test_init_with_sock_uses_provided_socket(self, sock):
        from veltix.socket_core.threading_socket import ThreadingSocket

        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client = ThreadingSocket(
                sock.request_handler, 1024, sock.bus, sock=raw_sock, handshake_timeout=3.0
            )
            assert client._sock is raw_sock
            assert client.handshake_timeout == 3.0
        finally:
            raw_sock.close()


class TestAsyncSocketUnit:
    @pytest.fixture
    def sock(self):
        from veltix.socket_core.async_socket import AsyncSocket

        return AsyncSocket(request_handler=_make_handler(), max_message_size=1024, bus=_make_bus())

    def test_settimeout_failure(self, sock):
        with patch.object(socket.socket, "settimeout", side_effect=OSError("mock")):
            assert sock.settimeout(1.0) is False

    def test_send_failure(self, sock):
        with patch.object(socket.socket, "sendall", side_effect=OSError("mock")):
            assert sock.send(b"data") is False

    def test_send_blockingioerror_returns_false(self, sock):
        """A full send buffer must fail fast without toggling blocking mode."""
        with (
            patch.object(socket.socket, "setblocking", return_value=None) as setblocking,
            patch.object(
                socket.socket,
                "sendall",
                side_effect=BlockingIOError("mock"),
            ),
        ):
            assert sock.send(b"data") is False
            setblocking.assert_not_called()

    def test_send_full_buffer_returns_false_and_stays_nonblocking(self):
        """A full kernel send buffer returns False; the socket stays nonblocking.

        Regression: the old code switched to a blocking sendall, which never
        returned while the peer was not reading, freezing the selector loop.
        """
        from veltix.socket_core.async_socket import AsyncSocket

        a, b = socket.socketpair()
        try:
            a.setblocking(False)
            b.setblocking(False)
            a.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
            b.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)

            client = AsyncSocket(
                request_handler=_make_handler(), max_message_size=1024, bus=_make_bus()
            )
            client._sock.close()
            client._sock = a

            # Fill the kernel send buffer until not even one byte fits.
            for _ in range(4 * 1024 * 1024):
                try:
                    a.sendall(b"x")
                except (BlockingIOError, ConnectionError):
                    break

            assert client.send(b"y" * 1024) is False
            assert a.getblocking() is False
        finally:
            a.close()
            b.close()

    def test_accept_client_rejects_and_closes_when_full(self, sock):
        from veltix.internal.events import ServerEvent

        conn_mock = MagicMock()
        sock._running_event.set()
        sock.client_manager.add_client(MagicMock())
        with patch.object(socket.socket, "accept", return_value=(conn_mock, ("1.2.3.4", 1234))):
            received = []
            sock.bus.subscribe(ServerEvent.CLIENT_REJECTED, lambda e, p: received.append(p))
            sock._accept_client(max_client=1)

        conn_mock.close.assert_called_once()
        assert len(received) == 1
        assert received[0]["addr"] == ("1.2.3.4", 1234)

    def test_accept_client_blockingioerror(self, sock):
        sock._running_event.set()
        with patch.object(socket.socket, "accept", side_effect=BlockingIOError("mock")):
            sock._accept_client(max_client=-1)

    def test_accept_client_oserror(self, sock):
        sock._running_event.set()
        with patch.object(socket.socket, "accept", side_effect=OSError("mock")):
            sock._accept_client(max_client=-1)

    def test_handle_server_client_not_found(self, sock):
        sock._handle_server_client(9999, 1024)

    def test_close_client_invalid_id(self, sock):
        assert sock.close_client(9999) is False

    def test_close_client_with_entry(self, sock):
        from veltix.internal.events import ServerEvent

        info = ClientInfo(conn=MagicMock(), addr=("127.0.0.1", 0), thread_id=1)
        entry = ClientEntry(id=1, info=info, buffer=MessageBuffer(1024))
        sock.client_manager.add_client(info)

        received = []
        sock.bus.subscribe(ServerEvent.ON_DISCONNECT, lambda e, p: received.append(p))
        assert sock.close_client(entry) is True
        assert received == [info]

    def test_disconnect_not_running(self, sock):
        result = sock.disconnect()
        assert result is True

    def test_close_not_running(self, sock):
        result = sock.close()
        assert result is False

    def test_connect_handshake_failure(self, sock):
        with (
            patch.object(socket.socket, "connect"),
            patch.object(
                sock.request_handler.handshake_handler,
                "do_client_handshake",
                return_value=(False, None),
            ),
        ):
            assert sock.connect("127.0.0.1", 9999, 1024, 1.0) is False

    def test_init_with_sock_no_selector_or_buffer(self, sock):
        from veltix.socket_core.async_socket import AsyncSocket

        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client = AsyncSocket(
                sock.request_handler, 1024, sock.bus, sock=raw_sock, handshake_timeout=3.0
            )
            assert client._sock is raw_sock
            assert client.handshake_timeout == 3.0
            assert not hasattr(client, "_selector")
            assert not hasattr(client, "_client_buffer")
        finally:
            raw_sock.close()
