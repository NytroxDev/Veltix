"""Tests for send_and_wait functionality."""

import socket

import pytest

from veltix import Client, ClientConfig, Events, MessageType, Request, Server, ServerConfig


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.usefixtures("socket_core_backend")
class TestSendAndWait:
    def test_client_send_and_wait(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))

        def on_message(client_info, response2):
            echo = Request(response2.type, response2.content, request_id=response2.request_id)
            server.sender.send(echo, client=client_info.conn)

        server.set_callback(Events.ON_RECV, on_message)
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client.connect()

        msg_type = MessageType(code=2303, name="echo_test")
        request = Request(msg_type, b"Echo this message!")
        response = client.send_and_wait(request, timeout=2.0)

        assert response is not None
        assert response.content == b"Echo this message!"
        assert response.request_id == request.request_id

        client.disconnect()
        server.close_all()

    def test_server_send_and_wait(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))

        def on_message(response2):
            echo = Request(response2.type, response2.content, request_id=response2.request_id)
            client.sender.send(echo)

        client.set_callback(Events.ON_RECV, on_message)
        client.connect()

        msg_type = MessageType(code=2304, name="server_echo")
        request = Request(msg_type, b"Server to client")
        response = server.send_and_wait(request, server.clients[0], timeout=2.0)

        assert response is not None
        assert response.content == b"Server to client"

        client.disconnect()
        server.close_all()

    def test_send_and_wait_timeout(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.set_callback(Events.ON_RECV, lambda _c, _r: None)
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client.connect()

        msg_type = MessageType(code=2305, name="timeout_test")
        response = client.send_and_wait(Request(msg_type, b"No response"), timeout=0.5)

        assert response is None

        client.disconnect()
        server.close_all()
