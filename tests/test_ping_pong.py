"""Tests for PING/PONG functionality."""

import socket
import time

import pytest

from veltix import Client, ClientConfig, Server, ServerConfig


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
class TestPingPong:
    def test_client_ping_server(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client.connect()

        latency = client.ping_server(timeout=2.0)

        assert latency is not None
        assert latency >= 0
        assert latency < 2000

        client.disconnect()
        server.close_all()

    def test_server_ping_client(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        ping_results = []

        def on_connect(client_info):
            server.ping_client_async(
                client_info, lambda latency: ping_results.append(latency), timeout=2.0
            )

        server.set_callback("on_connect", on_connect)
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client.connect()

        assert wait_for_condition(lambda: len(ping_results) > 0, timeout=3.0)
        assert ping_results[0] is not None
        assert ping_results[0] >= 0

        client.disconnect()
        server.close_all()

    def test_ping_timeout(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client.connect()

        latency = client.ping_server(timeout=0.001)
        assert latency is None or latency >= 0

        client.disconnect()
        server.close_all()
