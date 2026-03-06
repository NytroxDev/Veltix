"""Handshake handler for Veltix protocol."""

from typing import Optional

from ..logger.core import Logger
from ..network.request import Request, Response
from ..network.sender import Sender
from ..network.system_types import HELLO, HELLO_ACK
from ..utils.mode import Mode
from ..version import __version__


class HandshakeHandler:
    """
    Handles the HELLO / HELLO_ACK exchange for a single connection.

    SERVER side:
        1. prepare_hello()    — creates HELLO request (call before register()!)
        2. send_hello()       — sends the prepared HELLO
        3. handle_hello_ack() — validates the HELLO_ACK

    CLIENT side:
        1. handle_hello()     — receives and validates the HELLO
        2. send_hello_ack()   — sends HELLO_ACK back to the server
    """

    def __init__(self, sender: Sender, mode: Mode) -> None:
        """
        Initialize the handshake handler.

        Args:
            sender: Sender instance for outgoing messages
            mode:   Mode.SERVER or Mode.CLIENT
        """
        self.sender = sender
        self.mode = mode
        self.is_server = mode == Mode.SERVER
        self._logger = Logger.get_instance()

        self._logger.debug(f"HandshakeHandler initialized in {mode.value} mode")

    # ------------------------------------------------------------------ encode/decode

    @staticmethod
    def _encode_hello() -> bytes:
        version_bytes = __version__.encode("utf-8")
        length_bytes = len(version_bytes).to_bytes(2, "big")
        return length_bytes + version_bytes

    @staticmethod
    def _decode_hello(payload: bytes) -> str:
        length = int.from_bytes(payload[0:2], "big")
        return payload[2 : 2 + length].decode("utf-8")

    def split_version(self, version: str) -> Optional[tuple[int, int, int]]:
        try:
            major, minor, patch = map(int, version.split("."))
            return major, minor, patch
        except Exception as err:
            self._logger.error(f"Version decoding error: {err}")
            return None

    def _check_version(self, server_version: str, client_version: str) -> bool:
        """
        Check version compatibility between server and client.
        Only major.minor must match, patch is ignored.

        Args:
            server_version: Server version string (e.g. "1.4.0")
            client_version: Client version string (e.g. "1.4.5")

        Returns:
            True if compatible, False otherwise
        """
        server_version_split = self.split_version(server_version)
        client_version_split = self.split_version(client_version)

        if server_version_split is None or client_version_split is None:
            return False

        return server_version_split[:2] == client_version_split[:2]

    # ------------------------------------------------------------------ SERVER

    def prepare_hello(self) -> tuple[str, Request]:
        """
        SERVER: Prepare a HELLO request without sending it.

        Must be called BEFORE register() and send_hello() to avoid the race
        condition where HELLO_ACK arrives before the queue is registered.

        Returns:
            (request_id, hello_request) — register request_id, then call send_hello()
        """
        hello = Request(HELLO, self._encode_hello())
        self._logger.debug(f"[Handshake] HELLO prepared (request_id={hello.request_id[:8]}...)")
        return hello.request_id, hello

    def send_hello(self, hello: Request, client_conn=None) -> None:
        """
        SERVER: Send a previously prepared HELLO request.

        Must be called AFTER register() to avoid race conditions.

        Args:
            hello:       The Request object returned by prepare_hello()
            client_conn: Raw socket of the target client (server mode only)
        """
        if self.is_server:
            self.sender.send(hello, client=client_conn)
        else:
            self.sender.send(hello)

        self._logger.debug(f"[Handshake] HELLO sent (request_id={hello.request_id[:8]}...)")

    def handle_hello_ack(self, response: Response) -> bool:
        """
        SERVER: Validate an incoming HELLO_ACK from the client.

        Args:
            response: Incoming HELLO_ACK Response object

        Returns:
            True if handshake accepted, False otherwise
        """
        if response.type != HELLO_ACK:
            self._logger.warning(f"[Handshake] Expected HELLO_ACK, got '{response.type.name}'")
            return False

        client_version = self._decode_hello(response.content)

        if not self._check_version(__version__, client_version):
            self._logger.warning(
                f"[Handshake] Version mismatch — server={__version__}, client={client_version}"
            )
            return False

        self._logger.debug(f"[Handshake] HELLO_ACK accepted — client version={client_version}")
        return True

    # ------------------------------------------------------------------ CLIENT

    def handle_hello(self, response: Response) -> bool:
        """
        CLIENT: Validate an incoming HELLO from the server.

        Args:
            response: Incoming HELLO Response object

        Returns:
            True if HELLO is valid, False otherwise
        """
        if response.type != HELLO:
            self._logger.warning(f"[Handshake] Expected HELLO, got '{response.type.name}'")
            return False

        server_version = self._decode_hello(response.content)

        if not self._check_version(server_version, __version__):
            self._logger.warning(
                f"[Handshake] Version mismatch — server={server_version}, client={__version__}"
            )
            return False

        self._logger.debug(f"[Handshake] HELLO accepted — server version={server_version}")
        return True

    def send_hello_ack(self, request_id: str) -> None:
        """
        CLIENT: Send HELLO_ACK back to the server.

        Args:
            request_id: The request_id from the received HELLO — used for correlation
        """
        ack = Request(HELLO_ACK, self._encode_hello(), request_id=request_id)
        self.sender.send(ack)

        self._logger.debug(f"[Handshake] HELLO_ACK sent (request_id={request_id[:8]}...)")
