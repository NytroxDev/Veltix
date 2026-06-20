"""Tests for advanced Server and ClientInfo features."""

import socket

import pytest

from veltix import Client, ClientConfig, MessageType, Request, Server, ServerConfig
from veltix.server.client_info import ClientInfo

def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestClientInfoProperties:
    """Tests for ClientInfo.ip and ClientInfo.port properties."""

    def make_client(self) -> ClientInfo:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        return ClientInfo(conn=sock, addr=("192.168.1.100", 8888), thread_id=1)

    def test_ip_property(self):
        client = self.make_client()
        assert client.ip == "192.168.1.100"

    def test_port_property(self):
        client = self.make_client()
        assert client.port == 8888

    def test_ip_from_constructor_addr(self):
        client = self.make_client()
        assert client.addr[0] == client.ip

    def test_port_from_constructor_addr(self):
        client = self.make_client()
        assert client.addr[1] == client.port

    def test_equality_same_id(self):
        client1 = self.make_client()
        client2 = self.make_client()
        assert client1 != client2  # different auto-generated IDs

    def test_equality_same_ref(self):
        client = self.make_client()
        assert client == client  # same object

    def test_hashable(self):
        client = self.make_client()
        s = {client}
        assert client in s


@pytest.mark.usefixtures("socket_core_backend")
class TestServerGetClientsSocketsByTag:
    """Tests for Server.get_clients_sockets_by_tag()."""

    def test_get_by_tag_no_value(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port, max_connection=2))
        server.start()

        client1 = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client2 = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client1.connect()
        client2.connect()

        server.clients[0].add_tag("admin")
        server.clients[1].add_tag("guest")

        admin_sockets = server.get_clients_sockets_by_tag("admin")
        guest_sockets = server.get_clients_sockets_by_tag("guest")

        assert len(admin_sockets) == 1
        assert len(guest_sockets) == 1
        assert admin_sockets[0] == server.clients[0].conn
        assert guest_sockets[0] == server.clients[1].conn

        client1.disconnect()
        client2.disconnect()
        server.close_all()

    def test_get_by_tag_with_value(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port, max_connection=2))
        server.start()

        client1 = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client2 = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client1.connect()
        client2.connect()

        server.clients[0].add_tag("role", value="admin")
        server.clients[1].add_tag("role", value="guest")

        admin_sockets = server.get_clients_sockets_by_tag("role", value="admin")
        guest_sockets = server.get_clients_sockets_by_tag("role", value="guest")

        assert len(admin_sockets) == 1
        assert len(guest_sockets) == 1

        client1.disconnect()
        client2.disconnect()
        server.close_all()

    def test_get_by_tag_no_match(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client.connect()

        result = server.get_clients_sockets_by_tag("nonexistent")
        assert result == []

        client.disconnect()
        server.close_all()

    def test_get_by_tag_empty_value_filter(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client.connect()

        server.clients[0].add_tag("admin")

        with_value = server.get_clients_sockets_by_tag("admin", value="nonexistent")
        without_value = server.get_clients_sockets_by_tag("admin")
        assert len(with_value) == 0
        assert len(without_value) == 1

        client.disconnect()
        server.close_all()

    def test_server_route_with_tag_filtering(self):
        """Integration: tag-based socket filtering with routing."""
        import time
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port, max_connection=2))
        server.start()

        MSG = MessageType(code=2500, name="tag_test_msg")
        received = []

        client1 = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client2 = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client1.set_callback("on_recv", lambda r: received.append("client1"))
        client2.set_callback("on_recv", lambda r: received.append("client2"))
        client1.connect()
        client2.connect()

        server.clients[0].add_tag("role", value="admin")
        server.clients[1].add_tag("role", value="guest")

        admin_sockets = server.get_clients_sockets_by_tag("role", value="admin")
        server.get_sender().broadcast(Request(MSG, b"test"), admin_sockets)

        time.sleep(0.3)
        assert len(received) == 1
        assert received[0] == "client1"

        client1.disconnect()
        client2.disconnect()
        server.close_all()


class TestClientContextAPI:
    """Tests for Client context_* API used by ReconnectHandler."""

    def test_context_get_socket(self):
        port = find_free_port()
        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        sock = client.context_get_socket()
        assert sock is not None
        client.disconnect()

    def test_context_get_request_handler(self):
        port = find_free_port()
        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        handler = client.context_get_request_handler()
        assert handler is not None
        client.disconnect()

    def test_context_get_on_recv(self):
        port = find_free_port()
        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        result = client.context_get_on_recv()
        assert result is None  # no callback set by default
        client.disconnect()

    def test_context_set_running(self):
        port = find_free_port()
        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        assert client.running is True
        client.context_set_running(False)
        assert client.running is False
        client.disconnect()

    def test_context_set_connected(self):
        port = find_free_port()
        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        assert client.is_connected is False
        client.context_set_connected(True)
        assert client.is_connected is True
        client.disconnect()

    def test_context_init_reinitializes(self):
        port = find_free_port()
        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        old_socket = client.socket
        old_handler = client.request_handler

        client.context_init()

        assert client.socket is not old_socket
        assert client.request_handler is not old_handler
        client.disconnect()


class TestServerCloseClient:
    """Tests for close_client edge cases."""

    def test_close_client_with_none(self):
        """close_client(client=None) should return False."""
        server = Server(ServerConfig(host="127.0.0.1", port=find_free_port()))
        result = server.close_client(client=None)
        assert result is False
        server.close_all()

    def test_close_client_with_id_none(self):
        """close_client(id_=None) should return False — bugfix v1.6.6."""
        server = Server(ServerConfig(host="127.0.0.1", port=find_free_port()))
        result = server.close_client(client=None, id_=None)
        assert result is False
        server.close_all()

    def test_close_client_with_zero_id(self):
        """id_=0 should not crash — bugfix v1.6.6."""
        server = Server(ServerConfig(host="127.0.0.1", port=find_free_port()))
        result = server.close_client(client=None, id_=0)
        assert result is False
        server.close_all()

    def test_close_nonexistent_client_info(self):
        """close_client with ClientInfo not in manager should return False."""
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        fake_info = ClientInfo(conn=sock, addr=("127.0.0.1", 9999), thread_id=0)
        result = server.close_client(client=fake_info)
        assert result is False
        sock.close()
        server.close_all()
