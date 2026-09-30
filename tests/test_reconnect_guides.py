"""Guiding messages for the client reconnect flow."""

import socket
import threading
import time
from unittest.mock import patch

import pytest

from veltix import Client, ClientConfig, DisconnectReason, ServerFullError
from veltix.client.reconnect_handler import ReconnectHandler
from veltix.internal.bus import VeltixBus


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until(condition, timeout: float = 2.0, interval: float = 0.01) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(interval)
    return condition()


class _AlwaysFailContext:
    """Fake client context whose connect attempts always fail."""

    def __init__(self) -> None:
        self.config = ClientConfig(server_addr="127.0.0.1", port=0, retry=2, retry_delay=0.01)
        self.states: list = []
        self.connected = False
        self.running = False

    def _context_connect(self) -> bool:
        return False

    def _context_on_disconnect(self, state) -> None:
        self.states.append(state)

    def _context_init(self) -> None:
        pass

    def _context_set_running(self, value) -> None:
        self.running = value

    def _context_set_connected(self, value) -> None:
        self.connected = value

    def _context_get_request_handler(self):
        return None

    def _context_get_on_recv(self):
        return None

    def _context_get_socket(self):
        return None


class _BlockingConnectContext(_AlwaysFailContext):
    """Fake context whose connect blocks, keeping the reconnect loop active."""

    def __init__(self) -> None:
        super().__init__()
        self.config = ClientConfig(server_addr="127.0.0.1", port=0, retry=5, retry_delay=10.0)
        self.release = threading.Event()

    def _context_connect(self) -> bool:
        self.release.wait(2.0)
        return False


@pytest.mark.usefixtures("socket_core_backend")
class TestConnectFailureGuides:
    def test_connection_refused_error_guides(self) -> None:
        port = find_free_port()
        client = Client(ClientConfig(server_addr="127.0.0.1", port=port, retry=0))

        with patch.object(client.bus, "error") as err:
            result = client.connect()

        assert result is False
        messages = " ".join(str(c[0]) for c in err.call_args_list)
        assert "Fix:" in messages
        assert "server" in messages

    def test_server_full_error_guides(self) -> None:
        client = Client(ClientConfig(server_addr="127.0.0.1", port=find_free_port()))

        with (
            patch.object(client.socket, "connect", side_effect=ServerFullError("full")),
            patch.object(client.bus, "error") as err,
            pytest.raises(ServerFullError),
        ):
            client.connect()

        messages = " ".join(str(c[0]) for c in err.call_args_list)
        assert "Fix:" in messages
        assert "max_connection" in messages


@pytest.mark.usefixtures("socket_core_backend")
class TestRetryGuides:
    def test_retry_with_zero_config_warns_and_does_not_fire_disconnect(self) -> None:
        port = find_free_port()
        client = Client(ClientConfig(server_addr="127.0.0.1", port=port, retry=0, retry_delay=0.1))
        states = []
        client.on_disconnect(lambda s: states.append(s))

        with patch.object(client.bus, "warning") as warn:
            client.retry()
            assert _wait_until(lambda: warn.call_count > 0), "retry() did not warn"

        message = warn.call_args[0][0]
        assert "retry" in message.lower()
        assert "max_" in message
        assert "Fix:" in message
        # No spurious permanent disconnect when there is nothing to retry.
        assert len(states) == 0


class TestReconnectLoopGuides:
    def test_exhausted_retries_log_guide(self) -> None:
        bus = VeltixBus()
        ctx = _AlwaysFailContext()
        handler = ReconnectHandler(ctx, bus=bus)
        handler.init_connect()

        with patch.object(handler.bus, "error") as err:
            result = handler.reconnect_loop(reason=DisconnectReason.ERROR, retry_max=2)

        assert result is False
        last = err.call_args_list[-1][0][0]
        assert "Fix:" in last
        assert "attempt" in last.lower()

    def test_retry_ignored_when_loop_active_guides(self) -> None:
        bus = VeltixBus()
        ctx = _BlockingConnectContext()
        handler = ReconnectHandler(ctx, bus=bus)
        handler.init_connect()

        thread = threading.Thread(target=handler._retry_in_thread, daemon=True)
        thread.start()
        try:
            assert _wait_until(lambda: handler._reconnect_lock.locked()), (
                "reconnect loop did not start"
            )

            with patch.object(handler.bus, "warning") as warn:
                handler._retry_in_thread()
            message = warn.call_args[0][0]
            assert "retry() ignored" in message
            assert "Fix:" in message
            assert "stop_retry" in message
        finally:
            ctx.release.set()
            handler.stop_retry()
            thread.join(timeout=2.0)
