"""Tests for callback signature validation (on_recv, on_connect, on_disconnect)."""

import pytest

from veltix.client.client import Client
from veltix.client.config import ClientConfig
from veltix.handler.request_handler import RequestHandler
from veltix.internal.bus import VeltixBus
from veltix.internal.mode import Mode
from veltix.server.config import ServerConfig
from veltix.server.server import Server


def make_handler(mode: Mode) -> RequestHandler:
    return RequestHandler(mode=mode, bus=VeltixBus())


class TestOnRecvSignature:
    def test_server_on_recv_with_one_arg_raises(self):
        handler = make_handler(Mode.SERVER)
        with pytest.raises(TypeError, match=r"client, response"):
            handler.set_on_recv(lambda response: None)

    def test_client_on_recv_with_two_args_raises(self):
        handler = make_handler(Mode.CLIENT)
        with pytest.raises(TypeError, match=r"\bresponse\b"):
            handler.set_on_recv(lambda client, response: None)

    def test_server_on_recv_valid_signature_ok(self):
        handler = make_handler(Mode.SERVER)
        handler.set_on_recv(lambda client, response: None)  # must not raise

    def test_client_on_recv_valid_signature_ok(self):
        handler = make_handler(Mode.CLIENT)
        handler.set_on_recv(lambda response: None)  # must not raise


class TestOnConnectSignature:
    def test_server_on_connect_with_zero_args_raises(self):
        srv = Server(ServerConfig(host="127.0.0.1", port=59001))
        with pytest.raises(TypeError, match=r"with \(client\)"):
            srv.on_connect(lambda: None)

    def test_server_on_connect_with_two_args_raises(self):
        srv = Server(ServerConfig(host="127.0.0.1", port=59002))
        with pytest.raises(TypeError, match=r"with \(client\)"):
            srv.on_connect(lambda client, response: None)

    def test_server_on_connect_valid_signature_ok(self):
        srv = Server(ServerConfig(host="127.0.0.1", port=59003))
        srv.on_connect(lambda client: None)  # must not raise

    def test_client_on_connect_with_one_arg_raises(self):
        cli = Client(ClientConfig(server_addr="127.0.0.1", port=59004))
        with pytest.raises(TypeError, match=r"accepts 1 positional"):
            cli.on_connect(lambda client: None)

    def test_client_on_connect_valid_signature_ok(self):
        cli = Client(ClientConfig(server_addr="127.0.0.1", port=59005))
        cli.on_connect(lambda: None)  # must not raise


class TestOnDisconnectSignature:
    def test_server_on_disconnect_with_zero_args_raises(self):
        srv = Server(ServerConfig(host="127.0.0.1", port=59006))
        with pytest.raises(TypeError, match=r"with \(client\)"):
            srv.on_disconnect(lambda: None)

    def test_server_on_disconnect_valid_signature_ok(self):
        srv = Server(ServerConfig(host="127.0.0.1", port=59007))
        srv.on_disconnect(lambda client: None)  # must not raise

    def test_client_on_disconnect_with_zero_args_raises(self):
        cli = Client(ClientConfig(server_addr="127.0.0.1", port=59008))
        with pytest.raises(TypeError, match=r"with \(state\)"):
            cli.on_disconnect(lambda: None)

    def test_client_on_disconnect_valid_signature_ok(self):
        cli = Client(ClientConfig(server_addr="127.0.0.1", port=59009))
        cli.on_disconnect(lambda state: None)  # must not raise


class TestCallbackErrorGuidesTowardFix:
    def test_message_shows_fix_signature(self):
        def my_cb(response):  # type: ignore[no-untyped-def]
            pass

        handler = make_handler(Mode.SERVER)
        with pytest.raises(TypeError) as exc:
            handler.set_on_recv(my_cb)

        text = str(exc.value)
        assert "my_cb" in text
        assert "Fix: def my_cb(client: ClientInfo, response: Response) -> None." in text
