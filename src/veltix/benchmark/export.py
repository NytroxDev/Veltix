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

# File format version of the exported JSON - bump on breaking schema changes.
# v2 adds run-to-run dispersion: ``n_runs`` and a per-metric ``metrics`` block
# (median, IQR, 95% CI). v1 files were plain per-run means, so v1 and v2 files
# are deliberately not comparable.
FORMAT_VERSION = 2


def _normalise(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, list):
        return [r.to_dict() for r in value] if value else None
    return value.to_dict()


def _get_system_info() -> dict:
    import psutil  # type: ignore[import-untyped]

    from . import utils

    return {
        "python": sys.version.split()[0],
        "python_impl": platform.python_implementation(),
        "cpu_logical": psutil.cpu_count(logical=True),
        "cpu_physical": psutil.cpu_count(logical=False),
        "cpu_model": utils.cpu_model(),
        "cpu_mhz": utils.cpu_freq_mhz(),
        "cpu_governor": utils.cpu_governor(),
        "load_avg": utils.load_average(),
        "affinity": utils.process_affinity(),
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
    *,
    harness: dict[str, Any] | None = None,
) -> dict:
    """Build the JSON payload for an exported run.

    Args:
        mem: Memory result(s), or None when the bench was not selected.
        lat: Latency result(s), or None.
        fps: FPS result(s), or None.
        burst: Burst result(s), or None.
        stress: Stress result(s), or None.
        harness: Reproducibility settings that produced the results (runs,
            warmup, cooldown, pinning, ...). Recorded verbatim.

    Returns:
        A JSON-serializable dict.
    """
    return {
        "format_version": FORMAT_VERSION,
        "veltix_version": veltix.__version__,
        "engine": _engine_name(),
        "timestamp": datetime.now(UTC).isoformat(),
        "system": _get_system_info(),
        "harness": harness or {},
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
