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
        return s[int(len(s) * pct / 100)]

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
    # Pipeline drain latency
    recv_lat_p50_ms: float
    recv_lat_p95_ms: float
    recv_lat_p99_ms: float
    recv_lat_max_ms: float
    recv_jitter_ms: float

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
            "recv_lat_p50_ms": round(self.recv_lat_p50_ms, 1),
            "recv_lat_p95_ms": round(self.recv_lat_p95_ms, 1),
            "recv_lat_p99_ms": round(self.recv_lat_p99_ms, 1),
            "recv_lat_max_ms": round(self.recv_lat_max_ms, 1),
            "recv_jitter_ms": round(self.recv_jitter_ms, 3),
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
        }
