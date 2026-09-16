"""Unit tests for configuration validation."""

from __future__ import annotations

import pytest

from veltix import ServerConfig


class TestServerConfigIDWindow:
    def test_default_id_window_accepted(self) -> None:
        assert ServerConfig().id_window == 30000

    def test_uint16_max_accepted(self) -> None:
        assert ServerConfig(id_window=65535).id_window == 65535

    def test_zero_rejected(self) -> None:
        with pytest.raises(ValueError):
            ServerConfig(id_window=0)

    def test_above_uint16_max_rejected(self) -> None:
        with pytest.raises(ValueError):
            ServerConfig(id_window=65536)

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValueError):
            ServerConfig(id_window=-1)
