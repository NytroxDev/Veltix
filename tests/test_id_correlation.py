"""Regression tests for request-ID correlation (v3.0.1).

Covers the fix that splits the request-ID space by direction: clients
allocate from [0, 32768) and servers from [32768, 65536), so an
unsolicited push or broadcast can never carry an ID that matches a
pending ``send_and_wait`` in the opposite direction.
"""

from __future__ import annotations

import socket
import threading
import time

import pytest

from veltix import Client, ClientConfig, MessageType, Request, Server, ServerConfig

ECHO = MessageType(code=8800, name="corr_echo")
PUSH = MessageType(code=8801, name="corr_push")
QUERY = MessageType(code=8802, name="corr_query")
PUSH_BACK = MessageType(code=8803, name="corr_push_back")


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_condition(condition, timeout=5.0, interval=0.02) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(interval)
    return False


@pytest.mark.usefixtures("socket_core_backend")
class TestDirectionScopedIds:
    def test_server_push_and_broadcast_do_not_steal_client_pending(self):
        """Client send_and_wait must get its real answer even when the server
        pushes and broadcasts while the request is pending."""
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))

        push_received: list[bytes] = []
        push_event = threading.Event()

        @server.route(ECHO)
        def on_echo(client_info, response):
            # Unsolicited traffic first: under the old flat allocator these
            # carried ID 0 and stole the client's first pending response.
            server.broadcast(Request(PUSH, b"broadcast!"))
            server.send(Request(PUSH, b"unicast!"), client=client_info)
            server.send(
                Request(ECHO, response.content, request_id=response.request_id),
                client=client_info,
            )

        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))

        @client.route(PUSH)
        def on_push(response):
            push_received.append(response.content)
            push_event.set()

        assert client.connect()

        response = client.send_and_wait(Request(ECHO, b"expected!"), timeout=3.0)

        assert response is not None
        assert response.type == ECHO
        assert response.content == b"expected!"

        # Both pushes must be routed (they run in the callback pool, so poll
        # until both landed instead of relying on a single event).
        assert wait_for_condition(
            lambda: b"broadcast!" in push_received and b"unicast!" in push_received,
            timeout=2.0,
        ), f"pushes were not routed: {push_received}"

        client.disconnect()
        server.close_all()

    def test_client_push_does_not_steal_server_pending(self):
        """Server send_and_wait must get its real answer even when the client
        pushes while the request is pending."""
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))

        server_pushes: list[bytes] = []
        push_event = threading.Event()

        @server.route(PUSH_BACK)
        def on_push_back(client_info, response):
            server_pushes.append(response.content)
            push_event.set()

        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))

        @client.route(QUERY)
        def on_query(response):
            client.send(Request(PUSH_BACK, b"client push!"))
            client.send(Request(QUERY, b"answer!", request_id=response.request_id))

        assert client.connect()
        assert wait_for_condition(lambda: len(server.clients) == 1)

        response = server.send_and_wait(Request(QUERY, b"?"), client=server.clients[0], timeout=3.0)

        assert response is not None
        assert response.type == QUERY
        assert response.content == b"answer!"

        assert push_event.wait(2.0), f"client push was not routed: {server_pushes}"
        assert server_pushes == [b"client push!"]

        client.disconnect()
        server.close_all()
