"""
display.py
----------
Terminal rendering helpers and the README-ready summary table.
"""

from __future__ import annotations

from typing import Optional

from veltix import format_bytes

from .config import WIDTH
from .models import BurstResult, FpsResult, LatencyStats, MemoryResult, StressResult

# ── Low-level helpers ─────────────────────────────────────────────────────────

def sep(char: str = "─", width: int = WIDTH) -> None:
    print(char * width)


def header(title: str) -> None:
    print()
    sep("═")
    print(f"  {title}")
    sep("═")


def row(label: str, value: str, width: int = 36) -> None:
    print(f"  {label:<{width}}: {value}")


# ── Summary table helpers ─────────────────────────────────────────────────────

def _trow(label: str, value: str) -> None:
    print(f"│  {label:<21}│  {value:<43}│")


def _tdivider() -> None:
    print("├─────────────────────┼───────────────────────────────────────────────┤")


# ── Public summary ────────────────────────────────────────────────────────────

def _results(value):
    """Normalize to list or None."""
    if value is None:
        return None
    if isinstance(value, list):
        return value if value else None
    return [value]


def _show(mem, lat, fps64, fps128, burst, stress) -> None:
    """Internal rendering — assumes list values (or None)."""
    print()
    print("┌─────────────────────────────────────────────────────────────────────┐")
    print("│                    VELTIX PERFORMANCE RESULTS                       │")

    if mem:
        _tdivider()
        _trow("MEMORY", "")
        for r in mem:
            _trow(f"  Idle server ({r.backend})", format_bytes(int(r.server_idle_kb * 1_024)))
            _trow(f"  Per client ({r.backend})", format_bytes(int(r.client_cost_kb * 1_024)))
            _trow(f"  50 cl. total ({r.backend})", format_bytes(int(r.ram_50_clients_kb * 1_024)))

    if lat:
        _tdivider()
        _trow("LATENCY (local)", "")
        for r in lat:
            _trow(f"  Avg ({r.backend})", f"{r.avg:.3f} ms")
            _trow(f"  P95 ({r.backend})", f"{r.p95:.3f} ms")
            _trow(f"  P99 ({r.backend})", f"{r.p99:.3f} ms")
            _trow(f"  Max ({r.backend})", f"{r.max:.3f} ms")

    if fps64 or fps128:
        _tdivider()
        _trow("FPS SIMULATION", "")
        if fps64:
            for r in fps64:
                _trow(
                    f"  {r.players}p @{r.tick_rate}Hz ({r.backend})",
                    f"{r.msg_per_sec:,.0f} msg/s  –  {r.success_rate:.0f}% success",
                )
        if fps128:
            for r in fps128:
                _trow(
                    f"  {r.players}p @{r.tick_rate}Hz ({r.backend})",
                    f"{r.msg_per_sec:,.0f} msg/s  –  {r.success_rate:.0f}% success",
                )

    if burst:
        _tdivider()
        _trow("BURST THROUGHPUT", "")
        for r in burst:
            _trow(f"  Send ({r.backend})", f"{r.send_throughput:,.0f} msg/s")
            _trow(f"  Receive ({r.backend})", f"{r.recv_throughput:,.0f} msg/s")
            _trow(f"  Data ({r.backend})", f"{r.data_mbps:.2f} MB/s")

    if stress:
        _tdivider()
        _trow("CONCURRENT STRESS", "")
        for r in stress:
            _trow(
                f"  {r.num_clients} cl. ({r.backend})",
                f"{r.throughput:,.0f} msg/s  –  {r.success_rate:.0f}% success",
            )

    print("└─────────────────────┴───────────────────────────────────────────────┘")
    print()


def print_summary(
    mem: Optional[MemoryResult | list[MemoryResult]],
    lat: Optional[LatencyStats | list[LatencyStats]],
    fps64: Optional[FpsResult | list[FpsResult]],
    fps128: Optional[FpsResult | list[FpsResult]],
    burst: Optional[BurstResult | list[BurstResult]],
    stress: Optional[StressResult | list[StressResult]],
) -> None:
    header("📋  README-READY SUMMARY")
    _show(
        _results(mem),
        _results(lat),
        _results(fps64),
        _results(fps128),
        _results(burst),
        _results(stress),
    )