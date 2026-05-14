"""Handshake handler for Veltix protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..internal.compatibility import Version
from ..internal.mode import Mode
from ..logger.core import Logger
from ..network.request import Request, Response
from ..network.system_types import HELLO, HELLO_ACK
from ..version import __version__

if TYPE_CHECKING:
    from ..network.sender import Sender


class HandshakeHandler:
    """
    Handles the HELLO / HELLO_ACK exchange for a single connection.

    SERVER: prepare_hello() → send_hello() → handle_hello_ack()
    CLIENT: handle_hello() → send_hello_ack()
    """

    def __init__(self, sender: Sender, mode: Mode) -> None:
        self.sender = sender
        self.mode = mode
        self.is_server = mode == Mode.SERVER
        self._logger = Logger.get_instance()
        self.version = Version.from_str(__version__)
        self._logger.debug(
            f"[Handshake] {self.mode.name.lower()} handshake handler initialized (version={__version__})"
        )

    # ── Encode / decode ───────────────────────────────────────────────────────

    @staticmethod
    def _encode_hello() -> bytes:
        version_bytes = __version__.encode("utf-8")
        return len(version_bytes).to_bytes(2, "big") + version_bytes

    @staticmethod
    def _decode_hello(payload: bytes) -> Version:
        length = int.from_bytes(payload[0:2], "big")
        return Version.from_str(payload[2 : 2 + length].decode("utf-8"))

    # ── Server ────────────────────────────────────────────────────────────────

    def prepare_hello(self) -> tuple[bytes, Request]:
        """
        Prepare a HELLO request without sending it.

        Must be called BEFORE register() and send_hello() to avoid the race
        condition where HELLO_ACK arrives before the queue is registered.
        """
        hello = Request(HELLO, self._encode_hello())
        self._logger.debug(f"[Handshake] HELLO prepared (id={hello.request_id[:8]}...)")
        return hello.request_id, hello

    def send_hello(self, hello: Request, client_conn=None) -> None:
        """Send a previously prepared HELLO. Must be called AFTER register()."""
        if self.is_server:
            self.sender.send(hello, client=client_conn)
        else:
            self.sender.send(hello)
        self._logger.debug(f"[Handshake] HELLO sent (id={hello.request_id[:8]}...)")

    def handle_hello_ack(self, response: Response) -> bool:
        """Validate an incoming HELLO_ACK from the client."""
        if response.type != HELLO_ACK:
            self._logger.warning(f"[Handshake] Expected HELLO_ACK, got '{response.type.name}'")
            return False

        client_version = self._decode_hello(response.content)
        if not self.version.is_compatible(client_version):
            self._logger.warning(
                f"[Handshake] Version mismatch — server={self.version}, client={client_version}"
            )
            return False

        self._logger.debug(f"[Handshake] HELLO_ACK accepted — client={client_version}")
        return True

    # ── Client ────────────────────────────────────────────────────────────────

    def handle_hello(self, response: Response) -> bool:
        """Validate an incoming HELLO from the server."""
        if response.type != HELLO:
            self._logger.warning(f"[Handshake] Expected HELLO, got '{response.type.name}'")
            return False

        server_version = self._decode_hello(response.content)
        if not self.version.is_compatible(server_version):
            self._logger.warning(
                f"[Handshake] Version mismatch — server={server_version}, client={self.version}"
            )
            return False

        self._logger.debug(f"[Handshake] HELLO accepted — server={server_version}")
        return True

    def send_hello_ack(self, request_id: bytes) -> None:
        """Send HELLO_ACK back to the server."""
        ack = Request(HELLO_ACK, self._encode_hello(), request_id=request_id)
        self.sender.send(ack)
        self._logger.debug(f"[Handshake] HELLO_ACK sent (id={request_id[:8]}...)")
