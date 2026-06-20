"""Tests for auto-reconnect functionality — v1.5.0."""

import socket
import threading
import time

import pytest

from veltix import Client, ClientConfig, Events, Server, ServerConfig


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


def _wait_for_disconnect(client: Client, timeout: float = 2.0) -> bool:
    """Wait up to `timeout` seconds for the client to detect a disconnection."""
    return wait_for_condition(lambda: not client.is_connected, timeout)


def _wait_for_connect(client: Client, timeout: float = 5.0) -> bool:
    """Wait up to `timeout` seconds for the client to (re)connect."""
    return wait_for_condition(lambda: client.is_connected, timeout)


def _wait_for_reconnect(reconnect_count: list, min_count: int = 2, timeout: float = 5.0) -> bool:
    """Wait up to `timeout` seconds for the reconnect callback to fire `min_count` times."""
    return wait_for_condition(lambda: len(reconnect_count) >= min_count, timeout)


@pytest.mark.usefixtures("socket_core_backend")
class TestRetryInitial:
    """Tests for retry on initial connect() failure."""

    def test_no_retry_by_default(self):
        """retry=0 should return False immediately without retrying."""
        port = find_free_port()
        client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        start = time.time()
        result = client.connect()
        elapsed = time.time() - start

        assert result is False
        assert elapsed < 1.0  # should fail fast, no waiting

    def test_retry_exhausted_returns_false(self):
        """All retry attempts exhausted should return False."""
        port = find_free_port()
        client = Client(ClientConfig(server_addr="127.0.0.1", port=port, retry=3, retry_delay=0.1))
        result = client.connect()
        assert result is False
        assert client._fail_count == 3

    def test_retry_succeeds_when_server_starts_late(self):
        """Client should connect successfully if server starts during retry window."""
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))

        attempt_count = []

        original_try_reconnect = Client._try_reconnect

        def patched_try_reconnect(self_, reason):
            attempt_count.append(1)
            return original_try_reconnect(self_, reason)

        Client._try_reconnect = patched_try_reconnect

        def start_server_late():
            time.sleep(0.3)
            server.start()

        threading.Thread(target=start_server_late, daemon=True).start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port, retry=5, retry_delay=0.2))
        result = client.connect()

        Client._try_reconnect = original_try_reconnect  # restore

        assert result is True
        assert client.is_connected
        assert len(attempt_count) > 0

        client.disconnect()
        server.close_all()

    def test_fail_count_resets_after_success(self):
        """_fail_count should be reset to 0 after a successful connection."""
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))

        def start_late():
            time.sleep(0.2)
            server.start()

        threading.Thread(target=start_late, daemon=True).start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port, retry=5, retry_delay=0.15))
        client.connect()

        assert client._fail_count == 0

        client.disconnect()
        server.close_all()

    def test_retry_delay_is_respected(self):
        """retry_delay should be respected between attempts."""
        port = find_free_port()
        client = Client(ClientConfig(server_addr="127.0.0.1", port=port, retry=2, retry_delay=0.3))
        start = time.time()
        client.connect()
        elapsed = time.time() - start

        assert elapsed >= 0.3


@pytest.mark.usefixtures("socket_core_backend")
class TestAutoReconnect:
    """Tests for automatic reconnection after mid-session disconnection."""

    def test_auto_reconnect_after_server_restart(self):
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        reconnected = []
        client = Client(
            ClientConfig(
                server_addr="127.0.0.1",
                port=port,
                retry=10,
                retry_delay=0.1,
                handshake_timeout=1.0,
            )
        )
        client.set_callback(Events.ON_CONNECT, lambda: reconnected.append(True))
        assert client.connect()
        assert len(reconnected) == 1

        server.close_all()

        assert _wait_for_disconnect(client), "Client did not detect disconnection in time"

        server2 = Server(ServerConfig(host="127.0.0.1", port=port))
        server2.start()

        assert _wait_for_reconnect(reconnected, 2, timeout=5.0), (
            f"Client did not reconnect, got {len(reconnected)} callbacks"
        )

        client.disconnect()
        server2.close_all()

    def test_on_disconnect_fires_on_server_crash(self):
        port = find_free_port()

        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        disconnected = []
        client = Client(ClientConfig(server_addr="127.0.0.1", port=port, retry=0))
        client.set_callback(Events.ON_DISCONNECT, lambda state: disconnected.append(True))
        client.connect()

        server.close_all()
        assert _wait_for_disconnect(client), "Client did not detect disconnection in time"

        assert len(disconnected) == 1

    def test_no_auto_reconnect_when_retry_disabled(self):
        """With retry=0, client should not reconnect after disconnection."""
        port = find_free_port()

        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port, retry=0))
        client.connect()

        server.close_all()
        assert _wait_for_disconnect(client), "Client did not detect disconnection in time"
        time.sleep(0.3)
        assert not client.is_connected

    def test_reconnect_preserves_callbacks(self):
        """Callbacks should still work after a reconnection."""
        port = find_free_port()

        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        received = []
        client = Client(
            ClientConfig(
                server_addr="127.0.0.1",
                port=port,
                retry=5,
                retry_delay=0.1,
                handshake_timeout=1.0,
            )
        )
        client.set_callback(Events.ON_CONNECT, lambda: received.append("connected"))
        client.connect()

        server.close_all()
        assert _wait_for_disconnect(client), "Client did not detect disconnection in time"

        server2 = Server(ServerConfig(host="127.0.0.1", port=port))
        server2.start()

        assert _wait_for_reconnect(received, 2, timeout=5.0), (
            f"Client did not reconnect, got {len(received)} callbacks"
        )

        client.disconnect()
        server2.close_all()
