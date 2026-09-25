"""Tests for the runtime Rust engine switch (``enable_rust``/``disable_rust``).

The engine can be toggled in code after import. Each (re)initialization of
network components captures the engine it is built with: ``Server``/``Client``
construction, ``Server.restart()`` (via ``_init_components``), and ``Client``
reconnection (via ``init_components``). Components created earlier keep the
engine they were built with for their whole lifetime.
"""

from __future__ import annotations

import pytest

from veltix import Client, ClientConfig, Request, Server, ServerConfig
from veltix.network import _rust
from veltix.network.message_buffer import MessageBuffer
from veltix.network.sender import Mode, Sender
from veltix.network.types import MessageType

RUST_AVAILABLE = _rust._EXTENSION_LOADED
# Whether the compiled engine is actually usable in this process (the
# VELTIX_DISABLE_RUST env var is a hard process-wide off that the runtime
# enable_rust() cannot override).
ROOT_ENABLED = _rust.rust_enabled()


@pytest.fixture
def rust_switch() -> None:
    """Reset the runtime switch to the default after each test."""
    yield
    _rust.enable_rust()


def test_public_exports() -> None:
    import veltix

    assert callable(veltix.disable_rust)
    assert callable(veltix.enable_rust)
    assert "enable_rust" in veltix.__all__
    assert "disable_rust" in veltix.__all__


def test_enable_disable_toggle(rust_switch) -> None:
    _rust.disable_rust()
    assert not _rust.rust_enabled()
    assert _rust.engine_name() == "python"
    _rust.enable_rust()
    assert _rust.rust_enabled() == ROOT_ENABLED
    assert _rust.engine_name() == ("rust" if ROOT_ENABLED else "python")


def test_message_buffer_pins_engine_at_construction(rust_switch) -> None:
    _rust.disable_rust()
    buf = MessageBuffer()
    assert buf._use_rust is False

    _rust.enable_rust()
    # the already-initialized buffer keeps the engine it was built with
    assert buf._use_rust is False

    buf2 = MessageBuffer()
    assert buf2._use_rust == ROOT_ENABLED


@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust extension not installed")
def test_message_buffer_explicit_engine(rust_switch) -> None:
    assert MessageBuffer(use_rust=True)._use_rust is True
    assert MessageBuffer(use_rust=False)._use_rust is False


@pytest.mark.skipif(not RUST_AVAILABLE, reason="Rust extension not installed")
def test_request_compile_explicit_engine(rust_switch) -> None:
    req = Request(MessageType("compile_pin"), b"hello world")
    rust_bytes = req.compile(use_rust=True)
    python_bytes = req.compile(use_rust=False)
    assert rust_bytes == python_bytes
    assert len(rust_bytes) > len(b"hello world")


def test_sender_pins_compile_engine(rust_switch) -> None:
    _rust.disable_rust()
    sender_py = Sender(mode=Mode.SERVER)
    assert sender_py._use_rust is False

    _rust.enable_rust()
    sender_rust = Sender(mode=Mode.SERVER)
    assert sender_rust._use_rust == ROOT_ENABLED


def test_server_pins_engine_at_init(rust_switch) -> None:
    _rust.disable_rust()
    server = Server(ServerConfig(host="127.0.0.1", port=0))
    try:
        assert server._sender._use_rust is False
        assert server.socket._use_rust is False
    finally:
        server.close_all()


@pytest.mark.skipif(not ROOT_ENABLED, reason="Rust engine disabled in this process")
def test_server_reinit_repins_engine(rust_switch) -> None:
    """Server.restart() re-initializes components, so it re-pins the engine."""
    _rust.disable_rust()
    server = Server(ServerConfig(host="127.0.0.1", port=0))
    try:
        assert server._sender._use_rust is False

        _rust.enable_rust()
        old_socket = server.socket
        server._init_components()  # the exact re-init path used by restart()
        old_socket.close()

        assert server._sender._use_rust is True
        assert server.socket._use_rust is True
    finally:
        server.close_all()


def test_client_pins_engine_at_init(rust_switch) -> None:
    _rust.disable_rust()
    client = Client(ClientConfig(server_addr="127.0.0.1", port=0))
    try:
        assert client._sender._use_rust is False
        assert client.socket._use_rust is False
    finally:
        client.socket.close()


@pytest.mark.skipif(not ROOT_ENABLED, reason="Rust engine disabled in this process")
def test_client_reinit_repins_engine(rust_switch) -> None:
    """Client reconnection re-initializes components, so it re-pins."""
    _rust.disable_rust()
    client = Client(ClientConfig(server_addr="127.0.0.1", port=0))
    try:
        assert client._sender._use_rust is False

        _rust.enable_rust()
        client.init_components()  # called on reconnection

        assert client._sender._use_rust is True
        assert client.socket._use_rust is True
    finally:
        client.socket.close()
