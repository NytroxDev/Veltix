"""Tests for socket_core module: SocketEvents, BaseSocket ABC."""

import socket

from veltix.socket_core.base_socket import BaseSocket, SocketEvents
from veltix.socket_core.core import SocketCore


class TestSocketEvents:
    def test_enum_members(self):
        assert SocketEvents.CONNECT.value == "connect"
        assert SocketEvents.DISCONNECT.value == "disconnect"
        assert SocketEvents.RECV.value == "recv"

    def test_enum_distinct(self):
        members = set(SocketEvents)
        assert len(members) == 3


class TestSocketCore:
    def test_threading_value(self):
        from veltix.socket_core.threading_socket import ThreadingSocket

        assert SocketCore.THREADING.value is ThreadingSocket

    def test_async_value(self):
        from veltix.socket_core.async_socket import AsyncSocket

        assert SocketCore.ASYNC.value is AsyncSocket

    def test_socket_core_enum_members(self):
        members = set(SocketCore)
        assert len(members) == 2


class TestBaseSocketABC:
    """Test that socket implementations satisfy the BaseSocket ABC."""

    def _make_handler(self):
        from veltix.handler.request_handler import RequestHandler
        from veltix.network.sender import Mode, Sender

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sender = Sender(mode=Mode.CLIENT, conn=s)
        return RequestHandler(sender=sender, mode=Mode.CLIENT)

    def test_threading_socket_is_base_socket(self):
        """ThreadingSocket should satisfy BaseSocket ABC at runtime."""
        from veltix.socket_core.threading_socket import ThreadingSocket

        handler = self._make_handler()
        ts = ThreadingSocket(request_handler=handler, max_message_size=1024)
        assert isinstance(ts, BaseSocket) is True

    def test_async_socket_is_base_socket(self):
        """AsyncSocket should satisfy BaseSocket ABC at runtime."""
        from veltix.socket_core.async_socket import AsyncSocket

        handler = self._make_handler()
        aio = AsyncSocket(request_handler=handler, max_message_size=1024)
        assert isinstance(aio, BaseSocket) is True

    def test_socket_core_creates_threading(self):
        """SocketCore.THREADING should create a ThreadingSocket instance."""
        from veltix.socket_core.threading_socket import ThreadingSocket

        handler = self._make_handler()
        instance = SocketCore.THREADING.value(handler, 1024)
        assert isinstance(instance, ThreadingSocket)

    def test_socket_core_creates_async(self):
        """SocketCore.ASYNC should create an AsyncSocket instance."""
        from veltix.socket_core.async_socket import AsyncSocket

        handler = self._make_handler()
        instance = SocketCore.ASYNC.value(handler, 1024)
        assert isinstance(instance, AsyncSocket)

    def test_socket_core_str(self):
        assert str(SocketCore.THREADING) == "SocketCore.THREADING"
        assert str(SocketCore.ASYNC) == "SocketCore.ASYNC"
