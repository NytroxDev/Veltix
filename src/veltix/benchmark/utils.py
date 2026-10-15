"""
utils.py
--------
Shared low-level helpers used across benchmarks:
  - Environment capture (CPU model / governor / frequency, load, affinity)
  - RAM measurement (bytes / KB / MB)
  - Thread-safe counter and timestamp list helpers
"""

from __future__ import annotations

import contextlib
import os
import platform
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import threading

    import psutil  # type: ignore[import-untyped]

# ── psutil process handle (lazy) ─────────────────────────────────────────────
_proc: psutil.Process | None = None


def _get_proc() -> psutil.Process:
    global _proc
    if _proc is None:
        import psutil  # runtime import (TYPE_CHECKING is False at runtime)

        _proc = psutil.Process(os.getpid())
    return _proc


# ── Environment helpers (reproducibility context) ─────────────────────────────


def cpu_model() -> str:
    """Return a human-readable CPU model, best-effort per platform.

    Returns:
        The ``model name`` line from ``/proc/cpuinfo`` on Linux, otherwise the
        platform processor string, falling back to ``"unknown"``.
    """
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as fh:
            for line in fh:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine() or "unknown"


def cpu_governor() -> str | None:
    """Return the CPU frequency governor, or None when unavailable.

    Returns:
        The governor name (e.g. ``"performance"``), or None when the platform
        exposes no ``cpufreq`` sysfs entry.
    """
    try:
        with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", encoding="utf-8") as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def cpu_freq_mhz() -> float | None:
    """Return the current CPU frequency in MHz, or None when unavailable."""
    try:
        with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", encoding="utf-8") as fh:
            return round(int(fh.read().strip()) / 1000.0, 1)
    except (OSError, ValueError):
        return None


def load_average() -> list[float] | None:
    """Return the 1/5/15-minute load averages, or None when unavailable."""
    try:
        return [round(value, 2) for value in os.getloadavg()]
    except (OSError, AttributeError):
        return None


def process_affinity() -> list[int] | None:
    """Return the CPUs this process may run on, or None when unavailable.

    A count smaller than the machine's logical CPU count means the benchmark is
    pinned and therefore not comparable to an unpinned run.
    """
    try:
        return sorted(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        return None


# ── RAM helpers ───────────────────────────────────────────────────────────────


def ram_bytes() -> int:
    return _get_proc().memory_info().rss  # type: ignore[no-any-return]


def ram_kb() -> float:
    return ram_bytes() / 1_024


def ram_mb() -> float:
    return ram_kb() / 1_024


# ── Live benchmark resources (interrupt-time cleanup) ─────────────────────────

_live: list[Any] = []


def track(server: Any) -> None:
    """Register a live server so it is closed if the suite is interrupted."""
    _live.append(server)


def untrack(server: Any) -> None:
    """Remove a server from the live set after it has been closed normally."""
    if server in _live:
        _live.remove(server)


def cleanup() -> None:
    """Force-close every tracked server (called on KeyboardInterrupt)."""
    for obj in reversed(_live):
        close = getattr(obj, "close_all", None)
        if callable(close):
            with contextlib.suppress(Exception):
                close()
    _live.clear()


# ── Thread-safe helpers ───────────────────────────────────────────────────────


def incr(counter: list[int], lock: threading.Lock) -> None:
    """Increment a single-element list counter under a lock."""
    with lock:
        counter[0] += 1


def append_ts(ts_list: list[float], lock: threading.Lock) -> None:
    """Append current perf_counter timestamp to a list under a lock."""
    import time

    with lock:
        ts_list.append(time.perf_counter())
