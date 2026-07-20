from __future__ import annotations

import dataclasses
from enum import Enum, auto


class DisconnectReason(Enum):
    """
    Reason for a disconnection.

    Attributes:
        SERVER_CLOSED: Server closed the connection cleanly.
        ERROR:         Fatal network error (reset, aborted, etc.).
        MANUAL:        disconnect() was called manually by the user.
    """

    SERVER_CLOSED = auto()
    ERROR = auto()
    MANUAL = auto()


@dataclasses.dataclass
class DisconnectState:
    """
    State passed to the on_disconnect callback.

    Attributes:
        permanent:   True if the client has given up reconnecting.
                     False if a reconnection attempt will follow.
        attempt:     Current retry attempt number (0 = first disconnection,
                     before any retry has been attempted).
        retry_max:   Maximum number of retry attempts configured.
        reason:      Why the disconnection occurred.
    """

    permanent: bool
    attempt: int
    retry_max: int
    reason: DisconnectReason
