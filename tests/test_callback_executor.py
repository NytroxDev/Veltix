"""Tests for CallbackExecutor — v1.4.0."""

import time

import pytest

from veltix import Client, ClientConfig, Events, MessageType, Request, Server, ServerConfig
from veltix.handler.callback_executor import CallbackExecutor


class TestCallbackExecutor:
    """Unit tests for CallbackExecutor."""

    def test_submit_executes_callback(self):
        executor = CallbackExecutor(max_workers=2)
        results = []

        executor.submit(results.append, 42)
        time.sleep(0.05)

        assert results == [42]
        executor.shutdown()

    def test_submit_does_not_block(self):
        """submit() should return immediately even if callback is slow."""
        executor = CallbackExecutor(max_workers=2)
        start = time.time()

        executor.submit(time.sleep, 0.5)

        elapsed = time.time() - start
        assert elapsed < 0.1  # submit() must return immediately

        executor.shutdown()

    def test_exception_in_callback_does_not_propagate(self):
        """Exceptions inside callbacks should be caught and logged."""
        executor = CallbackExecutor(max_workers=2)

        def bad_callback():
            raise ValueError("This should not crash the executor")

        executor.submit(bad_callback)  # Should not raise
        time.sleep(0.05)

        executor.shutdown()

    def test_multiple_callbacks_execute(self):
        executor = CallbackExecutor(max_workers=4)
        results = []

        for i in range(10):
            executor.submit(results.append, i)

        time.sleep(0.2)
        assert len(results) == 10
        executor.shutdown()

    def test_shutdown_waits_for_completion(self):
        executor = CallbackExecutor(max_workers=2)
        results = []

        def slow_callback():
            time.sleep(0.1)
            results.append(True)

        executor.submit(slow_callback)
        executor.shutdown()  # Should wait for slow_callback to finish

        assert len(results) == 1


class TestCallbackExecutorIntegration:
    """Integration tests — slow on_recv should not block recv loop."""

    def test_slow_callback_does_not_block_reception(self):
        """A slow on_recv should not prevent other messages from being received."""
        server = Server(ServerConfig(host="127.0.0.1", port=18990, max_workers=4))
        received = []

        def slow_callback(_client, response):
            time.sleep(0.2)  # Simulate heavy work
            received.append(response.content)

        server.set_callback(Events.ON_RECV, slow_callback)
        server.start()

        client = Client(ClientConfig(server_addr="127.0.0.1", port=18990))
        client.connect()

        msg_type = MessageType(code=2400, name="slow_test")
        for i in range(5):
            client.get_sender().send(Request(msg_type, f"msg{i}".encode()))

        # All 5 messages should be received even though each callback takes 0.2s
        # Without thread pool this would take 1s+, here the recv loop is never blocked
        time.sleep(1.5)

        assert len(received) == 5

        client.disconnect()
        server.close_all()

    def test_max_workers_configurable(self):
        """max_workers from ServerConfig should be passed to executor."""
        server = Server(ServerConfig(host="127.0.0.1", port=18989, max_workers=8))
        assert server.request_handler._executor._max_workers == 8
        server.close_all()

    def test_client_max_workers_configurable(self):
        """max_workers from ClientConfig should be passed to executor."""
        import socket
        from veltix.network.sender import Sender, Mode
        from veltix.handler.request_handler import RequestHandler

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sender = Sender(mode=Mode.CLIENT, conn=sock)
        handler = RequestHandler(sender=sender, mode=Mode.CLIENT, max_workers=8)

        assert handler._executor._max_workers == 8
