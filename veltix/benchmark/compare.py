"""
compare.py
----------
Side-by-side comparison of two saved benchmark JSON files.

Usage:
    python -m benchmark --compare results_a.json results_b.json
"""

from __future__ import annotations

import json
from typing import Any, Optional, cast

from .display import _B as _BOLD
from .display import _C as _CYAN
from .display import _G as _GREEN
from .display import _R as _RESET
from .display import row, sep

_RED = "\033[31m" if __import__("sys").stdout.isatty() else ""


def _v(value: Any, fmt: str) -> str:
    if value is None:
        return "——"
    return fmt.format(value)


def _delta(a: Any, b: Any) -> str:
    if a is None or b is None:
        return ""
    try:
        d = float(b) - float(a)
        if d == 0:
            return "   0"
        return f"  {d:+9.2f}"
    except (TypeError, ValueError):
        return ""


def _pct(a: Any, b: Any, higher_better: Optional[bool]) -> str:
    if a is None or b is None:
        return ""
    try:
        av = float(a)
        bv = float(b)
        if av == 0:
            return ""
        change = (bv - av) / av * 100
    except (TypeError, ValueError):
        return ""

    if change == 0:
        return "   0.0%"

    sign = "+" if change > 0 else ""
    text = f"  {sign}{change:.1f}%"

    is_improvement = (change < 0 and higher_better is False) or (
        change > 0 and higher_better is True
    )
    return f"{_GREEN}{text}{_RESET}" if is_improvement else f"{_RED}{text}{_RESET}"


# ── Metrics per bench: (label, json_key, fmt, higher_better) ────────────────

_MEMORY_METRICS: list[tuple[str, str, str, Optional[bool]]] = [
    ("Baseline RSS", "baseline_kb", "{:.1f} KB", None),
    ("Idle server", "server_idle_kb", "{:.1f} KB", False),
    ("Per client (avg)", "client_cost_avg_kb", "{:.1f} KB", False),
    ("Per client (min)", "client_cost_min_kb", "{:.1f} KB", False),
    ("Per client (max)", "client_cost_max_kb", "{:.1f} KB", False),
    ("Per client (median)", "client_cost_median_kb", "{:.1f} KB", False),
    ("Per client (stdev)", "client_cost_stdev_kb", "{:.1f} KB", False),
    ("10 clients", "ram_10_clients_kb", "{:.1f} KB", None),
    ("50 clients", "ram_50_clients_kb", "{:.1f} KB", None),
    ("After teardown", "ram_after_teardown_kb", "{:.1f} KB", None),
    ("Leak delta", "leak_kb", "{:+.1f} KB", False),
]

_LATENCY_METRICS: list[tuple[str, str, str, Optional[bool]]] = [
    ("Count", "count", "{:,}", None),
    ("Avg", "avg_ms", "{:.4f} ms", False),
    ("P50", "p50_ms", "{:.4f} ms", False),
    ("P95", "p95_ms", "{:.3f} ms", False),
    ("P99", "p99_ms", "{:.3f} ms", False),
    ("Min", "min_ms", "{:.4f} ms", False),
    ("Max", "max_ms", "{:.3f} ms", False),
    ("Stdev", "stdev_ms", "{:.3f} ms", False),
    ("Jitter", "jitter_ms", "{:.3f} ms", False),
    ("Throughput", "throughput", "{:,.1f} ping/s", True),
]

_FPS_METRICS: list[tuple[str, str, str, Optional[bool]]] = [
    ("Target tick", "tick_rate", "{} Hz", None),
    ("Actual tick", "actual_tick_rate", "{:.1f} Hz", True),
    ("Duration", "duration_s", "{:.2f} s", None),
    ("Sent total", "total_sent", "{:,}", None),
    ("Received", "total_recv", "{:,}", None),
    ("Success rate", "success_rate", "{:.1f}%", True),
    ("Throughput", "msg_per_sec", "{:,.0f} msg/s", True),
    ("RAM delta", "ram_delta_mb", "{:.2f} MB", None),
    ("Errors", "errors", "{:,}", False),
    ("Tick avg", "tick_avg_ms", "{:.3f} ms", False),
    ("Tick min", "tick_min_ms", "{:.3f} ms", False),
    ("Tick max", "tick_max_ms", "{:.3f} ms", False),
    ("Tick stdev", "tick_stdev_ms", "{:.3f} ms", False),
    ("Budget comply", "tick_budget_pct", "{:.1f}%", True),
    ("Overrun ticks", "overrun_ticks", "{:,}", False),
]

_BURST_METRICS: list[tuple[str, str, str, Optional[bool]]] = [
    ("Messages", "count", "{:,}", None),
    ("Payload", "payload_bytes", "{} B", None),
    ("Send throughput", "send_throughput", "{:,.0f} msg/s", True),
    ("Recv throughput", "recv_throughput", "{:,.0f} msg/s", True),
    ("Data", "data_mbps", "{:.3f} MB/s", True),
    ("Success rate", "success_rate", "{:.2f}%", True),
    ("Total duration", "duration_s", "{:.1f} ms", None),
    ("Send duration", "send_duration_s", "{:.1f} ms", None),
    ("Drain P50", "drain_p50_ms", "{:.1f} ms", False),
    ("Drain P95", "drain_p95_ms", "{:.1f} ms", False),
    ("Drain P99", "drain_p99_ms", "{:.1f} ms", False),
    ("Drain max", "drain_max_ms", "{:.1f} ms", False),
    ("Drain jitter", "drain_jitter_ms", "{:.3f} ms", False),
    ("Recv gap avg", "recv_gap_avg_ms", "{:.3f} ms", False),
]

_STRESS_METRICS: list[tuple[str, str, str, Optional[bool]]] = [
    ("Clients", "num_clients", "{:,}", None),
    ("Msgs/client", "msgs_per_client", "{:,}", None),
    ("Sent", "total_sent", "{:,}", None),
    ("Received", "total_recv", "{:,}", None),
    ("Success rate", "success_rate", "{:.2f}%", True),
    ("Throughput", "throughput", "{:,.0f} msg/s", True),
    ("Duration", "duration_s", "{:.1f} ms", None),
    ("RAM delta", "ram_delta_mb", "{:+.2f} MB", None),
    ("Send phase", "send_phase_s", "{:.1f} ms", None),
    ("Drain time", "drain_time_s", "{:.1f} ms", False),
    ("TTFR", "time_to_first_recv_ms", "{:.1f} ms", False),
    ("Per-client TPS avg", "per_client_tps_avg", "{:,.0f}", True),
    ("Per-client TPS min", "per_client_tps_min", "{:,.0f}", True),
    ("Per-client TPS max", "per_client_tps_max", "{:,.0f}", True),
    ("Per-client TPS sd", "per_client_tps_stdev", "{:,.0f}", False),
]

_BENCH_METRICS: dict[str, list[tuple[str, str, str, Optional[bool]]]] = {
    "memory": _MEMORY_METRICS,
    "latency": _LATENCY_METRICS,
    "fps_64": _FPS_METRICS,
    "fps_128": _FPS_METRICS,
    "burst": _BURST_METRICS,
    "stress": _STRESS_METRICS,
}

_BENCH_LABELS: dict[str, str] = {
    "memory": "MEMORY",
    "latency": "LATENCY",
    "fps_64": "FPS \u2014 64 players @ 64 Hz",
    "fps_128": "FPS \u2014 128 players @ 20 Hz",
    "burst": "BURST",
    "stress": "STRESS",
}


def _show_section(
    label: str,
    a_data: dict[str, Any],
    b_data: dict[str, Any],
    metrics: list[tuple[str, str, str, Optional[bool]]],
) -> tuple[int, int, int]:
    """Render a section and return (a_wins, b_wins, ties)."""
    print()
    print(f"  {_CYAN}{label}{_RESET}")
    sep("─")

    a_wins = b_wins = ties = 0

    for metric_label, key, fmt, hb in metrics:
        a_val = a_data.get(key)
        b_val = b_data.get(key)

        a_str = _v(a_val, fmt)
        b_str = _v(b_val, fmt)
        d_str = _delta(a_val, b_val)
        p_str = _pct(a_val, b_val, hb)

        line = f"    {metric_label:<28} {a_str:>22}  {b_str:>22}"
        if d_str or p_str:
            line += f" {d_str:>10}{p_str:>10}"

        if hb is not None and a_val is not None and b_val is not None:
            try:
                if float(a_val) == float(b_val):
                    ties += 1
                elif hb:
                    if float(b_val) > float(a_val):
                        b_wins += 1
                    else:
                        a_wins += 1
                else:
                    if float(b_val) < float(a_val):
                        b_wins += 1
                    else:
                        a_wins += 1
            except (TypeError, ValueError):
                pass

        print(line)

    print()
    return a_wins, b_wins, ties


def _load(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return cast("dict[str, Any]", json.load(f))


def _first_result(results: Any) -> Optional[dict[str, Any]]:
    """Extract first result object from a bench entry (handles list/None)."""
    if results is None:
        return None
    if isinstance(results, list):
        return cast("dict[str, Any]", results[0]) if results else None
    return cast("dict[str, Any]", results)


def cmd_compare(a_path: str, b_path: str) -> None:
    """
    Compare two saved benchmark JSON result files.

    Args:
        a_path: Path to the first result file.
        b_path: Path to the second result file.
    """
    a_data = _load(a_path)
    b_data = _load(b_path)

    a_results = a_data.get("results", {})
    b_results = b_data.get("results", {})

    a_ver = a_data.get("veltix_version", "?")
    b_ver = b_data.get("veltix_version", "?")
    a_ts = a_data.get("timestamp", "?")
    b_ts = b_data.get("timestamp", "?")

    print()
    sep("=")
    print(f"  {_BOLD}COMPARE{_RESET}  {a_path}  vs  {b_path}")
    sep("=")
    row("Version", f"{a_ver}  vs  {b_ver}")
    row("Timestamp", f"{a_ts}  vs  {b_ts}")

    a_sys = a_data.get("system", {})
    b_sys = b_data.get("system", {})
    for key in ("python", "os", "cpu_logical", "ram_gb"):
        av = a_sys.get(key, "?")
        bv = b_sys.get(key, "?")
        if av != bv:
            row(key.replace("_", " ").title(), f"{av}  vs  {bv}")

    total_a = total_b = total_ties = 0

    for bench_name, metrics in _BENCH_METRICS.items():
        a_r = _first_result(a_results.get(bench_name))
        b_r = _first_result(b_results.get(bench_name))

        if a_r is None and b_r is None:
            continue

        if a_r is None or b_r is None:
            continue

        label = _BENCH_LABELS.get(bench_name, bench_name.upper())
        a_wins, b_wins, ties = _show_section(label, a_r, b_r, metrics)
        total_a += a_wins
        total_b += b_wins
        total_ties += ties

    sep("=")
    print()
    print(f"  {_BOLD}SUMMARY{_RESET}")
    sep("\u2500")
    winner = ""
    if total_a > total_b:
        winner = f"  {_GREEN}{a_path} is better{_RESET}"
    elif total_b > total_a:
        winner = f"  {_GREEN}{b_path} is better{_RESET}"
    else:
        winner = "  Equal performance"
    row("A wins", str(total_a))
    row("B wins", str(total_b))
    row("Ties", str(total_ties))
    row("", "")
    row("Verdict", winner)
    sep("=")
    print()
