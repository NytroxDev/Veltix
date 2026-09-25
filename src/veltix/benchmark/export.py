"""
export.py
---------
JSON serialization and file export for benchmark results.
"""

from __future__ import annotations

import json
import platform
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import veltix

if TYPE_CHECKING:
    from .models import BurstResult, FpsResult, LatencyStats, MemoryResult, StressResult

# File format version of the exported JSON - bump on breaking schema changes
FORMAT_VERSION = 1


def _normalise(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, list):
        return [r.to_dict() for r in value] if value else None
    return value.to_dict()


def _get_system_info() -> dict:
    import psutil  # type: ignore[import-untyped]

    return {
        "python": sys.version.split()[0],
        "cpu_logical": psutil.cpu_count(logical=True),
        "cpu_physical": psutil.cpu_count(logical=False),
        "cpu_model": platform.processor() or "unknown",
        "ram_gb": round(psutil.virtual_memory().total / 1_073_741_824, 1),
        "os": sys.platform,
        "os_version": platform.version(),
        "machine": platform.machine(),
    }


def _engine_name() -> str:
    from veltix.network import _rust

    return _rust.engine_name()


def build_json(
    mem: MemoryResult | list[MemoryResult] | None,
    lat: LatencyStats | list[LatencyStats] | None,
    fps: FpsResult | list[FpsResult] | None,
    burst: BurstResult | list[BurstResult] | None,
    stress: StressResult | list[StressResult] | None,
) -> dict:
    """Build a JSON-serializable dict from benchmark results."""
    return {
        "format_version": FORMAT_VERSION,
        "veltix_version": veltix.__version__,
        "engine": _engine_name(),
        "timestamp": datetime.now(UTC).isoformat(),
        "system": _get_system_info(),
        "results": {
            "memory": _normalise(mem),
            "latency": _normalise(lat),
            "fps": _normalise(fps),
            "burst": _normalise(burst),
            "stress": _normalise(stress),
        },
    }


def save_json(data: dict, path: str) -> None:
    """Save benchmark results to a JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n  ✓ Results saved to {path}")
