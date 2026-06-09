"""Tests for MessageBuffer — TCP stream handling with protocol hardening (v1.7.0)."""

import pytest

from veltix import MessageType, Request
from veltix.network.message_buffer import MAX_BUFFER_SIZE, MessageBuffer


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

        buf.add_data(compiled[: len(compiled) // 2])
        messages = buf.extract_messages()
        assert len(messages) == 0

        buf.add_data(compiled[len(compiled) // 2 :])
        messages = buf.extract_messages()
        assert len(messages) == 1
        assert messages[0].content == b"Hello"

    def test_multiple_concatenated_messages(self, test_message_type):
        """Multiple messages arriving together should all be extracted."""
        buf = MessageBuffer()

        msg1 = Request(test_message_type, b"First").compile()

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

        assert messages == []

    def test_empty_buffer(self):
        """Empty buffer should return no messages."""
        buf = MessageBuffer()
        messages = buf.extract_messages()
        assert messages == []

    def test_corrupt_message_resync(self, test_message_type):
        """Corrupt message should be skipped and stream should resync on next message."""
        buf = MessageBuffer()

        msg1 = Request(test_message_type, b"Valid").compile()
        msg2_type = MessageType(
            code=test_message_type.code + 500, name=f"buf_test_{test_message_type.code}"
        )
        msg2 = Request(msg2_type, b"After corrupt").compile()

        corrupt = bytearray(msg1)
        corrupt[-1] ^= 0xFF

        buf.add_data(bytes(corrupt) + msg2)
        messages = buf.extract_messages()

        assert len(messages) == 1
        assert messages[0].content == b"After corrupt"

    # ── Corruption recovery ───────────────────────────────────────────────────

    def test_garbage_before_valid_frame(self, test_message_type):
        """Garbage before a valid frame should be discarded."""
        buf = MessageBuffer()
        request = Request(test_message_type, b"Hello")
        compiled = request.compile()

        garbage = b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09"
        buf.add_data(garbage + compiled)
        messages = buf.extract_messages()

        assert len(messages) == 1
        assert messages[0].content == b"Hello"

    def test_corrupted_size_field(self, test_message_type):
        """Corrupted size field (making message huge) should trigger resync."""
        buf = MessageBuffer()

        msg = Request(test_message_type, b"Hello").compile()

        msg2_type = MessageType(
            code=test_message_type.code + 500, name=f"buf_resync_{test_message_type.code}"
        )
        msg2 = Request(msg2_type, b"World").compile()

        corrupted = bytearray(msg)
        corrupted[5] = 0xFF  # corrupt size field high byte

        buf.add_data(bytes(corrupted) + msg2)
        messages = buf.extract_messages()

        assert len(messages) == 1
        assert messages[0].content == b"World"

    def test_corrupted_magic_bytes(self, test_message_type):
        """Corrupted magic bytes should trigger resync."""
        buf = MessageBuffer()

        msg = Request(test_message_type, b"Hello").compile()

        msg2_type = MessageType(
            code=test_message_type.code + 500, name=f"buf_magic_{test_message_type.code}"
        )
        msg2 = Request(msg2_type, b"World").compile()

        corrupted = bytearray(msg)
        corrupted[0] = 0x00
        corrupted[1] = 0x00

        buf.add_data(bytes(corrupted) + msg2)
        messages = buf.extract_messages()

        assert len(messages) == 1
        assert messages[0].content == b"World"

    def test_multiple_consecutive_corruptions(self, test_message_type):
        """Multiple corrupt frames between valid ones should all be skipped."""
        buf = MessageBuffer()

        msg1 = Request(test_message_type, b"First").compile()
        msg_type2 = MessageType(
            code=test_message_type.code + 500, name=f"buf_multi_{test_message_type.code}"
        )
        msg2 = Request(msg_type2, b"Second").compile()

        corrupt1 = bytearray(msg1)
        corrupt1[-1] ^= 0xFF

        corrupt2 = bytearray(msg2)
        corrupt2[-3] ^= 0xFF

        msg3_type = MessageType(
            code=test_message_type.code + 501, name=f"buf_multi2_{test_message_type.code}"
        )
        msg3 = Request(msg3_type, b"Third").compile()

        buf.add_data(bytes(corrupt1) + bytes(corrupt2) + msg3)
        messages = buf.extract_messages()

        assert len(messages) == 1
        assert messages[0].content == b"Third"

    # ── Buffer protection ─────────────────────────────────────────────────────

    def test_buffer_overflow_protection(self, test_message_type):
        """Adding data beyond MAX_BUFFER_SIZE should clear buffer."""
        buf = MessageBuffer(max_message_size=100, max_buffer_size=100)

        request = Request(test_message_type, b"Hello")
        compiled = request.compile()

        buf.add_data(compiled)
        assert len(buf) == len(compiled)

        buf.add_data(b"X" * 200)
        assert len(buf) == 0

    def test_buffer_overflow_edge(self, test_message_type):
        """Data exactly at limit should be accepted."""
        buf = MessageBuffer(max_message_size=100, max_buffer_size=100)

        request = Request(test_message_type, b"A" * 30)
        compiled = request.compile()
        padding = 100 - len(compiled)

        buf.add_data(compiled + b"B" * padding)
        assert len(buf) == 100

    def test_continuous_garbage_stream(self, test_message_type):
        """Continuous garbage should not cause unbounded growth."""
        buf = MessageBuffer()

        for _ in range(10):
            buf.add_data(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09" * 1000)
            messages = buf.extract_messages()
            assert len(messages) == 0
            assert len(buf) == 0

    # ── Large and edge-case messages ──────────────────────────────────────────

    def test_large_message(self, test_message_type):
        """A message near the size limit should be handled."""
        buf = MessageBuffer(max_message_size=100 * 1024)
        content = b"X" * (80 * 1024)
        request = Request(test_message_type, content)
        compiled = request.compile()

        buf.add_data(compiled)
        messages = buf.extract_messages()

        assert len(messages) == 1
        assert messages[0].content == content

    def test_empty_content_message(self, test_message_type):
        """Messages with empty content should be parseable."""
        buf = MessageBuffer()

        request = Request(test_message_type, b"")
        compiled = request.compile()

        buf.add_data(compiled)
        messages = buf.extract_messages()

        assert len(messages) == 1
        assert messages[0].content == b""
