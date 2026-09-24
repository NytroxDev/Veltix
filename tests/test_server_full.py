"""Integration tests for server full rejection (ServerFullError)."""

from __future__ import annotations

import socket
import time
from typing import TYPE_CHECKING

import pytest

from veltix import (
    Client,
    ClientConfig,
    Server,
    ServerConfig,
    ServerFullError,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_condition(
    condition: Callable[[], bool], timeout: float = 5.0, interval: float = 0.02
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(interval)
    return condition()


@pytest.mark.usefixtures("socket_core_backend")
class TestServerFullProperty:
    def test_is_full_returns_false_when_not_full(self) -> None:
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port, max_connection=2))
        server.start()

        try:
            assert not server.is_full

            client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
            client.connect()
            assert not server.is_full

            client.disconnect()
        finally:
            server.close_all()

    def test_is_full_returns_true_at_limit(self) -> None:
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port, max_connection=1))
        server.start()

        try:
            client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
            client.connect()
            assert wait_for_condition(lambda: server.is_full)

            client.disconnect()
        finally:
            server.close_all()

    def test_is_full_returns_false_when_unlimited(self) -> None:
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port, max_connection=-1))
        server.start()

        try:
            assert not server.is_full

            client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
            client.connect()
            assert not server.is_full

            client.disconnect()
        finally:
            server.close_all()


@pytest.mark.usefixtures("socket_core_backend")
class TestServerFullRejection:
    def test_connect_raises_server_full_error(self) -> None:
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port, max_connection=1))
        server.start()

        try:
            c1 = Client(ClientConfig(server_addr="127.0.0.1", port=port))
            c1.connect()
            assert wait_for_condition(lambda: server.is_full)

            c2 = Client(ClientConfig(server_addr="127.0.0.1", port=port))
            with pytest.raises(ServerFullError):
                c2.connect()

            c1.disconnect()
        finally:
            server.close_all()

    def test_rejected_client_not_in_clients_list(self) -> None:
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port, max_connection=1))
        server.start()

        try:
            c1 = Client(ClientConfig(server_addr="127.0.0.1", port=port))
            c1.connect()
            assert wait_for_condition(lambda: server.is_full)

            c2 = Client(ClientConfig(server_addr="127.0.0.1", port=port))
            with pytest.raises(ServerFullError):
                c2.connect()

            assert len(server.clients) == 1

            c1.disconnect()
        finally:
            server.close_all()

    def test_normal_connect_works_when_not_full(self) -> None:
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port, max_connection=2))
        server.start()

        try:
            c1 = Client(ClientConfig(server_addr="127.0.0.1", port=port))
            assert c1.connect()
            assert not server.is_full

            c2 = Client(ClientConfig(server_addr="127.0.0.1", port=port))
            assert c2.connect()
            assert wait_for_condition(lambda: server.is_full)

            c1.disconnect()
            c2.disconnect()
        finally:
            server.close_all()

    def test_client_not_connected_after_server_full(self) -> None:
        port = find_free_port()
        server = Server(ServerConfig(host="127.0.0.1", port=port, max_connection=1))
        server.start()

        try:
            c1 = Client(ClientConfig(server_addr="127.0.0.1", port=port))
            c1.connect()
            assert wait_for_condition(lambda: server.is_full)

            c2 = Client(ClientConfig(server_addr="127.0.0.1", port=port))
            with pytest.raises(ServerFullError):
                c2.connect()

            assert not c2.is_connected

            c1.disconnect()
        finally:
            server.close_all()
