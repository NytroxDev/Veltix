"""
compatibility.py
----------------
Version compatibility table for the Veltix protocol.

Defines which versions are wire-compatible with each other.
Used by HandshakeHandler to validate incoming connections.

Adding a new version
--------------------
When releasing a new version, add an entry to COMPATIBILITY:

    Version(1, 6, 7): [Version(1, 6, 7)],

To allow backward compatibility between two versions:

    Version(1, 6, 7): [Version(1, 6, 7), Version(1, 6, 6)],

Return values of Version.is_compatible():
    True  — versions are compatible, connection allowed
    False — versions are incompatible, connection should be rejected
    None  — version is unknown (not in the table), treat as incompatible
"""

from __future__ import annotations

import dataclasses
from typing import Optional

from ..logger import Logger

_logger = Logger.get_instance()


@dataclasses.dataclass()
class Version:
    """
    Represents a semantic version (major.minor.patch).

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
        Only the first three components are used.

        Args:
            version_str: Version string to parse.

        Returns:
            Parsed Version instance.

        Raises:
            ValueError: If the string is not a valid version.
        """
        version_str = version_str[1:] if version_str.startswith("v") else version_str
        return Version(*[int(part) for part in version_str.split(".")[:3]])

    def is_compatible(self, other: Version) -> Optional[bool]:
        """
        Check whether this version is compatible with another.

        Looks up self in the COMPATIBILITY table and checks if other
        is listed as a compatible peer.

        Args:
            other: The version to check compatibility against.

        Returns:
            True  if the versions are compatible.
            False if self is known but other is not in its compatible list.
            None  if self is not registered in the compatibility table
                  (unknown version — treat as incompatible).
        """
        if self in COMPATIBILITY:
            result = other in COMPATIBILITY[self]
            if result:
                _logger.debug(f"[Compatibility] {self} ↔ {other}: compatible ✓")
            else:
                _logger.warning(f"[Compatibility] {self} ↔ {other}: incompatible ✗")
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
# Compatibility table
# ---------------------------------------------------------------------------
# Keys   : the local version (self)
# Values : list of versions that are wire-compatible with the key
#
# By default each version is only compatible with itself (strict mode).
# To allow cross-version communication, add the peer version to the list.
# ---------------------------------------------------------------------------

COMPATIBILITY: dict[Version, list[Version]] = {
    Version(1, 8, 1): [Version(1, 8, 1)],
    Version(1, 8, 0): [Version(1, 8, 0)],
}
