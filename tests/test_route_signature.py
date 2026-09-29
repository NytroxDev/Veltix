"""Tests for route handler signature validation."""

import pytest

from veltix.handler.request_handler import RequestHandler
from veltix.internal.bus import VeltixBus
from veltix.internal.mode import Mode
from veltix.network.types import MessageType

MSG = MessageType(code=9800, name="signature_test")


def make_handler(mode: Mode) -> RequestHandler:
    return RequestHandler(mode=mode, bus=VeltixBus())


class TestRouteSignatureValidation:
    def test_server_route_with_one_arg_raises_guiding_error(self):
        handler = make_handler(Mode.SERVER)
        with pytest.raises(TypeError, match=r"client, response"):
            handler.register_route(MSG, lambda response: None)

    def test_server_route_with_three_args_raises_guiding_error(self):
        handler = make_handler(Mode.SERVER)
        with pytest.raises(TypeError, match="client, response"):
            handler.register_route(MSG, lambda a, b, c: None)

    def test_client_route_with_two_args_raises_guiding_error(self):
        handler = make_handler(Mode.CLIENT)
        with pytest.raises(TypeError, match=r"\bresponse\b"):
            handler.register_route(MSG, lambda client, response: None)

    def test_client_route_with_zero_args_raises_guiding_error(self):
        handler = make_handler(Mode.CLIENT)
        with pytest.raises(TypeError, match=r"\bresponse\b"):
            handler.register_route(MSG, lambda: None)

    def test_server_route_valid_signature_ok(self):
        handler = make_handler(Mode.SERVER)
        assert handler.register_route(MSG, lambda client, response: None) is True

    def test_client_route_valid_signature_ok(self):
        handler = make_handler(Mode.CLIENT)
        assert handler.register_route(MSG, lambda response: None) is True

    def test_handler_with_varargs_passes(self):
        handler = make_handler(Mode.SERVER)
        assert handler.register_route(MSG, lambda *args: None) is True

    def test_handler_with_optional_args_passes(self):
        handler = make_handler(Mode.SERVER)
        assert handler.register_route(MSG, lambda client, response=None: None) is True

    def test_error_message_guides_toward_fix(self):
        handler = make_handler(Mode.SERVER)

        def on_msg(response):  # type: ignore[no-untyped-def]
            pass

        with pytest.raises(TypeError) as exc:
            handler.register_route(MSG, on_msg)
        text = str(exc.value)
        assert "on_msg" in text
        assert "client, response" in text
        assert "def on_msg(client: ClientInfo, response: Response) -> None" in text
