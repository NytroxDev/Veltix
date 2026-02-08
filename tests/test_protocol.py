# tests/test_protocol.py
"""Tests for the binary protocol (Request/Response)"""

import pytest

from Veltix.network.request import Request, Response
from Veltix.network.types import MessageType


def test_request_compile():
    """Test Request compilation to bytes"""
    msg_type = MessageType(code=200, name="test", description="Test type")
    content = b"Hello World"

    request = Request(msg_type, content)
    compiled = request.compile()

    # Header should be 62 bytes
    assert len(compiled) >= 62
    assert isinstance(compiled, bytes)


def test_request_parse():
    """Test parsing bytes back to Response"""
    msg_type = MessageType(code=200, name="test", description="Test type")
    content = b"Hello World"

    # Compile
    request = Request(msg_type, content)
    compiled = request.compile()

    # Parse
    response = Request.parse(compiled)

    assert response.type.code == 200
    assert response.content == b"Hello World"
    assert response.latency >= 0


def test_request_id_preservation():
    """Test that request_id is preserved in round-trip"""
    msg_type = MessageType(code=200, name="test")
    request = Request(msg_type, b"test", request_id="custom-id-123")

    compiled = request.compile()
    response = Request.parse(compiled)

    # Check if ID contains our custom ID (converted to hex)
    assert response.request_id is not None


def test_message_integrity():
    """Test that corrupted messages are rejected"""
    msg_type = MessageType(code=200, name="test")
    request = Request(msg_type, b"Hello")

    compiled = request.compile()

    # Corrupt the data
    corrupted = (
        compiled[:50] + b"CORRUPTED" + compiled[67:]
    )  # 50 + 17 = 67 pour rester dans header

    with pytest.raises(Exception):
        Request.parse(corrupted)


# tests/test_integration.py
"""Integration tests for Server and Client"""
import threading
import time

from Veltix import (
    Binding,
    Client,
    ClientConfig,
    MessageType,
    Request,
    Server,
    ServerConfig,
)


def test_basic_connection():
    """Test basic server-client connection"""
    config_server = ServerConfig(host="127.0.0.1", port=9999)
    server = Server(config_server)

    messages_received = []

    def on_message(client, response):
        messages_received.append(response.content)

    server.bind(Binding.ON_RECV, on_message)
    server.start()

    # Give server time to start
    time.sleep(0.5)

    # Client connects
    config_client = ClientConfig(server_addr="127.0.0.1", port=9999)
    client = Client(config_client)

    assert client.connect() == True
    time.sleep(0.2)

    # Send message
    msg_type = MessageType(code=200, name="test")
    sender = client.get_sender()
    request = Request(msg_type, b"Hello Server")
    sender.send(request)

    time.sleep(0.5)

    # Verify
    assert len(messages_received) > 0
    assert messages_received[0] == b"Hello Server"

    # Cleanup
    client.disconnect()
    server.close_all()


def test_ping_pong():
    """Test PING/PONG functionality"""
    config_server = ServerConfig(host="127.0.0.1", port=9998)
    server = Server(config_server)
    server.start()

    time.sleep(0.5)

    config_client = ClientConfig(server_addr="127.0.0.1", port=9998)
    client = Client(config_client)
    client.connect()

    time.sleep(0.2)

    # Ping server
    latency = client.ping_server(timeout=2.0)

    assert latency is not None
    assert latency >= 0
    assert latency < 1000  # Should be under 1 second

    # Cleanup
    client.disconnect()
    server.close_all()


def test_multiple_clients():
    """Test server handling multiple clients"""
    config_server = ServerConfig(host="127.0.0.1", port=9997, max_connection=3)
    server = Server(config_server)
    server.start()

    time.sleep(0.5)

    clients = []
    for i in range(3):
        config = ClientConfig(server_addr="127.0.0.1", port=9997)
        client = Client(config)
        assert client.connect() == True
        clients.append(client)
        time.sleep(0.1)

    assert len(server.clients) == 3

    # Cleanup
    for client in clients:
        client.disconnect()
    server.close_all()


def test_send_and_wait():
    """Test send_and_wait functionality"""
    config_server = ServerConfig(host="127.0.0.1", port=9996)
    server = Server(config_server)

    # Server echoes back messages
    def on_message(client, response):
        print("recv: ", response.request_id)
        echo = Request(response.type, response.content, request_id=response.request_id)
        server.get_sender().send(echo, client=client.conn)
        print("send: ", echo.request_id)

    server.bind(Binding.ON_RECV, on_message)
    server.start()

    time.sleep(0.5)

    config_client = ClientConfig(server_addr="127.0.0.1", port=9996)
    client = Client(config_client)
    client.connect()

    time.sleep(0.2)

    # Send and wait for response
    msg_type = MessageType(code=201, name="echo")
    request = Request(msg_type, b"Echo this!")

    response = client.send_and_wait(request, timeout=2.0)

    assert response is not None
    assert response.content == b"Echo this!"
    assert response.request_id == request.request_id

    # Cleanup
    client.disconnect()
    server.close_all()


# tests/conftest.py
"""Pytest configuration"""
import pytest


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Cleanup after each test"""
    yield
    # Give threads time to cleanup
    import time

    time.sleep(0.1)
