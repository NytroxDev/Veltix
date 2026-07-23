"""Tests for JSON raw-socket handshake (v1.8.0+)."""

from __future__ import annotations

import json
import socket
import struct
import threading
import time
from typing import Optional

import pytest

from veltix import __version__
from veltix.handler.handshake_handler import HandshakeHandler
from veltix.internal.bus import VeltixBus
from veltix.internal.mode import Mode

# ── Encode / decode ────────────────────────────────────────────────────────────


class TestHandshakeEncodeDecode:
    def setup_method(self) -> None:
        self.handler = HandshakeHandler(mode=Mode.SERVER, bus=VeltixBus())

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
        with pytest.raises(TypeError):
            self.handler._encode({"v": object()})  # type: ignore

    def test_decode_raises_on_truncated(self):
        with pytest.raises(json.JSONDecodeError):
            self.handler._decode(b"\x00\x05hello")

    def test_decode_raises_on_empty(self):
        with pytest.raises(struct.error):
            self.handler._decode(b"")


# ── Version check ──────────────────────────────────────────────────────────────


class TestHandshakeCheckVersion:
    def setup_method(self) -> None:
        self.handler = HandshakeHandler(mode=Mode.SERVER, bus=VeltixBus())

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
        server_handler = HandshakeHandler(mode=Mode.SERVER, bus=VeltixBus())
        client_handler = HandshakeHandler(mode=Mode.CLIENT, bus=VeltixBus())

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
        server_handler = HandshakeHandler(mode=Mode.SERVER, bus=VeltixBus())
        client_handler = HandshakeHandler(mode=Mode.CLIENT, bus=VeltixBus())

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
        handler = HandshakeHandler(mode=Mode.SERVER, bus=VeltixBus())

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
        server_handler = HandshakeHandler(mode=Mode.SERVER, bus=VeltixBus())

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
            client_handler = HandshakeHandler(mode=Mode.CLIENT, bus=VeltixBus())
            success, _ = client_handler.do_client_handshake(client_sock)
            assert success is True
            client_sock.close()

        t.join(timeout=3.0)
        server_sock.close()

        assert len(server_results) == n_clients
        assert all(server_results)


# ── Mock socket for failure-path tests ─────────────────────────────────────────


class MockSocket:
    """Minimal mock implementing the RawSocket protocol for unit testing."""

    def __init__(
        self,
        recv_data: Optional[bytes] = None,
        send_error: Optional[Exception] = None,
        send_error_on_call: Optional[int] = None,
    ) -> None:
        self._recv_data = recv_data or b""
        self._recv_pos = 0
        self._send_error = send_error
        self._send_error_on_call = send_error_on_call
        self.sent: list[bytes] = []
        self._send_call = 0

    def settimeout(self, timeout: Optional[float]) -> None:
        pass

    def sendall(self, data: bytes) -> None:
        if self._send_error is not None:
            self._send_call += 1
            if self._send_error_on_call is None or self._send_call == self._send_error_on_call:
                raise self._send_error
        self.sent.append(data)

    def recv(self, bufsize: int) -> bytes:
        chunk = self._recv_data[self._recv_pos : self._recv_pos + bufsize]
        self._recv_pos += bufsize
        return chunk


def _mock_send_fail() -> MockSocket:
    """Socket that fails on the very first sendall."""
    return MockSocket(send_error=ConnectionResetError("send failed"))


def _mock_recv_empty() -> MockSocket:
    """Socket that returns empty bytes immediately (connection closed)."""
    return MockSocket(recv_data=b"")


def _mock_recv_partial_header() -> MockSocket:
    """Socket that returns only1 byte for the header."""
    return MockSocket(recv_data=b"\x00")


def _mock_recv_bad_version() -> MockSocket:
    """Socket that serves a valid server payload but with an incompatible version."""
    handler = HandshakeHandler(mode=Mode.SERVER, bus=VeltixBus())
    server_payload = handler._encode({"v": "0.0.1", "meta": {"id_window": 30000}})
    ack = handler._encode({"result": "ok"})
    return MockSocket(recv_data=server_payload + ack)


def _mock_ack_fail() -> MockSocket:
    """Socket that sends a valid first payload but fails on the ack send."""
    handler = HandshakeHandler(mode=Mode.SERVER, bus=VeltixBus())
    server_payload = handler._encode({"v": __version__, "meta": {"id_window": 30000}})
    return MockSocket(
        recv_data=server_payload,
        send_error=ConnectionResetError("ack failed"),
        send_error_on_call=2,
    )


def _mock_bad_ack() -> MockSocket:
    """Socket that sends a valid first payload but a wrong ack result."""
    handler = HandshakeHandler(mode=Mode.SERVER, bus=VeltixBus())
    server_payload = handler._encode({"v": __version__, "meta": {"id_window": 30000}})
    bad_ack = handler._encode({"result": "nok"})
    return MockSocket(recv_data=server_payload + bad_ack)


# ── Server failure paths ───────────────────────────────────────────────────────


class TestServerHandshakeFailurePaths:
    """Unit tests for server handshake failure branches using MockSocket."""

    def test_server_send_failed(self):
        handler = HandshakeHandler(mode=Mode.SERVER, bus=VeltixBus())
        sock = _mock_send_fail()
        assert handler.do_server_handshake(sock) is False

    def test_server_recv_failed(self):
        handler = HandshakeHandler(mode=Mode.SERVER, bus=VeltixBus())
        sock = _mock_recv_empty()
        assert handler.do_server_handshake(sock) is False

    def test_server_version_mismatch(self):
        handler = HandshakeHandler(mode=Mode.SERVER, bus=VeltixBus())
        sock = _mock_recv_bad_version()
        assert handler.do_server_handshake(sock) is False

    def test_server_ack_send_failed(self):
        handler = HandshakeHandler(mode=Mode.SERVER, bus=VeltixBus())
        sock = _mock_ack_fail()
        assert handler.do_server_handshake(sock) is False


# ── Client failure paths ───────────────────────────────────────────────────────


class TestClientHandshakeFailurePaths:
    """Unit tests for client handshake failure branches using MockSocket."""

    def test_client_recv_failed(self):
        handler = HandshakeHandler(mode=Mode.CLIENT, bus=VeltixBus())
        sock = _mock_recv_empty()
        success, meta = handler.do_client_handshake(sock)
        assert success is False
        assert meta is None

    def test_client_version_mismatch(self):
        handler = HandshakeHandler(mode=Mode.CLIENT, bus=VeltixBus())
        sock = _mock_recv_bad_version()
        success, meta = handler.do_client_handshake(sock)
        assert success is False
        assert meta is None

    def test_client_send_failed(self):
        handler = HandshakeHandler(mode=Mode.CLIENT, bus=VeltixBus())
        sock = MockSocket(
            recv_data=HandshakeHandler._encode({"v": __version__, "meta": {"id_window": 30000}}),
            send_error=ConnectionResetError("send failed"),
            send_error_on_call=1,
        )
        success, meta = handler.do_client_handshake(sock)
        assert success is False
        assert meta is None

    def test_client_ack_failed(self):
        handler = HandshakeHandler(mode=Mode.CLIENT, bus=VeltixBus())
        sock = _mock_bad_ack()
        success, meta = handler.do_client_handshake(sock)
        assert success is False
        assert meta is None

    def test_client_meta_returned_on_success(self):
        handler = HandshakeHandler(mode=Mode.CLIENT, bus=VeltixBus())
        server_payload = {"v": __version__, "meta": {"id_window": 50000}}
        encoded = HandshakeHandler._encode(server_payload)
        ack = HandshakeHandler._encode({"result": "ok"})
        sock = MockSocket(recv_data=encoded + ack)
        success, meta = handler.do_client_handshake(sock)
        assert success is True
        assert meta == {"id_window": 50000}


# ── Recv edge cases ────────────────────────────────────────────────────────────


class TestRecvHandshakeEdgeCases:
    def test_recv_partial_header(self):
        handler = HandshakeHandler(mode=Mode.SERVER, bus=VeltixBus())
        sock = _mock_recv_partial_header()
        result = handler._recv_handshake(sock)
        assert result is None

    def test_recv_partial_payload(self):
        handler = HandshakeHandler(mode=Mode.SERVER, bus=VeltixBus())
        full = handler._encode({"v": __version__, "meta": {}})
        sock = MockSocket(recv_data=full[:5])
        result = handler._recv_handshake(sock)
        assert result is None

    def test_send_handshake_returns_true_on_success(self):
        handler = HandshakeHandler(mode=Mode.SERVER, bus=VeltixBus())
        sock = MockSocket()
        assert handler._send_handshake(sock, {"v": __version__}) is True

    def test_send_handshake_returns_false_on_error(self):
        handler = HandshakeHandler(mode=Mode.SERVER, bus=VeltixBus())
        sock = _mock_send_fail()
        assert handler._send_handshake(sock, {"v": __version__}) is False

    def test_recv_exception_in_recv_all(self):
        """Cover lines 108-110: generic exception handler in _recv_handshake."""
        handler = HandshakeHandler(mode=Mode.SERVER, bus=VeltixBus())

        call_count = 0

        def exploding_recv(bufsize: int) -> bytes:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b"\x00\x05"
            raise RuntimeError("socket exploded")

        class ExcSocket:
            def settimeout(self, timeout: object) -> None:
                pass

            def sendall(self, data: bytes) -> None:
                pass

            def recv(self, bufsize: int) -> bytes:
                return exploding_recv(bufsize)

        result = handler._recv_handshake(ExcSocket())
        assert result is None
