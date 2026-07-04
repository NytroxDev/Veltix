"""Tests for JSON raw-socket handshake (v1.8.0+)."""

from __future__ import annotations

import json
import socket
import struct
import threading
import time
from typing import Optional

import pytest

from veltix.handler.handshake_handler import HandshakeHandler
from veltix.internal.mode import Mode
from veltix.version import __version__

# ── Encode / decode ────────────────────────────────────────────────────────────


class TestHandshakeEncodeDecode:
    def setup_method(self) -> None:
        self.handler = HandshakeHandler(mode=Mode.SERVER)

    def test_encode_returns_bytes(self):
        result = self.handler._encode({"v": "1.8.0", "meta": {}})
        assert isinstance(result, bytes)
        assert len(result) > 2

    def test_decode_returns_dict(self):
        payload = self.handler._encode({"v": "1.8.0", "meta": {}})
        decoded = self.handler._decode(payload)
        assert decoded is not None
        assert decoded["v"] == "1.8.0"

    def test_encode_decode_roundtrip(self):
        original = {"v": "1.8.0", "meta": {"key": "val"}}
        encoded = self.handler._encode(original)
        decoded = self.handler._decode(encoded)
        assert decoded == original

    def test_encode_raises_on_bad_input(self):
        import json
        with pytest.raises(TypeError):
            self.handler._encode({"v": object()})  # type: ignore

    def test_decode_raises_on_truncated(self):
        with pytest.raises(json.JSONDecodeError):
            self.handler._decode(b"\x00\x05hello")

    def test_decode_raises_on_empty(self):
        import struct
        with pytest.raises(struct.error):
            self.handler._decode(b"")


# ── Version check ──────────────────────────────────────────────────────────────


class TestHandshakeCheckVersion:
    def setup_method(self) -> None:
        self.handler = HandshakeHandler(mode=Mode.SERVER)

    def test_compatible_version(self):
        assert self.handler._check_version(__version__) is True

    def test_incompatible_version(self):
        assert self.handler._check_version("0.0.1") is False

    def test_invalid_version_string(self):
        assert self.handler._check_version("not_a_version") is False

    def test_empty_version_string(self):
        assert self.handler._check_version("") is False


# ── Integration with real sockets ──────────────────────────────────────────────


def _find_free_port() -> int:
    """Bind to port 0 and return the assigned port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestHandshakeIntegration:
    """Test the full handshake flow using real TCP sockets."""

    def test_server_client_handshake_success(self):
        port = _find_free_port()
        server_handler = HandshakeHandler(mode=Mode.SERVER)
        client_handler = HandshakeHandler(mode=Mode.CLIENT)

        results: dict[str, Optional[bool]] = {"server": None, "client": None}

        def server_thread() -> None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))
            sock.listen(1)
            sock.settimeout(3.0)
            try:
                conn, _ = sock.accept()
                results["server"] = server_handler.do_server_handshake(conn)
                conn.close()
            except Exception:
                results["server"] = False
            finally:
                sock.close()

        t = threading.Thread(target=server_thread, daemon=True)
        t.start()
        time.sleep(0.1)

        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_sock.settimeout(3.0)
        client_sock.connect(("127.0.0.1", port))
        success, meta = client_handler.do_client_handshake(client_sock)
        client_sock.close()
        t.join()

        assert results["server"] is True
        assert success is True
        assert isinstance(meta, dict)

    def test_version_mismatch_rejected(self):
        port = _find_free_port()
        server_handler = HandshakeHandler(mode=Mode.SERVER)
        client_handler = HandshakeHandler(mode=Mode.CLIENT)

        results: dict[str, Optional[bool]] = {"server": None, "client": None}

        def server_thread() -> None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))
            sock.listen(1)
            sock.settimeout(3.0)
            try:
                conn, _ = sock.accept()
                results["server"] = server_handler.do_server_handshake(conn)
                conn.close()
            except Exception:
                results["server"] = False
            finally:
                sock.close()

        t = threading.Thread(target=server_thread, daemon=True)
        t.start()
        time.sleep(0.1)

        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_sock.settimeout(3.0)
        client_sock.connect(("127.0.0.1", port))

        server_payload = client_handler._recv_handshake(client_sock)
        assert server_payload is not None
        client_handler._send_handshake(client_sock, {"v": "0.0.1", "meta": {}})
        client_sock.close()
        t.join()

        assert results["server"] is False

    def test_handshake_timeout(self):
        port = _find_free_port()
        handler = HandshakeHandler(mode=Mode.SERVER)

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", port))
        sock.listen(1)
        sock.settimeout(3.0)

        results: list[bool] = []

        def server_thread() -> None:
            try:
                conn, _ = sock.accept()
                result = handler.do_server_handshake(conn)
                results.append(result)
                conn.close()
            except Exception:
                results.append(False)
            finally:
                sock.close()

        t = threading.Thread(target=server_thread, daemon=True)
        t.start()
        time.sleep(0.1)

        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_sock.settimeout(1.0)
        client_sock.connect(("127.0.0.1", port))
        server_payload = handler._recv_handshake(client_sock)
        assert server_payload is not None
        time.sleep(1.5)
        client_sock.close()
        t.join(timeout=3.0)

        assert len(results) == 1
        assert results[0] is False

    def test_multiple_clients_sequential(self):
        port = _find_free_port()
        server_handler = HandshakeHandler(mode=Mode.SERVER)

        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(("127.0.0.1", port))
        server_sock.listen(5)
        server_sock.settimeout(5.0)

        n_clients = 3
        server_results: list[bool] = []

        def accept_loop() -> None:
            for _ in range(n_clients):
                try:
                    conn, _ = server_sock.accept()
                    ok = server_handler.do_server_handshake(conn)
                    server_results.append(ok)
                    conn.close()
                except Exception:
                    server_results.append(False)

        t = threading.Thread(target=accept_loop, daemon=True)
        t.start()
        time.sleep(0.2)

        for _ in range(n_clients):
            client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_sock.settimeout(3.0)
            client_sock.connect(("127.0.0.1", port))
            client_handler = HandshakeHandler(mode=Mode.CLIENT)
            success, _ = client_handler.do_client_handshake(client_sock)
            assert success is True
            client_sock.close()

        t.join(timeout=3.0)
        server_sock.close()

        assert len(server_results) == n_clients
        assert all(server_results)
