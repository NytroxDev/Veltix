"""Integration tests for Client and Server."""

import time

from veltix import Client, ClientConfig, Events, MessageType, Request, Server, ServerConfig


class TestClientServer:
    def test_basic_connection(self):
        server = Server(ServerConfig(host="127.0.0.1", port=19999))
        messages_received = []

        def on_message(_client, response):
            messages_received.append(response.content)

        server.set_callback(Events.ON_RECV, on_message)
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=19999))
        assert client.connect()

        msg_type = MessageType(code=2300, name="test_basic")
        client.get_sender().send(Request(msg_type, b"Hello Server"))

        time.sleep(0.5)

        assert len(messages_received) > 0
        assert messages_received[0] == b"Hello Server"

        client.disconnect()
        server.close_all()

    def test_client_reconnect(self):
        server = Server(ServerConfig(host="127.0.0.1", port=19998))
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=19998))
        assert client.connect()
        assert client.is_connected

        client.disconnect()
        assert not client.is_connected

        server.close_all()

    def test_server_on_connect_callback(self):
        server = Server(ServerConfig(host="127.0.0.1", port=19997))
        connected_clients = []

        server.set_callback(Events.ON_CONNECT, lambda c: connected_clients.append(c.addr))
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=19997))
        client.connect()
        time.sleep(0.1)

        assert len(connected_clients) == 1

        client.disconnect()
        server.close_all()

    def test_client_on_connect_callback(self):
        """Test client ON_CONNECT callback fires after handshake."""
        server = Server(ServerConfig(host="127.0.0.1", port=19985))
        server.start()

        connected = []
        client = Client(ClientConfig(server_addr="127.0.0.1", port=19985))
        client.set_callback(Events.ON_CONNECT, lambda: connected.append(True))
        client.connect()

        time.sleep(0.1)
        assert len(connected) == 1

        client.disconnect()
        server.close_all()

    def test_client_on_disconnect_callback(self):
        """Test client ON_DISCONNECT callback fires on disconnect."""
        server = Server(ServerConfig(host="127.0.0.1", port=19984))
        server.start()

        disconnected = []
        client = Client(ClientConfig(server_addr="127.0.0.1", port=19984))
        client.set_callback(Events.ON_DISCONNECT, lambda state: disconnected.append(True))
        client.connect()
        client.disconnect()

        time.sleep(0.1)
        assert len(disconnected) == 1

        server.close_all()

    def test_multiple_clients(self):
        server = Server(ServerConfig(host="127.0.0.1", port=19996, max_connection=3))
        server.start()

        clients = []
        for _ in range(3):
            client = Client(ClientConfig(server_addr="127.0.0.1", port=19996))
            assert client.connect()
            clients.append(client)

        assert len(server.clients) == 3

        for client in clients:
            client.disconnect()
        server.close_all()

    def test_broadcasting(self):
        server = Server(ServerConfig(host="127.0.0.1", port=19995, max_connection=3))
        server.start()
        time.sleep(0.1)

        clients = []
        messages_received = [[], [], []]

        for i in range(3):
            client = Client(ClientConfig(server_addr="127.0.0.1", port=19995))

            def make_callback(index):
                def callback(response):
                    messages_received[index].append(response.content)

                return callback

            client.set_callback(Events.ON_RECV, make_callback(i))
            client.connect()
            clients.append(client)
            time.sleep(0.1)

        time.sleep(0.3)

        msg_type = MessageType(code=2301, name="broadcast_test")
        server.get_sender().broadcast(
            Request(msg_type, b"Broadcast to all"), server.get_all_clients_sockets()
        )

        time.sleep(0.5)

        for msgs in messages_received:
            assert len(msgs) > 0
            assert msgs[0] == b"Broadcast to all"

        for client in clients:
            client.disconnect()
        server.close_all()

    def test_broadcast_with_exclusion(self):
        server = Server(ServerConfig(host="127.0.0.1", port=19994, max_connection=3))
        server.start()
        time.sleep(0.1)

        clients = []
        messages_received = [[], [], []]

        for i in range(3):
            client = Client(ClientConfig(server_addr="127.0.0.1", port=19994))

            def make_callback(index):
                def callback(response):
                    messages_received[index].append(response.content)

                return callback

            client.set_callback(Events.ON_RECV, make_callback(i))
            client.connect()
            clients.append(client)
            time.sleep(0.05)

        time.sleep(0.2)

        msg_type = MessageType(code=2302, name="selective_broadcast")
        exclude_socket = server.clients[0].conn
        server.get_sender().broadcast(
            Request(msg_type, b"Not for everyone"),
            server.get_all_clients_sockets(),
            except_clients=[exclude_socket],
        )

        time.sleep(0.5)

        assert len(messages_received[0]) == 0
        assert len(messages_received[1]) > 0
        assert len(messages_received[2]) > 0

        for client in clients:
            client.disconnect()
        server.close_all()
