"""Regression test: a stalled handshake must not freeze the ASYNC selector.

A peer that connects and never completes its handshake used to block the
selector loop for the full ``handshake_timeout`` (remote DoS on the default
ASYNC backend). The handshake now runs in a worker thread.
"""

from __future__ import annotations

import socket
import time

import pytest

from veltix import Client, ClientConfig, Server, ServerConfig


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.mark.usefixtures("socket_core_backend")
class TestHandshakeStall:
    def test_stalled_handshake_does_not_block_second_client(self) -> None:
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port, handshake_timeout=8.0))
        server.start()

        # Peer that connects but never completes its handshake.
        raw = socket.create_connection(("127.0.0.1", port))
        try:
            start = time.time()
            client = Client(ClientConfig(server_addr="127.0.0.1", port=port, handshake_timeout=2.0))
            ok = client.connect()
            elapsed = time.time() - start
            client.disconnect()

            assert ok is True, "second client could not connect while a handshake stalled"
            assert elapsed < 4.0, f"connect took {elapsed:.2f}s (selector blocked?)"
        finally:
            raw.close()
            server.close_all()
