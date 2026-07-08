from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

from .display import _B as _BOLD
from .display import _C as _CYAN
from .display import _G as _GREEN
from .display import _R as _RESET
from .display import row, sep

_RED = "\033[31m" if sys.stdout.isatty() else ""


def _resolve_path(name: str) -> Path:
    """Resolve name to a file path.

    Try: exact path → .vltxbench/saved/<name>.json → .vltxbench/saved/<name>
    """
    p = Path(name)
    if p.exists():
        return p
    vltx = Path(".vltxbench") / "saved"
    for candidate in [vltx / name, vltx / (name + ".json"), vltx / name]:
        if candidate.exists():
            return candidate
    sys.exit(
        f"  ERROR: Result not found: {name}\n    Looked in: {p}, {vltx / name}.json, {vltx / name}"
    )


def _load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
        return data


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

# ... to add: stress

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
    "fps_64": "FPS — 64 players @ 64 Hz",
    "fps_128": "FPS — 128 players @ 20 Hz",
    "burst": "BURST",
    "stress": "STRESS",
}


def _v(v: Any, fmt: str) -> str:
    """Format a value or return —— if None."""
    if v is None:
        return "——"
    return fmt.format(v)


def _delta(a_val: Any, b_val: Any) -> str:
    """Return formatted delta string or empty."""
    if a_val is None or b_val is None:
        return ""
    try:
        d = float(b_val) - float(a_val)
        if d == 0:
            return "  0"
        return f"  {d:+.2f}" if isinstance(d, float) and d == int(d) else f"  {d:+.2f}"
    except (TypeError, ValueError):
        return ""


def _pct(a_val: Any, b_val: Any, higher_better: Optional[bool]) -> str:
    """Return formatted % change with color."""
    if a_val is None or b_val is None:
        return ""
    try:
        a = float(a_val)
        b = float(b_val)
        if a == 0:
            return ""
        change = (b - a) / a * 100
    except (TypeError, ValueError):
        return ""

    if change == 0:
        return "  0.0%"

    sign = "+" if change > 0 else ""
    text = f"  {sign}{change:.1f}%"

    is_improvement = (change < 0 and higher_better is False) or (
        change > 0 and higher_better is True
    )

    if is_improvement:
        return f"{_GREEN}{text}{_RESET}"
    else:
        return f"{_RED}{text}{_RESET}"


def _show_section(
    label: str,
    a_data: dict[str, Any],
    b_data: dict[str, Any],
    metrics: list[tuple[str, str, str, Optional[bool]]],
) -> None:
    row("", "")
    row(f"  {_CYAN}{label}{_RESET}", "")
    sep("─")

    for metric_label, key, fmt, hb in metrics:
        a_val = a_data.get(key)
        b_val = b_data.get(key)

        a_str = _v(a_val, fmt)
        b_str = _v(b_val, fmt)
        d_str = _delta(a_val, b_val)
        p_str = _pct(a_val, b_val, hb)

        line = f"    {metric_label:<28} {a_str:>22}  {b_str:>22}"
        if d_str or p_str:
            line += f" {d_str:>8}{p_str:>10}"
        print(line)

    row("", "")


def cmd_cmp(a_name: str, b_name: str) -> None:
    a_path = _resolve_path(a_name)
    b_path = _resolve_path(b_name)

    a_data = _load(a_path)
    b_data = _load(b_path)

    a_results = a_data.get("results", {})
    b_results = b_data.get("results", {})

    a_ver = a_data.get("veltix_version", "?")
    b_ver = b_data.get("veltix_version", "?")
    a_ts = a_data.get("timestamp", "?")
    b_ts = b_data.get("timestamp", "?")

    # ── Header ────────────────────────────────────────────────────────────────
    print()
    sep("=")
    print(f"  {_BOLD}COMPARE{_RESET}  {a_name}  vs  {b_name}")
    sep("=")
    row("Version", f"{a_ver}  vs  {b_ver}")
    row("Timestamp", f"{a_ts}  vs  {b_ts}")

    a_sys = a_data.get("system", {})
    b_sys = b_data.get("system", {})
    # Only show system info if it differs
    for key in ("python", "os", "cpu_logical", "ram_gb"):
        av = a_sys.get(key, "?")
        bv = b_sys.get(key, "?")
        if av != bv:
            row(key.replace("_", " ").title(), f"{av}  vs  {bv}")

    # ── Sections ──────────────────────────────────────────────────────────────
    for bench_name, metrics in _BENCH_METRICS.items():
        a_r = a_results.get(bench_name)
        b_r = b_results.get(bench_name)

        if a_r is None and b_r is None:
            continue

        label = _BENCH_LABELS.get(bench_name, bench_name.upper())

        # If result is a list (e.g. multiple runs/backends), use the first entry
        a_obj = a_r[0] if isinstance(a_r, list) else a_r
        b_obj = b_r[0] if isinstance(b_r, list) else b_r

        if a_obj is None or b_obj is None:
            continue

        _show_section(label, a_obj, b_obj, metrics)

    sep("=")
    print()
