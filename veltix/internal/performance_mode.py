"""Performance mode configuration for Veltix."""

from __future__ import annotations

import dataclasses
from enum import Enum, auto


class PerformanceMode(Enum):
    """
    Performance mode for Veltix clients and servers.

    Controls socket timeout, affecting the trade-off between CPU usage
    and disconnection detection speed.

    LOW:      ~1.0s detection, minimal CPU. Good for low-traffic or constrained envs.
    BALANCED: ~0.5s detection, recommended default.
    HIGH:     ~0.1s detection, higher CPU. For latency-sensitive applications.
    AUTO:     Dynamic adjustment based on traffic (coming soon).
    """

    LOW = auto()
    BALANCED = auto()
    HIGH = auto()
    AUTO = auto()


@dataclasses.dataclass(frozen=True)
class PerformanceModeSettings:
    """Internal settings derived from a PerformanceMode."""

    socket_timeout: float
    description: str


PERFORMANCE_SETTINGS: dict[PerformanceMode, PerformanceModeSettings] = {
    PerformanceMode.LOW: PerformanceModeSettings(
        socket_timeout=1.0,
        description="Low CPU usage, slower disconnection detection (~1.0s)",
    ),
    PerformanceMode.BALANCED: PerformanceModeSettings(
        socket_timeout=0.5,
        description="Balanced CPU usage and reactivity (~0.5s) — recommended",
    ),
    PerformanceMode.HIGH: PerformanceModeSettings(
        socket_timeout=0.1,
        description="Fast disconnection detection (~0.1s), higher CPU usage",
    ),
    PerformanceMode.AUTO: PerformanceModeSettings(
        socket_timeout=0.5,
        description="Dynamic adjustment based on traffic (coming soon)",
    ),
}


def get_settings(mode: PerformanceMode) -> PerformanceModeSettings:
    return PERFORMANCE_SETTINGS[mode]
