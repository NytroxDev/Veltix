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

def print_summary(
    mem: Optional[MemoryResult],
    lat: Optional[LatencyStats],
    fps64: Optional[FpsResult],
    fps128: Optional[FpsResult],
    burst: Optional[BurstResult],
    stress: Optional[StressResult],
) -> None:
    header("📋  README-READY SUMMARY")
    print()
    print("┌─────────────────────────────────────────────────────────────────────┐")
    print("│                    VELTIX PERFORMANCE RESULTS                       │")

    if mem:
        _tdivider()
        _trow("MEMORY", "")
        _trow("Idle server",     format_bytes(int(mem.server_idle_kb * 1_024)))
        _trow("Per client",      format_bytes(int(mem.client_cost_kb * 1_024)))
        _trow("50 clients total", format_bytes(int(mem.ram_50_clients_kb * 1_024)))

    if lat:
        _tdivider()
        _trow("LATENCY (local)", "")
        _trow("Average", f"{lat.avg:.3f} ms")
        _trow("P95",     f"{lat.p95:.3f} ms")
        _trow("P99",     f"{lat.p99:.3f} ms")
        _trow("Max",     f"{lat.max:.3f} ms")

    if fps64 or fps128:
        _tdivider()
        _trow("FPS SIMULATION", "")
        if fps64:
            _trow(
                f"{fps64.players} players @{fps64.tick_rate}Hz",
                f"{fps64.msg_per_sec:,.0f} msg/s  –  {fps64.success_rate:.0f}% success",
            )
        if fps128:
            _trow(
                f"{fps128.players} players @{fps128.tick_rate}Hz",
                f"{fps128.msg_per_sec:,.0f} msg/s  –  {fps128.success_rate:.0f}% success",
            )

    if burst:
        _tdivider()
        _trow("BURST THROUGHPUT", "")
        _trow("Send",    f"{burst.send_throughput:,.0f} msg/s")
        _trow("Receive", f"{burst.recv_throughput:,.0f} msg/s")
        _trow("Data",    f"{burst.data_mbps:.2f} MB/s")

    if stress:
        _tdivider()
        _trow("CONCURRENT STRESS", "")
        _trow(
            f"{stress.num_clients} clients",
            f"{stress.throughput:,.0f} msg/s  –  {stress.success_rate:.0f}% success",
        )

    print("└─────────────────────┴───────────────────────────────────────────────┘")
    print()