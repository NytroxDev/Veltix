"""Tests for MessageType and MessageTypeRegistry."""

import pytest

from veltix import PING, PONG, MessageType, MessageTypeError
from veltix.network.types import (
    _USER_CODE_MAX,
    _USER_CODE_MIN,
    MessageTypeRegistry,
)


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


class TestAutoAllocate:
    def test_auto_alloc_by_name_positional(self):
        msg = MessageType("auto_pos")
        assert msg.name == "auto_pos"
        assert msg.code >= _USER_CODE_MIN
        assert msg.code <= _USER_CODE_MAX

    def test_auto_alloc_by_name_keyword(self):
        msg = MessageType(name="auto_kw")
        assert msg.name == "auto_kw"
        assert msg.code >= _USER_CODE_MIN
        assert msg.code <= _USER_CODE_MAX

    def test_auto_alloc_codes_are_unique(self):
        msg1 = MessageType("unique1")
        msg2 = MessageType("unique2")
        assert msg1.code != msg2.code

    def test_auto_alloc_first_code_is_min(self):
        msg = MessageType("first")
        assert msg.code == _USER_CODE_MIN

    def test_auto_alloc_skips_used_codes(self):
        MessageType(code=_USER_CODE_MIN, name="skip1")
        msg2 = MessageType("skip2")
        assert msg2.code == _USER_CODE_MIN + 1

    def test_auto_alloc_exhausted_raises(self):
        for i in range(_USER_CODE_MAX - _USER_CODE_MIN + 1):
            code = _USER_CODE_MIN + i
            if MessageTypeRegistry.get(code) is None:
                MessageType(code=code, name=f"fill_{i}")
        with pytest.raises(MessageTypeError, match="No available codes"):
            MessageType("exhausted")

    def test_auto_alloc_name_and_description(self):
        msg = MessageType("with_desc", description="A description")
        assert msg.name == "with_desc"
        assert msg.description == "A description"
        assert msg.code >= _USER_CODE_MIN

    def test_string_first_arg_and_name_kw_raises(self):
        with pytest.raises(MessageTypeError, match="Cannot pass a name"):
            MessageType("conflict", name="other")

    def test_system_requires_explicit_code(self):
        with pytest.raises(MessageTypeError, match="System messages must have"):
            MessageType(_system=True)

    def test_backward_compat_positional_code(self):
        msg = MessageType(5000, "backward")
        assert msg.code == 5000
        assert msg.name == "backward"

    def test_backward_compat_keyword_code(self):
        msg = MessageType(code=5001, name="backward_kw")
        assert msg.code == 5001
        assert msg.name == "backward_kw"
