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


# ── Summary ───────────────────────────────────────────────────────────────────

def _val(v: str, width: int) -> str:
    return f"{v:>{width}}"


def _section(title: str, rows: list[tuple], backend_count: int, col_width: int) -> None:
    if not rows:
        return
    print(f"  {title}")
    if backend_count == 2:
        for label, *values in rows:
            parts = "".join(_val(v, col_width) for v in values)
            print(f"    {label:<28}{parts}")
    else:
        for label, value in rows:
            print(f"    {label:<28}{_val(value, col_width)}")


def _memory_rows(mem, col_width: int) -> list:
    rows = []
    for r in mem:
        suffix = f" ({r.backend})"
        rows.append(
            (f"Idle server{suffix}", format_bytes(int(r.server_idle_kb * 1_024)))
        )
        rows.append(
            (f"Per client{suffix}", format_bytes(int(r.client_cost_kb * 1_024)))
        )
        rows.append(
            (f"50 clients total{suffix}", format_bytes(int(r.ram_50_clients_kb * 1_024)))
        )
    return rows


def _latency_rows(lat, col_width: int) -> list:
    rows = []
    for r in lat:
        suffix = f" ({r.backend})"
        rows.append((f"Avg{suffix}", f"{r.avg:.3f} ms"))
        rows.append((f"P95{suffix}", f"{r.p95:.3f} ms"))
        rows.append((f"P99{suffix}", f"{r.p99:.3f} ms"))
        rows.append((f"Max{suffix}", f"{r.max:.3f} ms"))
    return rows


def _burst_rows(burst, col_width: int) -> list:
    rows = []
    for r in burst:
        suffix = f" ({r.backend})"
        rows.append((f"Send{suffix}", f"{r.send_throughput:,.0f} msg/s"))
        rows.append((f"Receive{suffix}", f"{r.recv_throughput:,.0f} msg/s"))
        rows.append((f"Data{suffix}", f"{r.data_mbps:.2f} MB/s"))
    return rows


def _fps_rows(fps, col_width: int) -> list:
    rows = []
    for r in fps:
        suffix = f" ({r.backend})"
        rows.append(
            (
                f"{r.players}p @{r.tick_rate}Hz{suffix}",
                f"{r.msg_per_sec:,.0f} msg/s ({r.success_rate:.0f}%)",
            )
        )
    return rows


def _stress_rows(stress, col_width: int) -> list:
    rows = []
    for r in stress:
        suffix = f" ({r.backend})"
        rows.append(
            (
                f"{r.num_clients} clients{suffix}",
                f"{r.throughput:,.0f} msg/s ({r.success_rate:.0f}%)",
            )
        )
    return rows


# ── Side-by-side helpers (both mode) ──────────────────────────────────────────

def _side_by_side(rows: list[tuple]) -> list[tuple]:
    """Group rows by label, side-by-side for 2 backends, preserving order."""
    by_name: dict[str, list[str]] = {}
    for label, value in rows:
        name = label.rsplit(" (", 1)[0]
        if name not in by_name:
            by_name[name] = []
        by_name[name].append(value)
    return [(name, *vals) for name, vals in by_name.items() if len(vals) == 2]


def _show_side_by_side(mem, lat, fps64, fps128, burst, stress) -> None:
    """Summary layout for two backends: side-by-side columns."""
    cw = 20  # column width for values

    if mem:
        rows = _side_by_side(_memory_rows(mem, cw))
        print(f"  MEMORY")
        for label, v1, v2 in rows:
            print(f"    {label:<28}{_val(v1, cw)}{_val(v2, cw)}")
        print()

    if lat:
        print(f"  LATENCY (local)")
        rows = _side_by_side(_latency_rows(lat, cw))
        for label, v1, v2 in rows:
            print(f"    {label:<28}{_val(v1, cw)}{_val(v2, cw)}")
        print()

    if fps64 or fps128:
        print(f"  FPS SIMULATION")
        if fps64:
            rows = _side_by_side(_fps_rows(fps64, cw))
            for label, v1, v2 in rows:
                print(f"    {label:<28}{_val(v1, cw)}{_val(v2, cw)}")
        if fps128:
            rows = _side_by_side(_fps_rows(fps128, cw))
            for label, v1, v2 in rows:
                print(f"    {label:<28}{_val(v1, cw)}{_val(v2, cw)}")
        print()

    if burst:
        print(f"  BURST THROUGHPUT")
        rows = _side_by_side(_burst_rows(burst, cw))
        for label, v1, v2 in rows:
            print(f"    {label:<28}{_val(v1, cw)}{_val(v2, cw)}")
        print()

    if stress:
        print(f"  CONCURRENT STRESS")
        rows = _side_by_side(_stress_rows(stress, cw))
        for label, v1, v2 in rows:
            print(f"    {label:<28}{_val(v1, cw)}{_val(v2, cw)}")
        print()


def _show_single(mem, lat, fps64, fps128, burst, stress) -> None:
    """Summary layout for a single backend."""
    cw = 20

    if mem:
        section = []
        for r in mem:
            section.append(("Idle server", format_bytes(int(r.server_idle_kb * 1_024))))
            section.append(("Per client", format_bytes(int(r.client_cost_kb * 1_024))))
            section.append(("50 clients total", format_bytes(int(r.ram_50_clients_kb * 1_024))))
        if section:
            print(f"  MEMORY")
            for label, value in section:
                print(f"    {label:<28}{_val(value, cw)}")
            print()

    if lat:
        print(f"  LATENCY (local)")
        for r in lat:
            print(f"    {'Avg':<28}{_val(f'{r.avg:.3f} ms', cw)}")
            print(f"    {'P95':<28}{_val(f'{r.p95:.3f} ms', cw)}")
            print(f"    {'P99':<28}{_val(f'{r.p99:.3f} ms', cw)}")
            print(f"    {'Max':<28}{_val(f'{r.max:.3f} ms', cw)}")
        print()

    if fps64 or fps128:
        print(f"  FPS SIMULATION")
        if fps64:
            for r in fps64:
                print(f"    {f'{r.players}p @{r.tick_rate}Hz':<28}"
                      f"{_val(f'{r.msg_per_sec:,.0f} msg/s ({r.success_rate:.0f}%)', cw)}")
        if fps128:
            for r in fps128:
                print(f"    {f'{r.players}p @{r.tick_rate}Hz':<28}"
                      f"{_val(f'{r.msg_per_sec:,.0f} msg/s ({r.success_rate:.0f}%)', cw)}")
        print()

    if burst:
        print(f"  BURST THROUGHPUT")
        for r in burst:
            print(f"    {'Send':<28}{_val(f'{r.send_throughput:,.0f} msg/s', cw)}")
            print(f"    {'Receive':<28}{_val(f'{r.recv_throughput:,.0f} msg/s', cw)}")
            print(f"    {'Data':<28}{_val(f'{r.data_mbps:.2f} MB/s', cw)}")
        print()

    if stress:
        print(f"  CONCURRENT STRESS")
        for r in stress:
            print(f"    {f'{r.num_clients} clients':<28}"
                  f"{_val(f'{r.throughput:,.0f} msg/s ({r.success_rate:.0f}%)', cw)}")
        print()


# ── Public API ────────────────────────────────────────────────────────────────

def _results(value):
    """Normalize to list or None."""
    if value is None:
        return None
    if isinstance(value, list):
        return value if value else None
    return [value]


def _is_both(*groups) -> bool:
    for g in groups:
        if g is not None and len(g) > 1:
            return True
    return False


def print_summary(
    mem: Optional[MemoryResult | list[MemoryResult]],
    lat: Optional[LatencyStats | list[LatencyStats]],
    fps64: Optional[FpsResult | list[FpsResult]],
    fps128: Optional[FpsResult | list[FpsResult]],
    burst: Optional[BurstResult | list[BurstResult]],
    stress: Optional[StressResult | list[StressResult]],
) -> None:
    header("📋  README-READY SUMMARY")
    print()

    mem = _results(mem)
    lat = _results(lat)
    fps64 = _results(fps64)
    fps128 = _results(fps128)
    burst = _results(burst)
    stress = _results(stress)

    if _is_both(mem, lat, fps64, fps128, burst, stress):
        # Derive backend names from first group with data
        backends = []
        for g in (mem, lat, fps64, fps128, burst, stress):
            if g:
                backends = [r.backend for r in g]
                break
        header_parts = "".join(f"{b:>20}" for b in backends)
        print(f"  {'':30}{header_parts}")
        sep("─")
        _show_side_by_side(mem, lat, fps64, fps128, burst, stress)
    else:
        _show_single(mem, lat, fps64, fps128, burst, stress)

    sep("─")
    print()
