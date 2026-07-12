"""Protocol message flags for the Veltix wire format."""

from __future__ import annotations

from enum import IntFlag


class MessageFlag(IntFlag):
    """
    Bitfield flags stored in the protocol header (1 byte).

    Internal to the protocol. Not part of the public API.
    """

    NONE = 0x00
