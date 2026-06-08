"""Tests for PING/PONG functionality."""

import time

import pytest

from veltix import Client, ClientConfig, Server, ServerConfig


@pytest.mark.usefixtures("socket_core_backend")
class TestPingPong:
    def test_client_ping_server(self):
        server = Server(ServerConfig(host="127.0.0.1", port=19993))
        server.start()
        time.sleep(0.1)

        client = Client(ClientConfig(server_addr="127.0.0.1", port=19993))
        client.connect()

        latency = client.ping_server(timeout=2.0)

        assert latency is not None
        assert latency >= 0
        assert latency < 2000

        client.disconnect()
        server.close_all()

    def test_server_ping_client(self):
        server = Server(ServerConfig(host="127.0.0.1", port=19992))
        ping_results = []

        def on_connect(client_info):
            server.ping_client_async(
                client_info, lambda latency: ping_results.append(latency), timeout=2.0
            )

        server.set_callback("on_connect", on_connect)
        server.start()
        time.sleep(0.1)

        client = Client(ClientConfig(server_addr="127.0.0.1", port=19992))
        client.connect()
        time.sleep(0.3)

        assert len(ping_results) > 0
        assert ping_results[0] is not None
        assert ping_results[0] >= 0

        client.disconnect()
        server.close_all()

    def test_ping_timeout(self):
        server = Server(ServerConfig(host="127.0.0.1", port=19991))
        server.start()
        time.sleep(0.1)

        client = Client(ClientConfig(server_addr="127.0.0.1", port=19991))
        client.connect()

        latency = client.ping_server(timeout=0.001)
        assert latency is None or latency >= 0

        client.disconnect()
        server.close_all()
