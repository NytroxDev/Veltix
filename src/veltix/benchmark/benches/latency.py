"""
benches/latency.py
------------------
Benchmark 2 — Ping / pong latency.

Measures:
  - avg, median, p95, p99, min, max, stdev  (ms)
  - Jitter: stdev of *consecutive* sample deltas (ms)
    (stdev measures spread from the mean; jitter measures moment-to-moment
     variability — a low-jitter connection is more predictable even if avg is high)
  - Throughput: successful pings per second
  - Latency histogram bucketed into four ranges:
      < 0.1 ms  — essentially instant (loopback ideal)
      0.1–0.5 ms — normal loopback range
      0.5–1 ms  — mild scheduling noise
      > 1 ms    — outliers / OS scheduler hiccup
  - Warmup stats (displayed separately, not included in main results)
"""

from __future__ import annotations

import time

from veltix import Client, ClientConfig, Server, ServerConfig, SocketCore

from ..config import PORT_LATENCY
from ..display import header, row
from ..models import LatencyStats

_WARMUP = 20

_BUCKETS = [
    ("<0.1 ms  — instant", lambda v: v < 0.1),
    ("0.1–0.5 ms — normal", lambda v: 0.1 <= v < 0.5),
    ("0.5–1 ms  — noisy", lambda v: 0.5 <= v < 1.0),
    (">1 ms     — outlier", lambda v: v >= 1.0),
]


def _histogram(samples: list[float]) -> None:
    n = len(samples)
    if not n:
        return
    row("", "")
    row("  Latency histogram", "")
    for label, predicate in _BUCKETS:
        count = sum(1 for v in samples if predicate(v))
        pct = count / n * 100
        bar = "█" * int(pct / 2)
        row(f"    {label}", f"{count:>5}  ({pct:5.1f}%)  {bar}")


def run(
    iterations: int = 50_000,
    port: int = PORT_LATENCY,
    socket_core: str = "async",
    step_label: str = "",
) -> LatencyStats:
    header("PING / PONG LATENCY", prefix=step_label)

    _socket = SocketCore.THREADING if socket_core == "threading" else SocketCore.ASYNC

    server = Server(ServerConfig(host="127.0.0.1", port=port, socket_core=_socket))
    server.start()
    time.sleep(0.3)

    client = Client(ClientConfig(server_addr="127.0.0.1", port=port, retry=0, socket_core=_socket))
    client.connect()
    time.sleep(0.2)

    # ── Warmup ────────────────────────────────────────────────────────────────
    warmup = LatencyStats()
    for _ in range(_WARMUP):
        warmup.add(client.ping_server(timeout=2.0))
    row("Warmup iterations", str(_WARMUP))
    row("Warmup avg", f"{warmup.avg:.3f} ms  (discarded)")

    # ── Main measurement ──────────────────────────────────────────────────────
    stats = LatencyStats()
    samples_raw: list[float] = []

    t0 = time.perf_counter()
    for _ in range(iterations):
        v = client.ping_server(timeout=2.0)
        stats.add(v)
        if v is not None:
            samples_raw.append(v)
    elapsed = time.perf_counter() - t0

    client.disconnect()
    server.close_all()
    time.sleep(0.3)

    # ── Jitter: stdev of consecutive deltas ───────────────────────────────────
    if len(samples_raw) >= 2:
        deltas = [abs(samples_raw[i] - samples_raw[i - 1]) for i in range(1, len(samples_raw))]
        import statistics

        jitter = statistics.stdev(deltas) if len(deltas) > 1 else 0.0
    else:
        jitter = 0.0

    throughput = stats.count / elapsed

    # ── Display ───────────────────────────────────────────────────────────────
    success_pct = stats.count / iterations * 100
    row("Iterations", f"{iterations:,}")
    row("Success rate", f"{success_pct:.1f}%")
    row("", "")
    row("  Latency stats", "")
    row("    Average", f"{stats.avg:.3f} ms")
    row("    Median P50", f"{stats.median:.3f} ms")
    row("    P95", f"{stats.p95:.3f} ms")
    row("    P99", f"{stats.p99:.3f} ms")
    row("    Min", f"{stats.min:.3f} ms")
    row("    Max", f"{stats.max:.3f} ms")
    row("    Stdev", f"{stats.stdev:.3f} ms")
    row("    Jitter", f"{jitter:.3f} ms")
    row("", "")
    row("  Throughput", f"{throughput:,.0f} ping/s")

    _histogram(samples_raw)

    stats.jitter_ms = jitter
    stats.throughput = throughput

    return stats
