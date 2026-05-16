"""Tests for auto-reconnect functionality — v1.5.0."""

import socket
import threading
import time

from veltix import Client, ClientConfig, Events, Server, ServerConfig


def _find_free_port() -> int:
    """Return a free TCP port on localhost to avoid conflicts."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_disconnect(client: Client, timeout: float = 2.0) -> bool:
    """Wait up to `timeout` seconds for the client to detect a disconnection."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not client.is_connected:
            return True
        time.sleep(0.05)
    return False


def _wait_for_connect(client: Client, timeout: float = 5.0) -> bool:
    """Wait up to `timeout` seconds for the client to (re)connect."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if client.is_connected:
            return True
        time.sleep(0.05)
    return False


def _wait_for_reconnect(reconnect_count: list, min_count: int = 2, timeout: float = 5.0) -> bool:
    """Wait up to `timeout` seconds for the reconnect callback to fire `min_count` times."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if len(reconnect_count) >= min_count:
            return True
        time.sleep(0.05)
    return False


class TestRetryInitial:
    """Tests for retry on initial connect() failure."""

    def test_no_retry_by_default(self):
        """retry=0 should return False immediately without retrying."""
        client = Client(ClientConfig(server_addr="127.0.0.1", port=17999))
        start = time.time()
        result = client.connect()
        elapsed = time.time() - start

        assert result is False
        assert elapsed < 1.0  # should fail fast, no waiting

    def test_retry_exhausted_returns_false(self):
        """All retry attempts exhausted should return False."""
        client = Client(ClientConfig(server_addr="127.0.0.1", port=17998, retry=3, retry_delay=0.1))
        result = client.connect()
        assert result is False
        assert client._fail_count == 3

    def test_retry_succeeds_when_server_starts_late(self):
        """Client should connect successfully if server starts during retry window."""
        port = _find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port))

        attempt_count = []  # track attempts before reset

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
        assert len(attempt_count) > 0  # at least one retry happened

        client.disconnect()
        server.close_all()

    def test_fail_count_resets_after_success(self):
        """_fail_count should be reset to 0 after a successful connection."""
        port = _find_free_port()
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
        client = Client(ClientConfig(server_addr="127.0.0.1", port=17995, retry=2, retry_delay=0.3))
        start = time.time()
        client.connect()
        elapsed = time.time() - start

        # 2 attempts × 1 sleep of 0.3s between them
        assert elapsed >= 0.3


class TestAutoReconnect:
    """Tests for automatic reconnection after mid-session disconnection."""

    def test_auto_reconnect_after_server_restart(self):
        port = _find_free_port()
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

        # Kill the server
        server.close_all()

        # Wait for client to detect the disconnection
        assert _wait_for_disconnect(client), "Client did not detect disconnection in time"

        # Restart the server
        server2 = Server(ServerConfig(host="127.0.0.1", port=port))
        server2.start()

        # Wait for ON_CONNECT to fire again (handshake-complete reconnect)
        assert _wait_for_reconnect(reconnected, 2, timeout=5.0), (
            f"Client did not reconnect, got {len(reconnected)} callbacks"
        )

        client.disconnect()
        server2.close_all()

    def test_on_disconnect_fires_on_server_crash(self):
        port = _find_free_port()

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
        port = _find_free_port()

        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port, retry=0))
        client.connect()

        server.close_all()
        # Client should still detect the disconnection (socket reset)
        assert _wait_for_disconnect(client), "Client did not detect disconnection in time"
        # But should stay disconnected (no auto-reconnect with retry=0)
        time.sleep(0.3)
        assert not client.is_connected

    def test_reconnect_preserves_callbacks(self):
        """Callbacks should still work after a reconnection."""
        port = _find_free_port()

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

        # Kill and restart
        server.close_all()
        assert _wait_for_disconnect(client), "Client did not detect disconnection in time"

        server2 = Server(ServerConfig(host="127.0.0.1", port=port))
        server2.start()

        # Wait for ON_CONNECT to fire again (handshake-complete reconnect)
        assert _wait_for_reconnect(received, 2, timeout=5.0), (
            f"Client did not reconnect, got {len(received)} callbacks"
        )

        client.disconnect()
        server2.close_all()
