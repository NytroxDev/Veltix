"""Tests for HELLO/HELLO_ACK handshake — updated for v1.6.6 refacto."""

import socket
import struct
import time
import zlib

import pytest

from veltix import Client, ClientConfig, Events, Server, ServerConfig
from veltix.handler.handshake_handler import HandshakeHandler
from veltix.internal.compatibility import Version
from veltix.network.sender import Mode, Sender
from veltix.network.request import MAGIC, HEADER_SIZE
from veltix.version import __version__


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
        result = handler.version.is_compatible(other)
        assert not result  # False or None — both mean reject


# ── Integration ───────────────────────────────────────────────────────────────

@pytest.mark.usefixtures("socket_core_backend")
class TestHandshakeIntegration:
    def test_handshake_completes_on_connect(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        result = client.connect()

        assert result is True
        assert client.is_connected
        assert wait_for_condition(lambda: server.clients[0].handshake_done is True, timeout=2.0)

        client.disconnect()
        server.close_all()

    def test_handshake_done_flag_on_client_info(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client.connect()

        assert wait_for_condition(
            lambda: server.clients[0].handshake_done is True, timeout=2.0
        )

        client.disconnect()
        server.close_all()

    def test_on_connect_fires_after_handshake(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        handshake_states = []

        def on_connect(client_info):
            handshake_states.append(client_info.handshake_done)

        server.set_callback(Events.ON_CONNECT, on_connect)
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        client.connect()

        assert wait_for_condition(lambda: len(handshake_states) == 1, timeout=2.0)
        assert handshake_states[0] is True

        client.disconnect()
        server.close_all()

    def test_handshake_timeout_returns_false(self):
        port = find_free_port()
        client = Client(ClientConfig(server_addr="127.0.0.1", port=port, handshake_timeout=1.0))
        result = client.connect()
        assert result is False

    def test_multiple_clients_all_handshake(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port, max_connection=3))
        server.start()

        clients = []
        for _ in range(3):
            client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
            assert client.connect() is True
            clients.append(client)

        assert wait_for_condition(
            lambda: all(c.handshake_done for c in server.clients), timeout=2.0
        )

        for client in clients:
            client.disconnect()
        server.close_all()

    def test_server_rejects_incompatible_version(self):
        """Server must reject a client whose HELLO_ACK contains an incompatible version."""
        port = find_free_port()
        connected = []
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.set_callback(Events.ON_CONNECT, lambda c: connected.append(c))
        server.start()

        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw.connect(("127.0.0.1", port))
        raw.settimeout(3.0)

        header = raw.recv(HEADER_SIZE)
        assert len(header) == HEADER_SIZE, "Server should send HELLO on connect"
        magic, code, size, _, request_id = struct.unpack(">2sHI4s4s", header)
        assert magic == MAGIC
        assert code == 10  # HELLO

        content = raw.recv(size)
        assert len(content) == size

        bad_version = b"0.0.1"
        bad_content = len(bad_version).to_bytes(2, "big") + bad_version
        bad_hash = zlib.crc32(bad_content).to_bytes(4, "big")
        ack_header = struct.pack(">2sHI4s4s", MAGIC, 11, len(bad_content), bad_hash, request_id)
        raw.sendall(ack_header + bad_content)

        time.sleep(0.3)

        assert len(connected) == 0, "on_connect must not fire for incompatible version"

        raw.close()
        server.close_all()
