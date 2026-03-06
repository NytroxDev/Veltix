"""Shared fixtures for Veltix test suite."""

import time

import pytest

from veltix import Logger, LoggerConfig, LogLevel, MessageType

Logger(LoggerConfig(LogLevel.TRACE))

code = 200


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Give threads time to clean up after each test."""
    yield
    time.sleep(0.1)


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
