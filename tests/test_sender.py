"""Tests for Sender class."""

import pytest

from veltix import Mode, Sender, SenderError


class TestSender:
    def test_sender_client_mode_requires_socket(self):
        with pytest.raises(SenderError):
            Sender(mode=Mode.CLIENT, conn=None)

    def test_sender_server_mode(self):
        sender = Sender(mode=Mode.SERVER)
        assert sender.mode == Mode.SERVER
        assert not sender.is_client
