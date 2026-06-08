"""Tests for HELLO/HELLO_ACK handshake — updated for v1.6.6 refacto."""

import socket
import time

import pytest

from veltix import Client, ClientConfig, Events, Server, ServerConfig
from veltix.handler.handshake_handler import HandshakeHandler
from veltix.internal.compatibility import Version
from veltix.network.sender import Mode, Sender
from veltix.version import __version__


# ── Fixture ───────────────────────────────────────────────────────────────────

def make_handler(mode: Mode = Mode.CLIENT) -> HandshakeHandler:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sender = Sender(mode=Mode.CLIENT, conn=sock)
    return HandshakeHandler(sender=sender, mode=mode)


# ── Encode / decode ───────────────────────────────────────────────────────────

class TestHandshakeEncoding:
    def test_encode_decode_roundtrip(self):
        handler = make_handler()
        encoded = handler._encode_hello()
        decoded = handler._decode_hello(encoded)
        assert decoded == Version.from_str(__version__)

    def test_encode_hello_wire_format(self):
        """Wire format: [2B length][NB version UTF-8]."""
        encoded = HandshakeHandler._encode_hello()
        length = int.from_bytes(encoded[0:2], "big")
        version_bytes = encoded[2: 2 + length]
        assert version_bytes.decode("utf-8") == __version__

    def test_decode_returns_version_object(self):
        handler = make_handler()
        encoded = handler._encode_hello()
        decoded = handler._decode_hello(encoded)
        assert isinstance(decoded, Version)

    def test_decode_correct_components(self):
        handler = make_handler()
        encoded = handler._encode_hello()
        decoded = handler._decode_hello(encoded)
        expected = Version.from_str(__version__)
        assert decoded.major == expected.major
        assert decoded.minor == expected.minor
        assert decoded.patch == expected.patch


# ── Version stored on handler ─────────────────────────────────────────────────

class TestHandshakeVersion:
    def test_handler_stores_version(self):
        handler = make_handler()
        assert isinstance(handler.version, Version)
        assert handler.version == Version.from_str(__version__)

    def test_server_handler_stores_version(self):
        handler = make_handler(Mode.SERVER)
        assert handler.version == Version.from_str(__version__)

    def test_is_server_flag(self):
        server_handler = make_handler(Mode.SERVER)
        client_handler = make_handler(Mode.CLIENT)
        assert server_handler.is_server is True
        assert client_handler.is_server is False


# ── Compatibility check ───────────────────────────────────────────────────────

class TestHandshakeCompatibility:
    def test_compatible_versions_accepted(self):
        """Same version should be accepted."""
        handler = make_handler()
        assert handler.version.is_compatible(Version.from_str(__version__)) is True

    def test_incompatible_version_rejected(self):
        """Different patch version should be rejected."""
        handler = make_handler()
        other = Version(handler.version.major, handler.version.minor, handler.version.patch + 1)
        # Only check if other is registered — if not, returns None (falsy)
        result = handler.version.is_compatible(other)
        assert not result  # False or None — both mean reject


# ── Integration ───────────────────────────────────────────────────────────────

@pytest.mark.usefixtures("socket_core_backend")
class TestHandshakeIntegration:
    def test_handshake_completes_on_connect(self):
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
        server = Server(ServerConfig(host="127.0.0.1", port=18998))
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=18998))
        client.connect()
        time.sleep(0.1)

        assert server.clients[0].handshake_done is True

        client.disconnect()
        server.close_all()

    def test_on_connect_fires_after_handshake(self):
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
        client = Client(ClientConfig(server_addr="127.0.0.1", port=11112, handshake_timeout=1.0))
        result = client.connect()
        assert result is False

    def test_multiple_clients_all_handshake(self):
        server = Server(ServerConfig(host="127.0.0.1", port=18996, max_connection=3))
        server.start()

        clients = []
        for _ in range(3):
            client = Client(ClientConfig(server_addr="127.0.0.1", port=18996))
            assert client.connect() is True
            clients.append(client)

        time.sleep(0.1)

        for entry in server.clients:
            assert entry.handshake_done is True

        for client in clients:
            client.disconnect()
        server.close_all()
