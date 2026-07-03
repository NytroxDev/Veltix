"""Tests for MessageType and MessageTypeRegistry."""

import pytest

from veltix import ERROR, INVALID_REQUEST, PING, PONG, MessageType, MessageTypeError
from veltix.network.types import MessageTypeRegistry


class TestMessageType:
    def test_create_message_type(self):
        msg_type = MessageType(code=1250, name="custom", description="Custom type")
        assert msg_type.code == 1250
        assert msg_type.name == "custom"
        assert msg_type.description == "Custom type"

    def test_message_type_auto_register(self):
        MessageType(code=1251, name="auto_reg")
        retrieved = MessageTypeRegistry.get(1251)
        assert retrieved is not None
        assert retrieved.code == 1251
        assert retrieved.name == "auto_reg"

    def test_duplicate_code_raises_error(self):
        MessageType(code=1252, name="first")
        with pytest.raises(MessageTypeError):
            MessageType(code=1252, name="duplicate")

    def test_invalid_code_range(self):
        with pytest.raises(MessageTypeError):
            MessageType(code=-1, name="negative")
        with pytest.raises(MessageTypeError):
            MessageType(code=70000, name="too_big")

    def test_message_type_equality(self):
        msg1 = MessageType(code=1253, name="type1")
        msg2 = MessageType(code=1254, name="type2")
        msg1_copy = MessageTypeRegistry.get(1253)
        assert msg1 == msg1_copy
        assert msg1 != msg2

    def test_system_types_exist(self):
        assert PING.code == 0
        assert PONG.code == 1
        assert PING.name == "ping"
        assert PONG.name == "pong"

    def test_error_types_exist(self):
        """Test that error system types are registered."""
        assert ERROR.code == 20
        assert INVALID_REQUEST.code == 21
        assert ERROR.name == "error"
        assert INVALID_REQUEST.name == "invalid_request"
