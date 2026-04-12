"""Tests for HELLO/HELLO_ACK handshake — v1.4.0."""

import time

from veltix import Client, ClientConfig, Events, Server, ServerConfig
from veltix.handler.handshake_handler import HandshakeHandler
from veltix.network.sender import Mode, Sender
from veltix.version import __version__


class TestHandshakeHandler:
    """Unit tests for HandshakeHandler encode/decode/version logic."""

    @staticmethod
    def _make_handler():
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sender = Sender(mode=Mode.CLIENT, conn=sock)
        return HandshakeHandler(sender=sender, mode=Mode.CLIENT)

    def test_encode_decode_roundtrip(self):
        handler = self._make_handler()
        encoded = handler._encode_hello()
        decoded = handler._decode_hello(encoded)
        assert decoded == __version__

    def test_encode_hello_format(self):
        """Verify wire format: [2B length][NB version]."""
        encoded = HandshakeHandler._encode_hello()
        length = int.from_bytes(encoded[0:2], "big")
        version_bytes = encoded[2 : 2 + length]
        assert version_bytes.decode("utf-8") == __version__

    def test_split_version_valid(self):
        handler = self._make_handler()
        result = handler.split_version("1.4.0")
        assert result == (1, 4, 0)

    def test_split_version_invalid(self):
        handler = self._make_handler()
        result = handler.split_version("not_a_version")
        assert result is None

    def test_check_version_compatible(self):
        handler = self._make_handler()
        assert handler._check_version("1.4.0", "1.4.0") is True

    def test_check_version_incompatible_patch(self):
        handler = self._make_handler()
        assert handler._check_version("1.4.3", "1.4.5") is False
        assert handler._check_version("1.4.3", "1.4.2") is False

    def test_check_version_incompatible_major(self):
        handler = self._make_handler()
        assert handler._check_version("1.4.0", "2.4.0") is False

    def test_check_version_invalid_string(self):
        handler = self._make_handler()
        assert handler._check_version("1.4.0", "invalid") is False


class TestHandshakeIntegration:
    """Integration tests for the full handshake flow."""

    def test_handshake_completes_on_connect(self):
        """connect() should block until handshake is done."""
        server = Server(ServerConfig(host="127.0.0.1", port=18999))
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=18999))
        result = client.connect()

        time.sleep(0.1)

        assert result is True
        assert client.is_connected
        assert server.clients[0].handshake_done is True

        client.disconnect()
        server.close_all()

    def test_handshake_done_flag_on_client_info(self):
        """ClientInfo.handshake_done should be True after connection."""
        server = Server(ServerConfig(host="127.0.0.1", port=18998))
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=18998))
        client.connect()
        time.sleep(0.1)

        assert server.clients[0].handshake_done is True

        client.disconnect()
        server.close_all()

    def test_on_connect_fires_after_handshake(self):
        """on_connect should only fire after handshake is complete."""
        server = Server(ServerConfig(host="127.0.0.1", port=18997))
        handshake_states = []

        def on_connect(client_info):
            handshake_states.append(client_info.handshake_done)

        server.set_callback(Events.ON_CONNECT, on_connect)
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=18997))
        client.connect()
        time.sleep(0.1)

        assert len(handshake_states) == 1
        assert handshake_states[0] is True

        client.disconnect()
        server.close_all()

    def test_handshake_timeout_returns_false(self):
        """connect() should return False if no server responds."""
        client = Client(ClientConfig(server_addr="127.0.0.1", port=11112, handshake_timeout=1.0))
        result = client.connect()
        assert result is False

    def test_multiple_clients_all_handshake(self):
        """All clients should complete the handshake."""
        server = Server(ServerConfig(host="127.0.0.1", port=18996, max_connection=3))
        server.start()

        clients = []
        for _ in range(3):
            client = Client(ClientConfig(server_addr="127.0.0.1", port=18996))
            assert client.connect() is True
            clients.append(client)

        time.sleep(0.1)

        for client_info in server.clients:
            assert client_info.handshake_done is True

        for client in clients:
            client.disconnect()
        server.close_all()
