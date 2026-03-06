"""Tests for MessageBuffer — TCP stream handling (v1.3.0)."""

import pytest

from veltix import MessageType, Request
from veltix.network.message_buffer import MessageBuffer


class TestMessageBuffer:
    def test_single_complete_message(self, test_message_type):
        """A single complete message should be extracted correctly."""
        buf = MessageBuffer()
        request = Request(test_message_type, b"Hello")
        compiled = request.compile()

        buf.add_data(compiled)
        messages = buf.extract_messages()

        assert len(messages) == 1
        assert messages[0].content == b"Hello"

    def test_partial_message(self, test_message_type):
        """Partial data should not produce messages until complete."""
        buf = MessageBuffer()
        request = Request(test_message_type, b"Hello")
        compiled = request.compile()

        # Send only half
        buf.add_data(compiled[: len(compiled) // 2])
        messages = buf.extract_messages()
        assert len(messages) == 0

        # Send the rest
        buf.add_data(compiled[len(compiled) // 2 :])
        messages = buf.extract_messages()
        assert len(messages) == 1
        assert messages[0].content == b"Hello"

    def test_multiple_concatenated_messages(self, test_message_type):
        """Multiple messages arriving together should all be extracted."""
        buf = MessageBuffer()

        msg1 = Request(test_message_type, b"First").compile()

        # Need a different type for second message
        msg_type2 = MessageType(
            code=test_message_type.code + 500, name=f"buf_test_{test_message_type.code}"
        )
        msg2 = Request(msg_type2, b"Second").compile()

        buf.add_data(msg1 + msg2)
        messages = buf.extract_messages()

        assert len(messages) == 2
        assert messages[0].content == b"First"
        assert messages[1].content == b"Second"

    def test_max_message_size(self, test_message_type):
        """Messages exceeding max_message_size should be dropped and buffer cleared."""
        buf = MessageBuffer(max_message_size=100)
        large_request = Request(test_message_type, b"X" * 200)
        compiled = large_request.compile()

        buf.add_data(compiled)
        messages = buf.extract_messages()

        # Buffer should be cleared, no messages extracted
        assert messages == []

    def test_empty_buffer(self):
        """Empty buffer should return no messages."""
        buf = MessageBuffer()
        messages = buf.extract_messages()
        assert messages == []
