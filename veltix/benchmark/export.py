"""
export.py
---------
JSON serialization and file export for benchmark results.
"""

from __future__ import annotations

import json
import platform
import sys
from datetime import datetime, timezone
from typing import Optional

import psutil

import veltix

from .models import BurstResult, FpsResult, LatencyStats, MemoryResult, StressResult


def _normalise(value):
    if value is None:
        return None
    if isinstance(value, list):
        return [r.to_dict() for r in value] if value else None
    return value.to_dict()


def build_json(
    mem: Optional[MemoryResult | list[MemoryResult]],
    lat: Optional[LatencyStats | list[LatencyStats]],
    fps64: Optional[FpsResult | list[FpsResult]],
    fps128: Optional[FpsResult | list[FpsResult]],
    burst: Optional[BurstResult | list[BurstResult]],
    stress: Optional[StressResult | list[StressResult]],
) -> dict:
    """Build a JSON-serializable dict from benchmark results."""
    return {
        "veltix_version": veltix.__version__,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "system": {
            "python": sys.version.split()[0],
            "cpu_logical": psutil.cpu_count(logical=True),
            "cpu_physical": psutil.cpu_count(logical=False),
            "cpu_model": platform.processor() or "unknown",
            "ram_gb": round(psutil.virtual_memory().total / 1_073_741_824, 1),
            "os": sys.platform,
            "os_version": platform.version(),
            "machine": platform.machine(),
        },
        "results": {
            "memory": _normalise(mem),
            "latency": _normalise(lat),
            "fps_64": _normalise(fps64),
            "fps_128": _normalise(fps128),
            "burst": _normalise(burst),
            "stress": _normalise(stress),
        },
    }


def save_json(data: dict, path: str) -> None:
    """Save benchmark results to a JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n  ✓ Results saved to {path}")
