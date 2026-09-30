"""Unit tests for configuration validation."""

from __future__ import annotations

import pytest

from veltix import ClientConfig, ServerConfig


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


class TestServerConfigValidation:
    def test_port_zero_ephemeral_accepted(self) -> None:
        assert ServerConfig(port=0).port == 0

    def test_port_negative_rejected(self) -> None:
        with pytest.raises(ValueError):
            ServerConfig(port=-1)

    def test_port_above_uint16_max_rejected(self) -> None:
        with pytest.raises(ValueError):
            ServerConfig(port=65536)

    def test_buffer_size_zero_rejected(self) -> None:
        with pytest.raises(ValueError):
            ServerConfig(buffer_size=0)

    def test_max_connection_unlimited_accepted(self) -> None:
        assert ServerConfig(max_connection=-1).max_connection == -1

    def test_max_connection_zero_rejected(self) -> None:
        with pytest.raises(ValueError):
            ServerConfig(max_connection=0)

    def test_max_connection_below_minus_one_rejected(self) -> None:
        with pytest.raises(ValueError):
            ServerConfig(max_connection=-2)

    def test_max_message_size_zero_rejected(self) -> None:
        with pytest.raises(ValueError):
            ServerConfig(max_message_size=0)

    def test_handshake_timeout_zero_rejected(self) -> None:
        with pytest.raises(ValueError):
            ServerConfig(handshake_timeout=0)

    def test_max_workers_zero_rejected(self) -> None:
        with pytest.raises(ValueError):
            ServerConfig(max_workers=0)


class TestConfigGuidingErrors:
    def test_server_port_string_guides(self) -> None:
        with pytest.raises(TypeError, match="must be an int"):
            ServerConfig(port="8080")

    def test_server_socket_core_string_guides(self) -> None:
        with pytest.raises(TypeError, match="SocketCore"):
            ServerConfig(socket_core="ASYNC")

    def test_server_handshake_timeout_string_guides(self) -> None:
        with pytest.raises(TypeError, match="handshake_timeout"):
            ServerConfig(handshake_timeout="5.0")

    def test_client_addr_wrong_type_guides(self) -> None:
        with pytest.raises(TypeError, match="server_addr"):
            ClientConfig(server_addr=8080)

    def test_client_retry_string_guides(self) -> None:
        with pytest.raises(TypeError, match="retry"):
            ClientConfig(retry="3")

    def test_config_errors_show_fix_and_value(self) -> None:
        with pytest.raises(TypeError) as exc:
            ServerConfig(port="8080")

        text = str(exc.value)
        assert "got str" in text
        assert "Fix:" in text


class TestClientConfigValidation:
    def test_defaults_valid(self) -> None:
        assert ClientConfig().port == 8080
        assert ClientConfig().retry == 0
        assert ClientConfig().retry_delay == 1.0

    def test_port_zero_ephemeral_accepted(self) -> None:
        assert ClientConfig(port=0).port == 0

    def test_port_negative_rejected(self) -> None:
        with pytest.raises(ValueError):
            ClientConfig(port=-1)

    def test_port_above_uint16_max_rejected(self) -> None:
        with pytest.raises(ValueError):
            ClientConfig(port=65536)

    def test_buffer_size_zero_rejected(self) -> None:
        with pytest.raises(ValueError):
            ClientConfig(buffer_size=0)

    def test_max_message_size_zero_rejected(self) -> None:
        with pytest.raises(ValueError):
            ClientConfig(max_message_size=0)

    def test_handshake_timeout_zero_rejected(self) -> None:
        with pytest.raises(ValueError):
            ClientConfig(handshake_timeout=0)

    def test_max_workers_zero_rejected(self) -> None:
        with pytest.raises(ValueError):
            ClientConfig(max_workers=0)

    def test_retry_negative_rejected(self) -> None:
        with pytest.raises(ValueError):
            ClientConfig(retry=-1)

    def test_retry_delay_zero_rejected(self) -> None:
        with pytest.raises(ValueError):
            ClientConfig(retry_delay=0)
