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


def build_json(
    mem: Optional[MemoryResult],
    lat: Optional[LatencyStats],
    fps64: Optional[FpsResult],
    fps128: Optional[FpsResult],
    burst: Optional[BurstResult],
    stress: Optional[StressResult],
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
            "memory": mem.to_dict() if mem else None,
            "latency": lat.to_dict() if lat else None,
            "fps_64": fps64.to_dict() if fps64 else None,
            "fps_128": fps128.to_dict() if fps128 else None,
            "burst": burst.to_dict() if burst else None,
            "stress": stress.to_dict() if stress else None,
        },
    }


def save_json(data: dict, path: str) -> None:
    """Save benchmark results to a JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n  ✓ Results saved to {path}")
