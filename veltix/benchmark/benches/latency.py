from __future__ import annotations

import statistics
import time

from veltix import Client, ClientConfig, Server, ServerConfig, SocketCore

from ..benchmark import Benchmark
from ..config import PORT_LATENCY
from ..display import header, row
from ..models import LatencyStats

_WARMUP = 20

_BUCKETS = [
    ("<0.1 ms  -- instant", lambda v: v < 0.1),
    ("0.1-0.5 ms -- normal", lambda v: 0.1 <= v < 0.5),
    ("0.5-1 ms  -- noisy", lambda v: 0.5 <= v < 1.0),
    (">1 ms     -- outlier", lambda v: v >= 1.0),
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
        bar = "#" * int(pct / 2)
        row(f"    {label}", f"{count:>5}  ({pct:5.1f}%)  {bar}")


class LatencyBench(Benchmark):
    name = "latency"
    description = "Ping/pong latency measurement"

    def run(self, backend: SocketCore) -> LatencyStats:
        port = self.config.get("port", PORT_LATENCY)
        iterations = self.config.get("iterations", 50_000)
        return _run_latency(iterations=iterations, port=port, socket_core=backend.name.lower())


def run(
    iterations: int = 50_000, port: int = PORT_LATENCY, socket_core: str = "async"
) -> LatencyStats:
    return _run_latency(iterations=iterations, port=port, socket_core=socket_core)


def _run_latency(
    iterations: int, port: int, socket_core: str
) -> LatencyStats:
    header("2 PING / PONG LATENCY")

    _socket = SocketCore.THREADING if socket_core == "threading" else SocketCore.ASYNC

    server = Server(ServerConfig(host="127.0.0.1", port=port, socket_core=_socket))
    server.start()
    time.sleep(0.3)

    client = Client(ClientConfig(server_addr="127.0.0.1", port=port, retry=0, socket_core=_socket))
    client.connect()
    time.sleep(0.2)

    warmup = LatencyStats()
    for _ in range(_WARMUP):
        warmup.add(client.ping_server(timeout=2.0))
    row("Warmup iterations", str(_WARMUP))
    row("Warmup avg", f"{warmup.avg:.3f} ms  (discarded)")

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

    if len(samples_raw) >= 2:
        deltas = [abs(samples_raw[i] - samples_raw[i - 1]) for i in range(1, len(samples_raw))]
        jitter = statistics.stdev(deltas) if len(deltas) > 1 else 0.0
    else:
        jitter = 0.0

    throughput = stats.count / elapsed

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
