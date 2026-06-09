"""
models.py
---------
Dataclasses for benchmark results.
Each class exposes a to_dict() method for JSON export.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LatencyStats:
    """Accumulates latency samples and exposes common percentile statistics."""

    _samples: list[float] = field(default_factory=list, repr=False)
    jitter_ms: float = 0.0
    throughput: float = 0.0
    backend: str = "async"

    def add(self, value: Optional[float]) -> None:
        if value is not None:
            self._samples.append(value)

    @property
    def count(self) -> int:
        return len(self._samples)

    @property
    def avg(self) -> float:
        return statistics.mean(self._samples) if self._samples else 0.0

    @property
    def median(self) -> float:
        return statistics.median(self._samples) if self._samples else 0.0

    def percentile(self, pct: float) -> float:
        if not self._samples:
            return 0.0
        s = sorted(self._samples)
        return s[min(int(len(s) * pct / 100), len(s) - 1)]

    @property
    def p95(self) -> float:
        return self.percentile(95)

    @property
    def p99(self) -> float:
        return self.percentile(99)

    @property
    def min(self) -> float:
        return min(self._samples) if self._samples else 0.0

    @property
    def max(self) -> float:
        return max(self._samples) if self._samples else 0.0

    @property
    def stdev(self) -> float:
        return statistics.stdev(self._samples) if len(self._samples) > 1 else 0.0

    @staticmethod
    def average(results: list[LatencyStats]) -> LatencyStats:
        combined = LatencyStats()
        for r in results:
            combined._samples.extend(r._samples)
        combined.jitter_ms = statistics.mean(r.jitter_ms for r in results)
        combined.throughput = statistics.mean(r.throughput for r in results)
        combined.backend = results[0].backend if results else "async"
        return combined

    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "avg_ms": round(self.avg, 4),
            "p50_ms": round(self.median, 4),
            "p95_ms": round(self.p95, 4),
            "p99_ms": round(self.p99, 4),
            "min_ms": round(self.min, 4),
            "max_ms": round(self.max, 4),
            "stdev_ms": round(self.stdev, 4),
            "jitter_ms": round(self.jitter_ms, 3),
            "throughput": round(self.throughput, 1),
            "backend": self.backend,
        }


@dataclass
class MemoryResult:
    baseline_kb: float
    server_idle_kb: float
    # Per-client cost stats (measured over first 10 clients)
    client_cost_kb: float  # avg
    client_cost_min_kb: float
    client_cost_max_kb: float
    client_cost_median_kb: float
    client_cost_stdev_kb: float
    ram_10_clients_kb: float
    ram_50_clients_kb: float
    # Teardown / leak detection
    ram_after_teardown_kb: float
    leak_kb: float
    backend: str = "async"

    @staticmethod
    def average(results: list[MemoryResult]) -> MemoryResult:
        return MemoryResult(
            baseline_kb=statistics.mean(r.baseline_kb for r in results),
            server_idle_kb=statistics.mean(r.server_idle_kb for r in results),
            client_cost_kb=statistics.mean(r.client_cost_kb for r in results),
            client_cost_min_kb=statistics.mean(r.client_cost_min_kb for r in results),
            client_cost_max_kb=statistics.mean(r.client_cost_max_kb for r in results),
            client_cost_median_kb=statistics.mean(r.client_cost_median_kb for r in results),
            client_cost_stdev_kb=statistics.mean(r.client_cost_stdev_kb for r in results),
            ram_10_clients_kb=statistics.mean(r.ram_10_clients_kb for r in results),
            ram_50_clients_kb=statistics.mean(r.ram_50_clients_kb for r in results),
            ram_after_teardown_kb=statistics.mean(r.ram_after_teardown_kb for r in results),
            leak_kb=statistics.mean(r.leak_kb for r in results),
            backend=results[0].backend if results else "async",
        )

    def to_dict(self) -> dict:
        return {
            "baseline_kb": round(self.baseline_kb, 1),
            "server_idle_kb": round(self.server_idle_kb, 1),
            "client_cost_avg_kb": round(self.client_cost_kb, 1),
            "client_cost_min_kb": round(self.client_cost_min_kb, 1),
            "client_cost_max_kb": round(self.client_cost_max_kb, 1),
            "client_cost_median_kb": round(self.client_cost_median_kb, 1),
            "client_cost_stdev_kb": round(self.client_cost_stdev_kb, 1),
            "ram_10_clients_kb": round(self.ram_10_clients_kb, 1),
            "ram_50_clients_kb": round(self.ram_50_clients_kb, 1),
            "ram_after_teardown_kb": round(self.ram_after_teardown_kb, 1),
            "leak_kb": round(self.leak_kb, 1),
            "backend": self.backend,
        }


@dataclass
class FpsResult:
    players: int
    tick_rate: int
    duration_s: float
    total_sent: int
    total_recv: int
    msg_per_sec: float
    success_rate: float
    ram_delta_mb: float
    errors: int
    # Tick accuracy
    actual_tick_rate: float
    tick_avg_ms: float
    tick_min_ms: float
    tick_max_ms: float
    tick_stdev_ms: float
    tick_budget_pct: float
    overrun_ticks: int
    backend: str = "async"

    @staticmethod
    def average(results: list[FpsResult]) -> FpsResult:
        return FpsResult(
            players=results[0].players,
            tick_rate=results[0].tick_rate,
            duration_s=statistics.mean(r.duration_s for r in results),
            total_sent=round(statistics.mean(r.total_sent for r in results)),
            total_recv=round(statistics.mean(r.total_recv for r in results)),
            msg_per_sec=statistics.mean(r.msg_per_sec for r in results),
            success_rate=statistics.mean(r.success_rate for r in results),
            ram_delta_mb=statistics.mean(r.ram_delta_mb for r in results),
            errors=round(statistics.mean(r.errors for r in results)),
            actual_tick_rate=statistics.mean(r.actual_tick_rate for r in results),
            tick_avg_ms=statistics.mean(r.tick_avg_ms for r in results),
            tick_min_ms=statistics.mean(r.tick_min_ms for r in results),
            tick_max_ms=statistics.mean(r.tick_max_ms for r in results),
            tick_stdev_ms=statistics.mean(r.tick_stdev_ms for r in results),
            tick_budget_pct=statistics.mean(r.tick_budget_pct for r in results),
            overrun_ticks=round(statistics.mean(r.overrun_ticks for r in results)),
            backend=results[0].backend if results else "async",
        )

    def to_dict(self) -> dict:
        return {
            "players": self.players,
            "tick_rate": self.tick_rate,
            "actual_tick_rate": round(self.actual_tick_rate, 2),
            "duration_s": round(self.duration_s, 3),
            "total_sent": self.total_sent,
            "total_recv": self.total_recv,
            "msg_per_sec": round(self.msg_per_sec, 1),
            "success_rate": round(self.success_rate, 2),
            "ram_delta_mb": round(self.ram_delta_mb, 2),
            "errors": self.errors,
            "tick_avg_ms": round(self.tick_avg_ms, 3),
            "tick_min_ms": round(self.tick_min_ms, 3),
            "tick_max_ms": round(self.tick_max_ms, 3),
            "tick_stdev_ms": round(self.tick_stdev_ms, 3),
            "tick_budget_pct": round(self.tick_budget_pct, 1),
            "overrun_ticks": self.overrun_ticks,
            "backend": self.backend,
        }


@dataclass
class BurstResult:
    count: int
    payload_bytes: int
    send_throughput: float
    recv_throughput: float
    data_mbps: float
    success_rate: float
    duration_s: float
    send_duration_s: float
    # Pipeline drain latency (time from send start to recv)
    drain_p50_ms: float
    drain_p95_ms: float
    drain_p99_ms: float
    drain_max_ms: float
    drain_jitter_ms: float
    recv_gap_avg_ms: float
    backend: str = "async"

    @staticmethod
    def average(results: list[BurstResult]) -> BurstResult:
        return BurstResult(
            count=round(statistics.mean(r.count for r in results)),
            payload_bytes=results[0].payload_bytes,
            send_throughput=statistics.mean(r.send_throughput for r in results),
            recv_throughput=statistics.mean(r.recv_throughput for r in results),
            data_mbps=statistics.mean(r.data_mbps for r in results),
            success_rate=statistics.mean(r.success_rate for r in results),
            duration_s=statistics.mean(r.duration_s for r in results),
            send_duration_s=statistics.mean(r.send_duration_s for r in results),
            drain_p50_ms=statistics.mean(r.drain_p50_ms for r in results),
            drain_p95_ms=statistics.mean(r.drain_p95_ms for r in results),
            drain_p99_ms=statistics.mean(r.drain_p99_ms for r in results),
            drain_max_ms=statistics.mean(r.drain_max_ms for r in results),
            drain_jitter_ms=statistics.mean(r.drain_jitter_ms for r in results),
            recv_gap_avg_ms=statistics.mean(r.recv_gap_avg_ms for r in results),
            backend=results[0].backend if results else "async",
        )

    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "payload_bytes": self.payload_bytes,
            "send_throughput": round(self.send_throughput, 1),
            "recv_throughput": round(self.recv_throughput, 1),
            "data_mbps": round(self.data_mbps, 3),
            "success_rate": round(self.success_rate, 2),
            "duration_s": round(self.duration_s, 3),
            "send_duration_s": round(self.send_duration_s, 3),
            "drain_p50_ms": round(self.drain_p50_ms, 1),
            "drain_p95_ms": round(self.drain_p95_ms, 1),
            "drain_p99_ms": round(self.drain_p99_ms, 1),
            "drain_max_ms": round(self.drain_max_ms, 1),
            "drain_jitter_ms": round(self.drain_jitter_ms, 3),
            "recv_gap_avg_ms": round(self.recv_gap_avg_ms, 3),
            "backend": self.backend,
        }


@dataclass
class StressResult:
    num_clients: int
    msgs_per_client: int
    total_sent: int
    total_recv: int
    success_rate: float
    throughput: float
    duration_s: float
    ram_delta_mb: float
    # Timing breakdown
    send_phase_s: float
    drain_time_s: float
    time_to_first_recv_ms: float
    # Per-client throughput
    per_client_tps_avg: float
    per_client_tps_min: float
    per_client_tps_max: float
    per_client_tps_stdev: float
    backend: str = "async"

    @staticmethod
    def average(results: list[StressResult]) -> StressResult:
        return StressResult(
            num_clients=results[0].num_clients,
            msgs_per_client=results[0].msgs_per_client,
            total_sent=round(statistics.mean(r.total_sent for r in results)),
            total_recv=round(statistics.mean(r.total_recv for r in results)),
            success_rate=statistics.mean(r.success_rate for r in results),
            throughput=statistics.mean(r.throughput for r in results),
            duration_s=statistics.mean(r.duration_s for r in results),
            ram_delta_mb=statistics.mean(r.ram_delta_mb for r in results),
            send_phase_s=statistics.mean(r.send_phase_s for r in results),
            drain_time_s=statistics.mean(r.drain_time_s for r in results),
            time_to_first_recv_ms=statistics.mean(r.time_to_first_recv_ms for r in results),
            per_client_tps_avg=statistics.mean(r.per_client_tps_avg for r in results),
            per_client_tps_min=statistics.mean(r.per_client_tps_min for r in results),
            per_client_tps_max=statistics.mean(r.per_client_tps_max for r in results),
            per_client_tps_stdev=statistics.mean(r.per_client_tps_stdev for r in results),
            backend=results[0].backend if results else "async",
        )

    def to_dict(self) -> dict:
        return {
            "num_clients": self.num_clients,
            "msgs_per_client": self.msgs_per_client,
            "total_sent": self.total_sent,
            "total_recv": self.total_recv,
            "success_rate": round(self.success_rate, 2),
            "throughput": round(self.throughput, 1),
            "duration_s": round(self.duration_s, 3),
            "ram_delta_mb": round(self.ram_delta_mb, 2),
            "send_phase_s": round(self.send_phase_s, 3),
            "drain_time_s": round(self.drain_time_s, 3),
            "time_to_first_recv_ms": round(self.time_to_first_recv_ms, 1),
            "per_client_tps_avg": round(self.per_client_tps_avg, 1),
            "per_client_tps_min": round(self.per_client_tps_min, 1),
            "per_client_tps_max": round(self.per_client_tps_max, 1),
            "per_client_tps_stdev": round(self.per_client_tps_stdev, 1),
            "backend": self.backend,
        }
