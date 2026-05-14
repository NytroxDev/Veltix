"""Tests for auto-reconnect functionality — v1.5.0."""

import threading
import time

from veltix import Client, ClientConfig, Events, Server, ServerConfig


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
        port = 17997
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
        port = 17996
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

        # 2 retries × 0.3s = at least 0.6s
        assert elapsed >= 0.6


class TestAutoReconnect:
    """Tests for automatic reconnection after mid-session disconnection."""

    def test_auto_reconnect_after_server_restart(self):
        port = 17990
        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        reconnected = []
        client = Client(ClientConfig(server_addr="127.0.0.1", port=port, retry=5, retry_delay=0.5))
        client.set_callback(Events.ON_CONNECT, lambda: reconnected.append(True))
        assert client.connect()
        assert len(reconnected) == 1  # Initial connection

        # Kill the server
        server.close_all()
        time.sleep(0.5)

        # Restart the server
        server2 = Server(ServerConfig(host="127.0.0.1", port=port))
        server2.start()

        # Wait for reconnect with timeout
        start = time.time()
        while time.time() - start < 15:  # Max 15 seconds
            if len(reconnected) >= 2:
                break
            time.sleep(0.1)

        assert client.is_connected
        assert len(reconnected) >= 2, f"Expected 2+ reconnects, got {len(reconnected)}"

        client.disconnect()
        server2.close_all()

    def test_on_disconnect_fires_on_server_crash(self):
        port = 17989

        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        disconnected = []
        client = Client(ClientConfig(server_addr="127.0.0.1", port=port, retry=0))
        client.set_callback(Events.ON_DISCONNECT, lambda state: disconnected.append(True))
        client.connect()

        server.close_all()
        time.sleep(2.0)  # 0.3 → 1.0

        assert len(disconnected) == 1

    def test_no_auto_reconnect_when_retry_disabled(self):
        """With retry=0, client should not reconnect after disconnection."""
        port = 17988

        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=port, retry=0))
        client.connect()

        server.close_all()
        time.sleep(3.0)

        assert not client.is_connected

    def test_reconnect_preserves_callbacks(self):
        """Callbacks should still work after a reconnection."""
        port = 17987

        server = Server(ServerConfig(host="127.0.0.1", port=port))
        server.start()

        received = []
        client = Client(ClientConfig(server_addr="127.0.0.1", port=port, retry=5, retry_delay=0.3))
        client.set_callback(Events.ON_CONNECT, lambda: received.append("connected"))
        client.connect()

        # Kill and restart
        server.close_all()
        time.sleep(0.3)

        server2 = Server(ServerConfig(host="127.0.0.1", port=port))
        server2.start()

        # Wait for reconnect with timeout
        start = time.time()
        while time.time() - start < 15:
            if len(received) >= 2:
                break
            time.sleep(0.1)

        assert len(received) >= 2, f"Expected 2+ callbacks, got {len(received)}"

        client.disconnect()
        server2.close_all()
