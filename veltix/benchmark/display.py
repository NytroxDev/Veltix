"""
display.py
----------
Terminal rendering helpers and the README-ready summary table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional, Union

from veltix import format_bytes

from .config import WIDTH

if TYPE_CHECKING:
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


_ColFmt = Callable[[Any], str]

# ── Summary ───────────────────────────────────────────────────────────────────

CW = 22  # value column width (applies in both modes)


def _val(v: str) -> str:
    return f"{v:>{CW}}"


def _fmt_kb(kb: float) -> str:
    return format_bytes(int(kb * 1_024))


# ── Row helpers per benchmark ─────────────────────────────────────────────────


def _memory_defs() -> list[tuple[str, str, _ColFmt]]:
    """Return (label, attr, fmt) triples.  attr is poked via getattr."""
    return [
        ("Baseline", "baseline_kb", _fmt_kb),
        ("Idle server", "server_idle_kb", _fmt_kb),
        ("Per client (avg)", "client_cost_kb", _fmt_kb),
        ("Per client (min)", "client_cost_min_kb", _fmt_kb),
        ("Per client (max)", "client_cost_max_kb", _fmt_kb),
        ("Per client (med)", "client_cost_median_kb", _fmt_kb),
        ("Per client (stdev)", "client_cost_stdev_kb", lambda v: f"{v:.1f} KB"),
        ("10 clients", "ram_10_clients_kb", _fmt_kb),
        ("50 clients", "ram_50_clients_kb", _fmt_kb),
        ("After teardown", "ram_after_teardown_kb", _fmt_kb),
        ("Leak delta", "leak_kb", lambda v: f"{v:.1f} KB"),
    ]


def _latency_defs() -> list[tuple[str, str, _ColFmt]]:
    return [
        ("Count", "count", str),
        ("Avg", "avg", lambda v: f"{v:.3f} ms"),
        ("P50", "median", lambda v: f"{v:.4f} ms"),
        ("P95", "p95", lambda v: f"{v:.3f} ms"),
        ("P99", "p99", lambda v: f"{v:.3f} ms"),
        ("Min", "min", lambda v: f"{v:.3f} ms"),
        ("Max", "max", lambda v: f"{v:.3f} ms"),
        ("Stdev", "stdev", lambda v: f"{v:.3f} ms"),
        ("Jitter", "jitter_ms", lambda v: f"{v:.3f} ms"),
        ("Throughput", "throughput", lambda v: f"{v:,.1f} ping/s"),
    ]


def _fps_defs() -> list[tuple[str, str, _ColFmt]]:
    return [
        ("Target tick", "tick_rate", lambda v: f"{v} Hz"),
        ("Actual tick", "actual_tick_rate", lambda v: f"{v:.1f} Hz"),
        ("Duration", "duration_s", lambda v: f"{v:.2f} s"),
        ("Sent total", "total_sent", lambda v: f"{v:,}"),
        ("Received", "total_recv", lambda v: f"{v:,}"),
        ("Success rate", "success_rate", lambda v: f"{v:.1f}%"),
        ("Throughput", "msg_per_sec", lambda v: f"{v:,.0f} msg/s"),
        ("RAM delta", "ram_delta_mb", lambda v: f"{v:+.2f} MB"),
        ("Errors", "errors", lambda v: f"{v:,}"),
        ("Tick avg", "tick_avg_ms", lambda v: f"{v:.3f} ms"),
        ("Tick min", "tick_min_ms", lambda v: f"{v:.3f} ms"),
        ("Tick max", "tick_max_ms", lambda v: f"{v:.3f} ms"),
        ("Tick stdev", "tick_stdev_ms", lambda v: f"{v:.3f} ms"),
        ("Budget comply", "tick_budget_pct", lambda v: f"{v:.1f}%"),
        ("Overrun ticks", "overrun_ticks", str),
    ]


def _burst_defs() -> list[tuple[str, str, _ColFmt]]:
    return [
        ("Messages", "count", lambda v: f"{v:,}"),
        ("Payload", "payload_bytes", lambda v: f"{v} B"),
        ("Send throughput", "send_throughput", lambda v: f"{v:,.0f} msg/s"),
        ("Recv throughput", "recv_throughput", lambda v: f"{v:,.0f} msg/s"),
        ("Data", "data_mbps", lambda v: f"{v:.2f} MB/s"),
        ("Success rate", "success_rate", lambda v: f"{v:.2f}%"),
        ("Total duration", "duration_s", lambda v: f"{v * 1000:.1f} ms"),
        ("Send duration", "send_duration_s", lambda v: f"{v * 1000:.1f} ms"),
        ("Drain P50", "drain_p50_ms", lambda v: f"{v:.1f} ms"),
        ("Drain P95", "drain_p95_ms", lambda v: f"{v:.1f} ms"),
        ("Drain P99", "drain_p99_ms", lambda v: f"{v:.1f} ms"),
        ("Drain max", "drain_max_ms", lambda v: f"{v:.1f} ms"),
        ("Drain jitter", "drain_jitter_ms", lambda v: f"{v:.3f} ms"),
        ("Recv gap avg", "recv_gap_avg_ms", lambda v: f"{v:.3f} ms"),
    ]


def _stress_defs() -> list[tuple[str, str, _ColFmt]]:
    return [
        ("Clients", "num_clients", lambda v: f"{v:,}"),
        ("Msgs/client", "msgs_per_client", lambda v: f"{v:,}"),
        ("Sent", "total_sent", lambda v: f"{v:,}"),
        ("Received", "total_recv", lambda v: f"{v:,}"),
        ("Success rate", "success_rate", lambda v: f"{v:.2f}%"),
        ("Throughput", "throughput", lambda v: f"{v:,.0f} msg/s"),
        ("Duration", "duration_s", lambda v: f"{v * 1000:.1f} ms"),
        ("RAM delta", "ram_delta_mb", lambda v: f"{v:+.2f} MB"),
        ("Send phase", "send_phase_s", lambda v: f"{v * 1000:.1f} ms"),
        ("Drain time", "drain_time_s", lambda v: f"{v * 1000:.1f} ms"),
        ("TTFR", "time_to_first_recv_ms", lambda v: f"{v:.1f} ms"),
        ("Per-client TPS avg", "per_client_tps_avg", lambda v: f"{v:,.0f}"),
        ("Per-client TPS min", "per_client_tps_min", lambda v: f"{v:,.0f}"),
        ("Per-client TPS max", "per_client_tps_max", lambda v: f"{v:,.0f}"),
        ("Per-client TPS sd", "per_client_tps_stdev", lambda v: f"{v:,.0f}"),
    ]


# ── Single-backend mode ───────────────────────────────────────────────────────


def _show_single_section(title: str, defs: list[tuple[str, str, _ColFmt]], result: Any) -> None:
    print(f"  {title}")
    for label, attr, fmt in defs:
        value = getattr(result, attr)
        print(f"    {label:<28}{_val(fmt(value))}")
    print()


def _show_single(
    mem: Any,
    lat: Any,
    fps64: Any,
    fps128: Any,
    burst: Any,
    stress: Any,
) -> None:
    if mem:
        _show_single_section("MEMORY", _memory_defs(), mem[0])
    if lat:
        _show_single_section("LATENCY", _latency_defs(), lat[0])
    if fps64:
        _show_single_section("FPS — 64 players @ 64 Hz", _fps_defs(), fps64[0])
    if fps128:
        _show_single_section("FPS — 128 players @ 20 Hz", _fps_defs(), fps128[0])
    if burst:
        _show_single_section("BURST", _burst_defs(), burst[0])
    if stress:
        _show_single_section("STRESS", _stress_defs(), stress[0])


# ── Both-backends mode ────────────────────────────────────────────────────────


def _sbw(label: str) -> str:
    """Print side-by-side value line."""
    return f"{label:<28}"


def _show_both_section(
    title: str, defs: list[tuple[str, str, _ColFmt]], results: list[Any]
) -> None:
    print(f"  {title}")
    for label, attr, fmt in defs:
        parts = "".join(_val(fmt(getattr(r, attr))) for r in results)
        print(f"    {_sbw(label)}{parts}")
    print()


def _show_side_by_side(
    mem: Any,
    lat: Any,
    fps64: Any,
    fps128: Any,
    burst: Any,
    stress: Any,
) -> None:
    if mem:
        _show_both_section("MEMORY", _memory_defs(), mem)
    if lat:
        _show_both_section("LATENCY", _latency_defs(), lat)
    if fps64:
        _show_both_section("FPS — 64 players @ 64 Hz", _fps_defs(), fps64)
    if fps128:
        _show_both_section("FPS — 128 players @ 20 Hz", _fps_defs(), fps128)
    if burst:
        _show_both_section("BURST", _burst_defs(), burst)
    if stress:
        _show_both_section("STRESS", _stress_defs(), stress)


# ── Public API ────────────────────────────────────────────────────────────────


def _results(value: Any) -> Optional[list[Any]]:
    """Normalize to list or None."""
    if value is None:
        return None
    if isinstance(value, list):
        return value if value else None
    return [value]


def _is_both(*groups: Any) -> bool:
    return any(g is not None and len(g) > 1 for g in groups)


def print_summary(
    mem: Optional[Union[MemoryResult, list[MemoryResult]]],
    lat: Optional[Union[LatencyStats, list[LatencyStats]]],
    fps64: Optional[Union[FpsResult, list[FpsResult]]],
    fps128: Optional[Union[FpsResult, list[FpsResult]]],
    burst: Optional[Union[BurstResult, list[BurstResult]]],
    stress: Optional[Union[StressResult, list[StressResult]]],
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
        backends = []
        for g in (mem, lat, fps64, fps128, burst, stress):
            if g:
                backends = [r.backend for r in g]
                break
        label_w = 28
        header_parts = "".join(f"{b:>{CW}}" for b in backends)
        print(f"  {'':<{label_w}}{header_parts}")
        sep("─")
        _show_side_by_side(mem, lat, fps64, fps128, burst, stress)
    else:
        _show_single(mem, lat, fps64, fps128, burst, stress)

    sep("─")
    print()
