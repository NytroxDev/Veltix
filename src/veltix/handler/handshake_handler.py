"""Handshake handler for Veltix protocol."""

from __future__ import annotations

import json
import struct
from typing import TYPE_CHECKING, Any, Protocol, cast

from ..exceptions import ServerFullError
from ..internal.compatibility import protocol_is_compatible, protocol_version_str
from ..internal.events import ProtocolEvent
from ..internal.mode import Mode
from ..internal.version import __version__

if TYPE_CHECKING:
    from ..internal.bus import VeltixBus

_HANDSHAKE_STRUCT = struct.Struct(">H")


class RawSocket(Protocol):
    """Minimal raw TCP socket interface for handshake I/O."""

    def settimeout(self, timeout: float | None) -> None: ...
    def sendall(self, data: bytes) -> None: ...
    def recv(self, bufsize: int) -> bytes: ...


class HandshakeHandler:
    """
    Manage the version compatibility handshake for a single raw TCP connection.
    Uses a 3-way protocol to ensure both sides are synchronized:

      1. Server → Client : {"v", "pv", "meta"}
      2. Client → Server : {"v", "pv", "meta"}
      3. Server → Client : {"result": "ok"}

    Server mode sends first, then validates client protocol version before acking.
    Client mode reads server protocol version, validates, sends its version, then
    waits for the server ack before returning.
    """

    def __init__(self, mode: Mode, bus: VeltixBus) -> None:
        """Initialise the handshake handler for a given role.

        Args:
            mode: Whether this handler operates as ``SERVER`` or ``CLIENT``.
            bus: Event bus for emitting handshake events and logging.
        """
        self.mode = mode
        self.is_server = mode == Mode.SERVER
        self.bus = bus
        self.bus.debug(
            f"[Handshake] {self.mode.name.lower()} handshake handler initialized (version={__version__})"
        )

    # ── Encode / decode ───────────────────────────────────────────────────────

    @staticmethod
    def _encode(payload: dict[str, Any]) -> bytes:
        """Length-prefixed JSON encoding."""
        payload_encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        data = _HANDSHAKE_STRUCT.pack(len(payload_encoded)) + payload_encoded
        return data

    @staticmethod
    def _decode(data: bytes) -> dict[str, Any] | None:
        """Parse length-prefixed JSON."""
        payload_len = _HANDSHAKE_STRUCT.unpack(data[:2])[0]
        return cast("dict[str, Any]", json.loads(data[2 : 2 + payload_len]))

    def _send_handshake(self, sock: RawSocket, payload: dict[str, Any]) -> bool:
        """Send a handshake JSON payload over a raw TCP socket."""
        try:
            data = self._encode(payload)
            sock.sendall(data)
            return True
        except Exception as e:
            self.bus.error(f"Handshake send failed: {e}")
            return False

    def _recv_handshake(self, sock: RawSocket, timeout: float = 5.0) -> dict[str, Any] | None:
        """Receive a handshake JSON payload from a raw TCP socket."""

        def _recv_all(sock: RawSocket, n: int) -> bytes | None:
            chunks = []
            remaining = n
            while remaining > 0:
                chunk = sock.recv(remaining)
                if not chunk:
                    return None
                chunks.append(chunk)
                remaining -= len(chunk)
            return b"".join(chunks)

        try:
            sock.settimeout(timeout)
            header = _recv_all(sock, 2)
            if not header or len(header) < 2:
                return None
            payload_len = _HANDSHAKE_STRUCT.unpack(header)[0]
            data = _recv_all(sock, payload_len)
            if not data or len(data) < payload_len:
                return None
            return self._decode(header + data)
        except Exception as e:
            self.bus.error(f"Handshake recv failed: {e}")
            return None

    def send_rejection(self, sock: RawSocket, reason: str) -> bool:
        """Send a rejection payload and close the connection.

        Used by the server to explicitly reject a client before the
        handshake (e.g. when the server is full).

        Args:
            sock: A raw TCP socket conforming to :class:`RawSocket`.
            reason: Rejection reason string (e.g. ``"server_full"``).

        Returns:
            True if the rejection was sent, False on error.
        """
        return self._send_handshake(sock, {"error": reason})

    def recv_rejection(self, sock: RawSocket, timeout: float = 5.0) -> str | None:
        """Try to read a rejection message from the server.

        If the server is full, it sends ``{"error": "server_full"}``
        before the handshake starts. This method reads that payload and
        returns the error string, or ``None`` if no rejection was received.

        Args:
            sock: A raw TCP socket conforming to :class:`RawSocket`.
            timeout: Maximum seconds to wait for the payload.

        Returns:
            The error string (e.g. ``"server_full"``) or ``None``.
        """
        payload = self._recv_handshake(sock, timeout=timeout)
        if payload and "error" in payload:
            return str(payload["error"])
        return None

    def _check_version(self, peer_pv: str) -> bool:
        """Check peer compatibility against the local protocol version.

        Two peers are compatible when they share the same protocol major.
        A peer without a protocol version (``pv``) is rejected.

        Args:
            peer_pv: The peer protocol version string (``MAJOR.MINOR``).

        Returns:
            True if the peer is compatible, False otherwise.
        """
        if not peer_pv:
            self.bus.error("Peer did not advertise a protocol version (pv)")
            return False
        return protocol_is_compatible(peer_pv)

    def do_server_handshake(self, sock: RawSocket, timeout: float = 5.0) -> bool:
        """Perform the server-side 3-way handshake.

        Steps:
            1. Send ``{"v": ..., "pv": ..., "meta": {}}`` to the client.
            2. Receive the client's ``{"v": ..., "pv": ..., "meta": ...}`` response.
            3. Validate the client's protocol version.
            4. Send ``{"result": "ok"}`` to acknowledge.

        Args:
            sock: A raw TCP socket conforming to :class:`RawSocket`.
            timeout: Maximum seconds to wait for each recv.

        Returns:
            True if the handshake succeeded, False on any failure.
        """
        self.bus.emit(ProtocolEvent.HANDSHAKE_START, {"role": "server"})

        if not self._send_handshake(
            sock,
            {
                "v": __version__,
                "pv": protocol_version_str(),
                "meta": {},
            },
        ):
            self.bus.emit(
                ProtocolEvent.HANDSHAKE_FAIL,
                {"role": "server", "reason": "send_failed"},
            )
            self.bus.error("Failed to send server handshake")
            return False

        client_payload = self._recv_handshake(sock, timeout=timeout)
        if not client_payload:
            self.bus.emit(
                ProtocolEvent.HANDSHAKE_FAIL,
                {"role": "server", "reason": "recv_failed"},
            )
            self.bus.error("Failed to receive client handshake response")
            return False

        peer_version = client_payload.get("v", "")
        peer_pv = client_payload.get("pv", "")
        if not self._check_version(peer_pv):
            self.bus.emit(
                ProtocolEvent.HANDSHAKE_FAIL,
                {
                    "role": "server",
                    "reason": "version_mismatch",
                    "peer_version": peer_version,
                },
            )
            self.bus.error(f"Client version {peer_version} is incompatible")
            return False

        if not self._send_handshake(sock, {"result": "ok"}):
            self.bus.emit(ProtocolEvent.HANDSHAKE_FAIL, {"role": "server", "reason": "ack_failed"})
            self.bus.error("Failed to send handshake acknowledgment")
            return False

        self.bus.emit(
            ProtocolEvent.HANDSHAKE_DONE,
            {"role": "server", "peer_version": peer_version},
        )
        return True

    def do_client_handshake(
        self, sock: RawSocket, timeout: float = 5.0
    ) -> tuple[bool, dict[str, Any] | None]:
        """Perform the client-side 3-way handshake.

        Steps:
            1. Receive the server's ``{"v": ..., "pv": ..., "meta": ...}`` payload.
            2. Validate the server's protocol version.
            3. Send ``{"v": ..., "meta": {}}`` to the server.
            4. Wait for the server's ``{"result": "ok"}`` acknowledgment.

        Args:
            sock: A raw TCP socket conforming to :class:`RawSocket`.
            timeout: Maximum seconds to wait for each recv.

        Returns:
            A tuple of ``(success, meta)`` where *meta* is the server's
            metadata dict on success, or ``None`` on failure.
        """
        self.bus.emit(ProtocolEvent.HANDSHAKE_START, {"role": "client"})

        server_payload = self._recv_handshake(sock, timeout=timeout)
        if not server_payload:
            self.bus.emit(
                ProtocolEvent.HANDSHAKE_FAIL,
                {"role": "client", "reason": "recv_failed"},
            )
            self.bus.error("Failed to receive server handshake")
            return False, None

        if "error" in server_payload:
            reason = str(server_payload["error"])
            self.bus.emit(
                ProtocolEvent.HANDSHAKE_FAIL,
                {"role": "client", "reason": reason},
            )
            self.bus.error(f"Server rejected connection: {reason}")
            raise ServerFullError(reason)

        peer_version = server_payload.get("v", "")
        peer_pv = server_payload.get("pv", "")
        if not self._check_version(peer_pv):
            self.bus.emit(
                ProtocolEvent.HANDSHAKE_FAIL,
                {
                    "role": "client",
                    "reason": "version_mismatch",
                    "peer_version": peer_version,
                },
            )
            self.bus.error(f"Server version {peer_version} is incompatible")
            return False, None

        if not self._send_handshake(
            sock, {"v": __version__, "pv": protocol_version_str(), "meta": {}}
        ):
            self.bus.emit(
                ProtocolEvent.HANDSHAKE_FAIL,
                {"role": "client", "reason": "send_failed"},
            )
            self.bus.error("Failed to send client handshake response")
            return False, None

        ack = self._recv_handshake(sock, timeout=timeout)
        if not ack or ack.get("result") != "ok":
            self.bus.emit(ProtocolEvent.HANDSHAKE_FAIL, {"role": "client", "reason": "ack_failed"})
            self.bus.error("Failed to receive server handshake acknowledgment")
            return False, None

        meta = server_payload.get("meta", {})
        self.bus.emit(
            ProtocolEvent.HANDSHAKE_DONE,
            {"role": "client", "peer_version": peer_version},
        )
        return True, meta
