"""
utils.py
--------
Shared low-level helpers used across benchmarks:
  - RAM measurement (bytes / KB / MB)
  - Thread-safe counter and timestamp list helpers
"""

from __future__ import annotations

import os
import threading

import psutil

# ── psutil process handle ─────────────────────────────────────────────────────
_proc = psutil.Process(os.getpid())


# ── RAM helpers ───────────────────────────────────────────────────────────────


def ram_bytes() -> int:
    return _proc.memory_info().rss


def ram_kb() -> float:
    return ram_bytes() / 1_024


def ram_mb() -> float:
    return ram_kb() / 1_024


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
