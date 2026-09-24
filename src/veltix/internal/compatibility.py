"""
compatibility.py
-----------------
Version and protocol compatibility for the Veltix wire format.

Starting with v2.0.3, the handshake uses a dedicated protocol version
(:data:`PROTOCOL_VERSION`) that is decoupled from the package version.
Two peers are wire-compatible if and only if they share the same protocol
*MAJOR* component. This is symmetric: a newer peer and an older peer both
accept each other as long as their protocol majors match.

The old ``COMPATIBILITY`` table and :meth:`Version.is_compatible` are kept
for backward compatibility with the public API but are deprecated. New code
should use :data:`PROTOCOL_VERSION` and :func:`protocol_is_compatible`.
"""

from __future__ import annotations

import dataclasses
import re

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


@dataclasses.dataclass
class Version:
    """Represents a semantic version (major.minor.patch).

    Can be used as a dict key via __hash__.
    Equality is based on all three components.

    Examples:
        >>> Version(1, 6, 6)
        Version(major=1, minor=6, patch=6)
        >>> Version.from_str("v1.6.6")
        Version(major=1, minor=6, patch=6)
    """

    major: int
    minor: int
    patch: int

    @classmethod
    def from_str(cls, version_str: str) -> Version:
        """
        Parse a version string into a Version object.

        Accepts optional leading 'v' prefix (e.g. 'v1.6.6' or '1.6.6').
        PEP 440 pre-release suffixes are stripped (e.g. '2.0.0b1' -> 2.0.0).
        Only the first three numeric components are used.

        Args:
            version_str: Version string to parse.

        Returns:
            Parsed Version instance.

        Raises:
            ValueError: If the string is not a valid version.
        """
        version_str = version_str[1:] if version_str.startswith("v") else version_str
        return Version(*[int(re.sub(r"[^0-9].*", "", p)) for p in version_str.split(".")[:3]])

    def is_compatible(self, other: Version) -> bool | None:
        """
        Check whether this version is compatible with another.

        Deprecated:
            Kept for backward compatibility with the old table-based API.
            New code should use :func:`protocol_is_compatible` with
            :data:`PROTOCOL_VERSION` instead.

        Looks up self in the COMPATIBILITY table and checks if other
        is listed as a compatible peer.

        Args:
            other: The version to check compatibility against.

        Returns:
            True  if the versions are compatible.
            False if self is known but other is not in its compatible list.
            None  if self is not registered in the compatibility table
                  (unknown version - treat as incompatible).
        """
        if self in COMPATIBILITY:
            result = other in COMPATIBILITY[self]
            if result:
                _logger.debug(f"[Compatibility] {self} compatible with {other}")
            else:
                _logger.warning(f"[Compatibility] {self} incompatible with {other}")
            return result

        _logger.warning(f"[Compatibility] {self} is not registered in the compatibility table")
        return None

    def __hash__(self) -> int:
        return hash((self.major, self.minor, self.patch))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __repr__(self) -> str:
        return f"Version({self.major}, {self.minor}, {self.patch})"


# ---------------------------------------------------------------------------
# Deprecated compatibility table
# ---------------------------------------------------------------------------
# Kept for backward compatibility with the public API. The handshake no
# longer uses this table. New code should rely on PROTOCOL_VERSION.
# ---------------------------------------------------------------------------

COMPATIBILITY: dict[Version, list[Version]] = {
    Version(2, 0, 3): [Version(2, 0, 3)],
    Version(2, 0, 2): [Version(2, 0, 1), Version(2, 0, 0), Version(2, 0, 2)],
    Version(2, 0, 1): [Version(2, 0, 1), Version(2, 0, 0)],
    Version(2, 0, 0): [Version(2, 0, 0)],
    Version(1, 9, 0): [Version(1, 9, 0)],
    Version(1, 8, 1): [Version(1, 8, 1)],
    Version(1, 8, 0): [Version(1, 8, 0)],
}
