"""Shared fixtures for Veltix test suite."""

import time

import pytest

from veltix import ClientConfig, Logger, LoggerConfig, LogLevel, MessageType, ServerConfig, SocketCore
from veltix.network.types import MessageTypeRegistry

Logger(LoggerConfig(LogLevel.TRACE))

code = 200


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Give threads time to clean up after each test."""
    saved_registry = dict(MessageTypeRegistry._registry)
    yield
    MessageTypeRegistry._registry.clear()
    MessageTypeRegistry._registry.update(saved_registry)
    time.sleep(0.3)


@pytest.fixture
def reset_logger():
    """Reset logger instance before and after each test."""
    Logger.reset_instance()
    yield
    Logger.reset_instance()


@pytest.fixture
def test_message_type():
    """Create a unique test message type per test."""
    global code
    code += 1
    return MessageType(code=code, name=f"test_msg_{code}")


@pytest.fixture(
    params=[
        pytest.param(SocketCore.THREADING, id="threading"),
        pytest.param(SocketCore.ASYNC, id="async"),
    ]
)
def socket_core_backend(request):
    """Parametrize integration tests over both socket backends.

    Monkey-patches ServerConfig.__init__ and ClientConfig.__init__ so any
    config created without an explicit ``socket_core`` gets the current
    backend value.
    """
    param = request.param

    orig_server_init = ServerConfig.__init__
    orig_client_init = ClientConfig.__init__

    def _server_init(self, *args, **kwargs):
        if "socket_core" not in kwargs:
            kwargs["socket_core"] = param
        return orig_server_init(self, *args, **kwargs)

    def _client_init(self, *args, **kwargs):
        if "socket_core" not in kwargs:
            kwargs["socket_core"] = param
        return orig_client_init(self, *args, **kwargs)

    ServerConfig.__init__ = _server_init
    ClientConfig.__init__ = _client_init

    yield

    ServerConfig.__init__ = orig_server_init
    ClientConfig.__init__ = orig_client_init
