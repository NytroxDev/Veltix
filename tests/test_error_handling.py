"""Tests for error handling and exceptions."""

from veltix import (
    Client,
    ClientConfig,
    MessageTypeError,
    RequestError,
    SenderError,
    VeltixError,
)


class TestErrorHandling:
    def test_veltix_error_hierarchy(self):
        assert issubclass(MessageTypeError, VeltixError)
        assert issubclass(RequestError, VeltixError)
        assert issubclass(SenderError, VeltixError)

    def test_connection_refused(self):
        client = Client(ClientConfig(server_addr="127.0.0.1", port=11111))
        result = client.connect()
        assert not result
        assert not client.is_connected
