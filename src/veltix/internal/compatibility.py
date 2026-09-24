"""
compatibility.py
----------------
Protocol version compatibility for the Veltix wire format.

The handshake uses a dedicated protocol version (:data:`PROTOCOL_VERSION`)
that is decoupled from the package version. Two peers are wire-compatible if
and only if they share the same protocol *MAJOR* component. This is symmetric:
a newer peer and an older peer both accept each other as long as their
protocol majors match.
"""

from __future__ import annotations

from ..logger.core import Logger

_logger = Logger.get_instance()


# ---------------------------------------------------------------------------
# Protocol version
# ---------------------------------------------------------------------------
#   pv <MAJOR>.<MINOR>
#   Two peers are compatible when their MAJOR components are equal.
#   The MINOR is informational only (the peer is not rejected on a mismatch).
#   Bump the MAJOR when the wire format breaks compatibility (e.g. header
#   layout, framing, handshake contract).
# ---------------------------------------------------------------------------

PROTOCOL_VERSION: tuple[int, int] = (1, 0)


def protocol_version_str() -> str:
    """Return the current protocol version as a ``MAJOR.MINOR`` string.

    Returns:
        The protocol version string (e.g. ``"1.0"``).
    """
    major, minor = PROTOCOL_VERSION
    return f"{major}.{minor}"


def _parse_protocol_version(value: str) -> tuple[int, int] | None:
    """Parse a ``MAJOR.MINOR`` protocol version string.

    Args:
        value: The protocol version string to parse.

    Returns:
        A ``(major, minor)`` tuple, or ``None`` if the string is invalid.
    """
    try:
        parts = value.split(".")
        if len(parts) != 2:
            return None
        major, minor = int(parts[0]), int(parts[1])
        return major, minor
    except (ValueError, AttributeError):
        return None


def protocol_is_compatible(peer_pv: str, local_pv: tuple[int, int] | None = None) -> bool:
    """Check whether a peer protocol version is compatible with the local one.

    Compatibility is determined by the MAJOR component: peers with the same
    major are compatible regardless of their minor.

    Args:
        peer_pv: The peer's protocol version string (``MAJOR.MINOR``).
        local_pv: The local protocol version as a ``(major, minor)`` tuple.
            Defaults to :data:`PROTOCOL_VERSION`.

    Returns:
        True if the majors match, False if the peer version is invalid or
        has a different major.
    """
    if local_pv is None:
        local_pv = PROTOCOL_VERSION
    peer = _parse_protocol_version(peer_pv)
    if peer is None:
        _logger.warning(f"[Compatibility] invalid protocol version: {peer_pv!r}")
        return False
    return peer[0] == local_pv[0]
