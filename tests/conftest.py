"""
Pytest configuration and shared fixtures for Veltix tests
"""

import pytest
import time
from veltix import Logger


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """
    Cleanup after each test.
    
    Gives threads time to cleanup properly and resets any global state.
    """
    yield
    # Give threads time to cleanup
    time.sleep(0.1)


@pytest.fixture
def reset_logger():
    """
    Reset logger instance before and after each test.
    
    Ensures tests don't interfere with each other through shared logger state.
    """
    Logger.reset_instance()
    yield
    Logger.reset_instance()


def pytest_configure(config):
    """Configure pytest with custom settings"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "network: marks tests that require network access"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically"""
    for item in items:
        # Add integration marker to all TestClientServer tests
        if "TestClientServer" in str(item.parent):
            item.add_marker(pytest.mark.integration)
        
        # Add network marker to all integration tests
        if "integration" in item.keywords:
            item.add_marker(pytest.mark.network)
        
        # Add unit marker to protocol and message type tests
        if any(name in str(item.parent) for name in ["TestMessageType", "TestProtocol", "TestLogger"]):
            item.add_marker(pytest.mark.unit)
