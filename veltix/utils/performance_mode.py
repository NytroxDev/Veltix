"""Performance mode configuration for Veltix."""

import dataclasses
from enum import Enum, auto


class PerformanceMode(Enum):
    """
    Performance mode for Veltix clients and servers.

    Controls internal timing parameters like socket timeout, which affects
    the trade-off between CPU usage and disconnection detection speed.

    Attributes:
        LOW:      Minimal CPU usage. Slower disconnection detection (~1.0s).
                  Best for low-traffic servers or resource-constrained environments.
        BALANCED: Good compromise between CPU and reactivity (~0.5s).
                  Recommended for most use cases. This is the default.
        HIGH:     Fast disconnection detection (~0.1s) at the cost of more CPU.
                  Best for latency-sensitive or high-traffic applications.
        AUTO:     Dynamically adjusts based on traffic and connected clients.
                  Requires monitoring to be enabled. (Coming in a future release)
    """

    LOW = auto()
    BALANCED = auto()
    HIGH = auto()
    AUTO = auto()


@dataclasses.dataclass(frozen=True)
class PerformanceModeSettings:
    """
    Internal settings derived from a PerformanceMode.

    Attributes:
        socket_timeout: Socket recv timeout in seconds
        description: Human-readable description of the mode
    """

    socket_timeout: float
    description: str


# Mapping from PerformanceMode to concrete settings
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
        socket_timeout=0.5,  # fallback until monitoring is implemented
        description="Dynamic adjustment based on traffic (coming soon)",
    ),
}


def get_settings(mode: PerformanceMode) -> PerformanceModeSettings:
    """
    Get the concrete settings for a given performance mode.

    Args:
        mode: Performance mode to look up

    Returns:
        PerformanceModeSettings for the given mode
    """
    return PERFORMANCE_SETTINGS[mode]
