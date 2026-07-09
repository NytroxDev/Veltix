"""Handshake handler for Veltix protocol."""

from __future__ import annotations

import json
import struct
from typing import TYPE_CHECKING, Any, Optional, Protocol, cast

from ..internal.compatibility import Version
from ..internal.mode import Mode
from ..version import __version__

if TYPE_CHECKING:
    from ..internal.bus import VeltixBus

_HANDSHAKE_STRUCT = struct.Struct(">H")


class RawSocket(Protocol):
    """Minimal raw TCP socket interface for handshake I/O."""

    def settimeout(self, timeout: Optional[float]) -> None: ...
    def sendall(self, data: bytes) -> None: ...
    def recv(self, bufsize: int) -> bytes: ...


class HandshakeHandler:
    """
    Manage the version compatibility handshake for a single raw TCP connection.
    Uses a 3-way protocol to ensure both sides are synchronized:

      1. Server → Client : {"v", "meta"}
      2. Client → Server : {"v", "meta"}
      3. Server → Client : {"result": "ok"}

    Server mode sends first, then validates client version before acking.
    Client mode reads server version, validates, sends its version, then
    waits for the server ack before returning.
    """

    def __init__(self, mode: Mode, bus: VeltixBus) -> None:
        self.mode = mode
        self.is_server = mode == Mode.SERVER
        self.bus = bus
        self.version = Version.from_str(__version__)
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
    def _decode(data: bytes) -> Optional[dict[str, Any]]:
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

    def _recv_handshake(self, sock: RawSocket, timeout: float = 5.0) -> Optional[dict[str, Any]]:
        """Receive a handshake JSON payload from a raw TCP socket."""

        def _recv_all(sock: RawSocket, n: int) -> Optional[bytes]:
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

    def _check_version(self, peer_version: str) -> bool:
        """Check peer version against the compatibility table."""
        try:
            peer = Version.from_str(peer_version)
            result = self.version.is_compatible(peer)
            return bool(result)
        except Exception:
            self.bus.error(f"Invalid peer version string: {peer_version!r}")
            return False

    def do_server_handshake(self, sock: RawSocket, timeout: float = 5.0) -> bool:
        """Server-side handshake: send server info, validate client response."""
        self.bus.debug("Server handshake start")

        if not self._send_handshake(sock, {"v": __version__, "meta": {}}):
            self.bus.error("Failed to send server handshake")
            return False

        client_payload = self._recv_handshake(sock, timeout=timeout)
        if not client_payload:
            self.bus.error("Failed to receive client handshake response")
            return False

        peer_version = client_payload.get("v", "")
        if not self._check_version(peer_version):
            self.bus.error(f"Client version {peer_version} is incompatible")
            return False

        if not self._send_handshake(sock, {"result": "ok"}):
            self.bus.error("Failed to send handshake acknowledgment")
            return False

        self.bus.debug("Server handshake complete")
        return True

    def do_client_handshake(self, sock: RawSocket) -> tuple[bool, Optional[dict[str, Any]]]:
        """Client-side handshake: read server info, send client response."""
        self.bus.debug("Client handshake start")

        server_payload = self._recv_handshake(sock)
        if not server_payload:
            self.bus.error("Failed to receive server handshake")
            return False, None

        peer_version = server_payload.get("v", "")
        if not self._check_version(peer_version):
            self.bus.error(f"Server version {peer_version} is incompatible")
            return False, None

        if not self._send_handshake(sock, {"v": __version__, "meta": {}}):
            self.bus.error("Failed to send client handshake response")
            return False, None

        ack = self._recv_handshake(sock)
        if not ack or ack.get("result") != "ok":
            self.bus.error("Failed to receive server handshake acknowledgment")
            return False, None

        meta = server_payload.get("meta", {})
        self.bus.debug("Client handshake complete")
        return True, meta
