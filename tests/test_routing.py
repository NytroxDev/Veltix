"""Tests for the routing system — v1.5.0."""

import socket
import time

import pytest

from veltix import Client, ClientConfig, Events, MessageType, Request, Server, ServerConfig
from veltix.network.request import Response
from veltix.server.client_info import ClientInfo


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_condition(condition, timeout=5.0, interval=0.02):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(interval)
    return False


@pytest.mark.usefixtures("socket_core_backend")
class TestServerRouting:
    """Tests for @server.route() decorator."""

    def test_route_basic(self, test_message_type):
        """Registered route should be called when matching message type arrives."""
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        received = []

        @server.route(test_message_type)
        def on_msg(client: ClientInfo, response: Response):
            received.append(response)

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client.connect()
        client.sender.send(Request(test_message_type, b"hello"))

        assert wait_for_condition(lambda: len(received) == 1, timeout=2.0)
        assert received[0].type == test_message_type

        client.disconnect()
        server.close_all()

    def test_route_priority_over_on_recv(self, test_message_type):
        """Route should take priority over on_recv for matching message type."""
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        routed = []
        fallback = []

        @server.route(test_message_type)
        def on_msg(client: ClientInfo, response: Response):
            routed.append(True)

        server.set_callback(Events.ON_RECV, lambda c, r: fallback.append(True))

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client.connect()
        client.sender.send(Request(test_message_type, b"hello"))

        assert wait_for_condition(lambda: len(routed) == 1, timeout=2.0)
        assert len(fallback) == 0

        client.disconnect()
        server.close_all()

    def test_unregistered_type_falls_to_on_recv(self, test_message_type):
        """Message with no matching route should fall through to on_recv."""
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        fallback = []

        server.set_callback(Events.ON_RECV, lambda c, r: fallback.append(r))

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client.connect()
        client.sender.send(Request(test_message_type, b"hello"))

        assert wait_for_condition(lambda: len(fallback) == 1, timeout=2.0)
        assert fallback[0].type == test_message_type

        client.disconnect()
        server.close_all()

    def test_route_not_called_for_other_types(self, test_message_type):
        """Route for one type should not be called when another type arrives."""
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        other_type = MessageType(
            code=test_message_type.code + 100, name=f"other_{test_message_type.code}"
        )
        routed = []

        @server.route(test_message_type)
        def on_msg(client: ClientInfo, response: Response):
            routed.append(True)

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client.connect()
        client.sender.send(Request(other_type, b"hello"))

        time.sleep(0.2)
        assert len(routed) == 0

        client.disconnect()
        server.close_all()

    def test_register_duplicate_returns_false(self, test_message_type):
        """Registering the same type twice should return False."""
        server = Server(ServerConfig(host="127.0.0.1", port=find_free_port()))

        result1 = server.request_handler.register_route(test_message_type, lambda c, r: None)
        result2 = server.request_handler.register_route(test_message_type, lambda c, r: None)

        assert result1 is True
        assert result2 is False

        server.close_all()

    def test_unregister_route(self, test_message_type):
        """After unregistering, message should fall through to on_recv."""
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        routed = []
        fallback = []

        @server.route(test_message_type)
        def on_msg(client: ClientInfo, response: Response):
            routed.append(True)

        server.set_callback(Events.ON_RECV, lambda c, r: fallback.append(True))
        server.request_handler.unregister_route(test_message_type)

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client.connect()
        client.sender.send(Request(test_message_type, b"hello"))

        assert wait_for_condition(lambda: len(fallback) == 1, timeout=2.0)
        assert len(routed) == 0

        client.disconnect()
        server.close_all()

    def test_unregister_nonexistent_returns_false(self, test_message_type):
        """Unregistering a type that was never registered should return False."""
        server = Server(ServerConfig(host="127.0.0.1", port=find_free_port()))

        result = server.request_handler.unregister_route(test_message_type)
        assert result is False

        server.close_all()

    def test_multiple_routes(self, test_message_type):
        """Multiple routes should each handle their respective types."""
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        type_b = MessageType(code=test_message_type.code + 100, name=f"b_{test_message_type.code}")
        received_a = []
        received_b = []

        @server.route(test_message_type)
        def on_a(client: ClientInfo, response: Response):
            received_a.append(True)

        @server.route(type_b)
        def on_b(client: ClientInfo, response: Response):
            received_b.append(True)

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client.connect()
        client.sender.send(Request(test_message_type, b"a"))
        client.sender.send(Request(type_b, b"b"))

        assert wait_for_condition(
            lambda: len(received_a) == 1 and len(received_b) == 1, timeout=2.0
        )

        client.disconnect()
        server.close_all()


@pytest.mark.usefixtures("socket_core_backend")
class TestClientRouting:
    """Tests for @client.route() decorator."""

    def test_client_route_basic(self, test_message_type):
        """Registered route on client should be called when matching message arrives."""
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))

        received = []

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))

        @client.route(test_message_type)
        def on_msg(response: Response, client=None):
            received.append(response)

        server.set_callback(
            Events.ON_CONNECT,
            lambda c: server.sender.send(
                Request(test_message_type, b"from server"), client=c.conn
            ),
        )

        server.start()
        client.connect()

        assert wait_for_condition(lambda: len(received) == 1, timeout=2.0)
        assert received[0].type == test_message_type

        client.disconnect()
        server.close_all()

    def test_client_route_priority_over_on_recv(self, test_message_type):
        """Client route should take priority over on_recv."""
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))

        routed = []
        fallback = []

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))

        @client.route(test_message_type)
        def on_msg(response: Response, client=None):
            routed.append(True)

        client.set_callback(Events.ON_RECV, lambda r: fallback.append(True))

        server.set_callback(
            Events.ON_CONNECT,
            lambda c: server.sender.send(
                Request(test_message_type, b"from server"), client=c.conn
            ),
        )

        server.start()
        client.connect()

        assert wait_for_condition(lambda: len(routed) == 1, timeout=2.0)
        assert len(fallback) == 0

        client.disconnect()
        server.close_all()
