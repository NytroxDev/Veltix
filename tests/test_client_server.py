"""Integration tests for Client and Server."""

import socket
import threading
import time

import pytest

from veltix import Client, ClientConfig, MessageType, Request, Server, ServerConfig
from veltix.handler.handshake_handler import HandshakeHandler
from veltix.internal.bus import VeltixBus
from veltix.internal.mode import Mode


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
class TestClientServer:
    def test_connect_returns_after_server_registration(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))

        assert client.connect()
        assert len(server.clients) == 1
        assert server.clients[0].handshake_done

        client.disconnect()
        server.close_all()

    def test_failed_handshake_does_not_leave_server_client(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        sock.connect(("127.0.0.1", port))

        handler = HandshakeHandler(mode=Mode.CLIENT, bus=VeltixBus())
        server_payload = handler._recv_handshake(sock)
        assert server_payload is not None

        bad_payload = handler._encode({"v": "0.0.1", "meta": {}})
        assert bad_payload is not None
        sock.sendall(bad_payload)
        sock.close()

        assert wait_for_condition(lambda: len(server.clients) == 0, timeout=2.0)

        server.close_all()

    def test_basic_connection(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        messages_received = []

        def on_message(_client, response):
            messages_received.append(response.content)

        server.on_recv(on_message)
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        assert client.connect()

        msg_type = MessageType(code=2300, name="test_basic")
        client.sender.send(Request(msg_type, b"Hello Server"))

        assert wait_for_condition(lambda: len(messages_received) > 0, timeout=2.0)
        assert messages_received[0] == b"Hello Server"

        client.disconnect()
        server.close_all()

    def test_client_reconnect(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        assert client.connect()
        assert client.is_connected

        client.disconnect()
        assert not client.is_connected

        server.close_all()

    def test_server_on_connect_callback(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        connected_clients = []

        server.on_connect(lambda c: connected_clients.append(c.addr))
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client.connect()

        assert wait_for_condition(lambda: len(connected_clients) == 1, timeout=2.0)

        client.disconnect()
        server.close_all()

    def test_client_on_connect_callback(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        connected = []
        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client.on_connect(lambda: connected.append(True))
        client.connect()

        assert wait_for_condition(lambda: len(connected) == 1, timeout=2.0)

        client.disconnect()
        server.close_all()

    def test_client_on_disconnect_callback(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        disconnected = []
        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client.on_disconnect(lambda state: disconnected.append(True))
        client.connect()
        client.disconnect()

        assert wait_for_condition(lambda: len(disconnected) == 1, timeout=2.0)

        server.close_all()

    def test_multiple_clients(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port, max_connection=3))
        server.start()

        clients = []
        for _ in range(3):
            client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
            assert client.connect()
            clients.append(client)

        assert len(server.clients) == 3

        for client in clients:
            client.disconnect()
        server.close_all()

    def test_broadcasting(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port, max_connection=3))
        server.start()

        clients = []
        messages_received = [[], [], []]
        clients_ready = threading.Event()
        ready_count = [0]
        ready_lock = threading.Lock()

        for i in range(3):
            client = Client(ClientConfig(server_addr="127.0.0.1", port=port))

            def make_callback(index):
                def callback(response):
                    messages_received[index].append(response.content)

                return callback

            client.on_recv(make_callback(i))

            def make_ready_callback(idx):
                def callback():
                    with ready_lock:
                        ready_count[0] += 1
                        if ready_count[0] == 3:
                            clients_ready.set()

                return callback

            client.on_connect(make_ready_callback(i))
            client.connect()
            clients.append(client)

        assert clients_ready.wait(timeout=10), "Not all clients connected in time"

        msg_type = MessageType(code=2301, name="broadcast_test")
        server.sender.broadcast(
            Request(msg_type, b"Broadcast to all"), server.get_all_clients_sockets()
        )

        assert wait_for_condition(
            lambda: all(len(msgs) > 0 for msgs in messages_received), timeout=2.0
        )
        for msgs in messages_received:
            assert msgs[0] == b"Broadcast to all"

        for client in clients:
            client.disconnect()
        server.close_all()

    def test_broadcast_with_exclusion(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port, max_connection=3))
        server.start()

        clients = []
        messages_received = [[], [], []]
        clients_ready = threading.Event()
        ready_count = [0]
        ready_lock = threading.Lock()

        for i in range(3):
            client = Client(ClientConfig(server_addr="127.0.0.1", port=port))

            def make_callback(index):
                def callback(response):
                    messages_received[index].append(response.content)

                return callback

            client.on_recv(make_callback(i))

            def make_ready_callback(idx):
                def callback():
                    with ready_lock:
                        ready_count[0] += 1
                        if ready_count[0] == 3:
                            clients_ready.set()

                return callback

            client.on_connect(make_ready_callback(i))
            client.connect()
            clients.append(client)

        assert clients_ready.wait(timeout=10), "Not all clients connected in time"

        msg_type = MessageType(code=2302, name="selective_broadcast")
        exclude_socket = server.clients[0].conn
        server.sender.broadcast(
            Request(msg_type, b"Not for everyone"),
            server.get_all_clients_sockets(),
            except_clients=[exclude_socket],
        )

        assert wait_for_condition(
            lambda: (
                len(messages_received[0]) == 0
                and len(messages_received[1]) > 0
                and len(messages_received[2]) > 0
            ),
            timeout=2.0,
        )

        for client in clients:
            client.disconnect()
        server.close_all()
