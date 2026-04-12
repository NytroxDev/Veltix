"""
Veltix Benchmark Suite
======================
Measures memory footprint, latency, FPS server simulation, burst throughput,
and concurrent stress. Results are printed in a README-ready format and can
optionally be saved as JSON for sharing or uploading to the Veltix leaderboard.

Usage
-----
    # Run all benchmarks
    python benchmark.py

    # Run specific benchmarks
    python benchmark.py --only memory latency burst

    # Save results to JSON
    python benchmark.py --save results.json

    # Adjust parameters
    python benchmark.py --latency-iterations 5000 --stress-clients 200

Available benchmark IDs: memory, latency, fps, burst, stress
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional

import psutil

import veltix
from veltix import (
    Client,
    ClientConfig,
    Events,
    Logger,
    LogLevel,
    MessageType,
    Request,
    Server,
    ServerConfig,
    format_bytes,
)

# ── Silence library logs so benchmark output stays clean ──────────────────────
Logger.get_instance().set_level(LogLevel.ERROR)

# ── Message types used during simulations ─────────────────────────────────────
PLAYER_MOVE = MessageType(401, "player_move")  # 32 B  – position + rotation
PLAYER_SHOOT = MessageType(402, "player_shoot")  # 16 B  – bullet event
GAME_STATE = MessageType(403, "game_state")  # 512 B – world snapshot
PLAYER_JOIN = MessageType(404, "player_join")  # 64 B  – join handshake
CHAT_MSG = MessageType(405, "chat_msg")  # 128 B – chat packet

# ── psutil process handle ──────────────────────────────────────────────────────
_proc = psutil.Process(os.getpid())

# ── Terminal width ─────────────────────────────────────────────────────────────
_WIDTH = 72


# ══════════════════════════════════════════════════════════════════════════════
# Terminal helpers
# ══════════════════════════════════════════════════════════════════════════════


def _sep(char: str = "─", width: int = _WIDTH) -> None:
    print(char * width)


def _header(title: str) -> None:
    print()
    _sep("═")
    print(f"  {title}")
    _sep("═")


def _row(label: str, value: str, width: int = 36) -> None:
    print(f"  {label:<{width}}: {value}")


# ══════════════════════════════════════════════════════════════════════════════
# Memory helpers
# ══════════════════════════════════════════════════════════════════════════════


def _ram_bytes() -> int:
    return _proc.memory_info().rss


def _ram_kb() -> float:
    return _ram_bytes() / 1_024


def _ram_mb() -> float:
    return _ram_kb() / 1_024


# ══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ══════════════════════════════════════════════════════════════════════════════


def _incr(counter: list[int], lock: threading.Lock) -> None:
    with lock:
        counter[0] += 1


def _append_ts(ts_list: list[float], lock: threading.Lock) -> None:
    with lock:
        ts_list.append(time.perf_counter())


# ══════════════════════════════════════════════════════════════════════════════
# Data containers
# ══════════════════════════════════════════════════════════════════════════════


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
    client_cost_kb: float
    ram_10_clients_kb: float
    ram_50_clients_kb: float

    def to_dict(self) -> dict:
        return {
            "baseline_kb": round(self.baseline_kb, 1),
            "server_idle_kb": round(self.server_idle_kb, 1),
            "client_cost_kb": round(self.client_cost_kb, 1),
            "ram_10_clients_kb": round(self.ram_10_clients_kb, 1),
            "ram_50_clients_kb": round(self.ram_50_clients_kb, 1),
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

    def to_dict(self) -> dict:
        return {
            "players": self.players,
            "tick_rate": self.tick_rate,
            "duration_s": round(self.duration_s, 3),
            "total_sent": self.total_sent,
            "total_recv": self.total_recv,
            "msg_per_sec": round(self.msg_per_sec, 1),
            "success_rate": round(self.success_rate, 2),
            "ram_delta_mb": round(self.ram_delta_mb, 2),
            "errors": self.errors,
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

    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "payload_bytes": self.payload_bytes,
            "send_throughput": round(self.send_throughput, 1),
            "recv_throughput": round(self.recv_throughput, 1),
            "data_mbps": round(self.data_mbps, 3),
            "success_rate": round(self.success_rate, 2),
            "duration_s": round(self.duration_s, 3),
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
        }


# ══════════════════════════════════════════════════════════════════════════════
# Benchmark 1 – Baseline memory footprint
# ══════════════════════════════════════════════════════════════════════════════


def bench_memory(port: int = 20_001) -> MemoryResult:
    _header("① BASELINE MEMORY FOOTPRINT")

    gc.collect()
    baseline = _ram_kb()
    _row("Python process baseline", format_bytes(int(baseline * 1_024)))

    # ── bare server ────────────────────────────────────────────────────────────
    server = Server(ServerConfig(host="127.0.0.1", port=port))
    server.start()
    time.sleep(0.3)
    gc.collect()
    server_ram = _ram_kb()
    server_cost = server_ram - baseline
    _row(
        "Idle server (0 clients)",
        f"{format_bytes(int(server_ram * 1_024))}  (+{format_bytes(int(server_cost * 1_024))})",
    )

    # ── first 10 clients ──────────────────────────────────────────────────────
    clients: list[Client] = []
    costs: list[float] = []

    for _ in range(10):
        gc.collect()
        before = _ram_kb()
        c = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        c.connect()
        time.sleep(0.05)
        gc.collect()
        costs.append(_ram_kb() - before)
        clients.append(c)

    avg_cost = statistics.mean(costs)
    ram_10 = _ram_kb()
    _row("Cost per client (avg)", format_bytes(int(avg_cost * 1_024)))
    _row("Server + 10 clients", format_bytes(int(ram_10 * 1_024)))

    # ── scale to 50 clients ───────────────────────────────────────────────────
    for _ in range(40):
        c = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        c.connect()
        time.sleep(0.01)
        clients.append(c)

    time.sleep(0.5)
    gc.collect()
    ram_50 = _ram_kb()
    _row("Server + 50 clients", format_bytes(int(ram_50 * 1_024)))

    for c in clients:
        c.disconnect()
    server.close_all()
    time.sleep(0.3)

    return MemoryResult(
        baseline_kb=baseline,
        server_idle_kb=server_cost,
        client_cost_kb=avg_cost,
        ram_10_clients_kb=ram_10,
        ram_50_clients_kb=ram_50,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Benchmark 2 – Ping / pong latency
# ══════════════════════════════════════════════════════════════════════════════


def bench_latency(iterations: int = 2_000, port: int = 20_002) -> LatencyStats:
    _header("② PING / PONG LATENCY")

    server = Server(ServerConfig(host="127.0.0.1", port=port))
    server.start()
    time.sleep(0.3)

    client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
    client.connect()
    time.sleep(0.2)

    # warmup — discard results
    for _ in range(20):
        client.ping_server(timeout=2.0)

    stats = LatencyStats()
    t0 = time.perf_counter()
    for _ in range(iterations):
        stats.add(client.ping_server(timeout=2.0))
    elapsed = time.perf_counter() - t0

    client.disconnect()
    server.close_all()
    time.sleep(0.3)

    success_pct = stats.count / iterations * 100
    _row("Iterations", f"{iterations:,}")
    _row("Success rate", f"{success_pct:.1f}%")
    _row("Average", f"{stats.avg:.3f} ms")
    _row("Median (P50)", f"{stats.median:.3f} ms")
    _row("P95", f"{stats.p95:.3f} ms")
    _row("P99", f"{stats.p99:.3f} ms")
    _row("Min", f"{stats.min:.3f} ms")
    _row("Max", f"{stats.max:.3f} ms")
    _row("Std dev", f"{stats.stdev:.3f} ms")
    _row("Throughput", f"{stats.count / elapsed:,.0f} ping/s")

    return stats


# ══════════════════════════════════════════════════════════════════════════════
# Benchmark 3 – FPS game-server simulation
# ══════════════════════════════════════════════════════════════════════════════


def bench_fps(
    num_players: int = 64,
    tick_rate: int = 64,
    duration_s: float = 5.0,
    port: int = 20_003,
) -> FpsResult:
    """
    Simulates a realistic FPS server:
      - Every player sends PLAYER_MOVE each tick (32 B)
      - ~10% of players send PLAYER_SHOOT each tick (16 B)
    """
    _header(f"③ FPS SERVER SIMULATION  ({num_players} players @ {tick_rate} tick/s)")

    recv_count = [0]
    lock = threading.Lock()

    server = Server(ServerConfig(host="127.0.0.1", port=port))
    server.set_callback(Events.ON_RECV, lambda _c, _m: _incr(recv_count, lock))
    server.start()
    time.sleep(0.5)

    clients: list[Client] = []
    print(f"  Connecting {num_players} players...", end="", flush=True)
    for _ in range(num_players):
        c = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        c.connect()
        clients.append(c)
        time.sleep(0.005)
    time.sleep(0.5)
    print(" done")

    gc.collect()
    ram_before = _ram_mb()
    tick_interval = 1.0 / tick_rate
    total_sent = errors = 0

    print(f"  Running simulation for {duration_s}s...")
    t0 = time.perf_counter()

    while time.perf_counter() - t0 < duration_s:
        tick_start = time.perf_counter()
        for i, c in enumerate(clients):
            try:
                c.get_sender().send(Request(PLAYER_MOVE, b"\x00" * 32))
                total_sent += 1
                if i % 10 == int(time.perf_counter() * 10) % 10:
                    c.get_sender().send(Request(PLAYER_SHOOT, b"\x00" * 16))
                    total_sent += 1
            except Exception:
                errors += 1

        sleep_for = tick_interval - (time.perf_counter() - tick_start)
        if sleep_for > 0:
            time.sleep(sleep_for)

    actual = time.perf_counter() - t0
    time.sleep(0.5)
    gc.collect()
    ram_after = _ram_mb()

    recv = recv_count[0]
    success = recv / total_sent * 100 if total_sent else 0.0
    msg_per_sec = total_sent / actual

    _row("Players", str(num_players))
    _row("Tick rate", f"{tick_rate} Hz")
    _row("Duration", f"{actual:.2f} s")
    _row("Messages sent", f"{total_sent:,}")
    _row("Messages recv", f"{recv:,}")
    _row("Success rate", f"{success:.1f}%")
    _row("Throughput", f"{msg_per_sec:,.0f} msg/s")
    _row("RAM delta", f"{ram_after - ram_before:+.1f} MB")
    _row("Errors", str(errors))

    for c in clients:
        c.disconnect()
    server.close_all()
    time.sleep(0.3)

    return FpsResult(
        players=num_players,
        tick_rate=tick_rate,
        duration_s=actual,
        total_sent=total_sent,
        total_recv=recv,
        msg_per_sec=msg_per_sec,
        success_rate=success,
        ram_delta_mb=ram_after - ram_before,
        errors=errors,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Benchmark 4 – Burst throughput
# ══════════════════════════════════════════════════════════════════════════════


def bench_burst(
    count: int = 10_000,
    payload_size: int = 64,
    port: int = 20_004,
) -> BurstResult:
    _header(f"④ BURST THROUGHPUT  ({count:,} msgs × {payload_size} B)")

    received_ts: list[float] = []
    lock = threading.Lock()

    server = Server(ServerConfig(host="127.0.0.1", port=port))
    server.set_callback(
        Events.ON_RECV,
        lambda _c, _m: _append_ts(received_ts, lock),
    )
    server.start()
    time.sleep(0.3)

    client = Client(ClientConfig(server_addr="127.0.0.1", port=port))
    client.connect()
    time.sleep(0.2)

    payload = b"X" * payload_size
    gc.collect()

    t0 = time.perf_counter()
    for _ in range(count):
        client.get_sender().send(Request(PLAYER_MOVE, payload))
    send_done = time.perf_counter()

    # wait up to 10 s for all messages to arrive
    deadline = time.perf_counter() + 10.0
    while len(received_ts) < count and time.perf_counter() < deadline:
        time.sleep(0.05)
    total_elapsed = time.perf_counter() - t0

    recv_count = len(received_ts)
    send_throughput = count / (send_done - t0)
    recv_throughput = recv_count / total_elapsed
    data_mbps = (recv_count * payload_size) / total_elapsed / 1_048_576
    success = recv_count / count * 100

    _row("Messages", f"{count:,}")
    _row("Payload size", format_bytes(payload_size))
    _row("Send throughput", f"{send_throughput:,.0f} msg/s")
    _row("Recv throughput", f"{recv_throughput:,.0f} msg/s")
    _row("Data throughput", f"{data_mbps:.2f} MB/s")
    _row("Success rate", f"{success:.1f}%")
    _row("Total duration", f"{total_elapsed:.3f} s")

    client.disconnect()
    server.close_all()
    time.sleep(0.3)

    return BurstResult(
        count=count,
        payload_bytes=payload_size,
        send_throughput=send_throughput,
        recv_throughput=recv_throughput,
        data_mbps=data_mbps,
        success_rate=success,
        duration_s=total_elapsed,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Benchmark 5 – Concurrent stress
# ══════════════════════════════════════════════════════════════════════════════


def bench_stress(
    num_clients: int = 100,
    msgs_per_client: int = 100,
    port: int = 20_005,
) -> StressResult:
    _header(f"⑤ CONCURRENT STRESS  ({num_clients} clients × {msgs_per_client} msgs)")

    recv_count = [0]
    lock = threading.Lock()

    server = Server(ServerConfig(host="127.0.0.1", port=port))
    server.set_callback(Events.ON_RECV, lambda _c, _m: _incr(recv_count, lock))
    server.start()
    time.sleep(0.5)

    clients: list[Client] = []
    print(f"  Connecting {num_clients} clients...", end="", flush=True)
    for _ in range(num_clients):
        c = Client(ClientConfig(server_addr="127.0.0.1", port=port))
        c.connect()
        clients.append(c)
        time.sleep(0.003)
    time.sleep(0.5)
    print(" done")

    total_msgs = num_clients * msgs_per_client
    gc.collect()
    ram_before = _ram_mb()

    def _blast(c: Client) -> None:
        for _ in range(msgs_per_client):
            c.get_sender().send(Request(PLAYER_MOVE, b"\x00" * 32))

    print(f"  Firing {total_msgs:,} messages simultaneously...")
    t0 = time.perf_counter()

    with ThreadPoolExecutor(max_workers=num_clients) as pool:
        futures = [pool.submit(_blast, c) for c in clients]
        for f in futures:
            f.result()

    # wait up to 15 s for all messages to arrive
    deadline = time.perf_counter() + 15.0
    while recv_count[0] < total_msgs and time.perf_counter() < deadline:
        time.sleep(0.05)

    elapsed = time.perf_counter() - t0
    gc.collect()
    ram_after = _ram_mb()

    recv = recv_count[0]
    success = recv / total_msgs * 100
    throughput = recv / elapsed

    _row("Clients", str(num_clients))
    _row("Messages / client", str(msgs_per_client))
    _row("Total messages", f"{total_msgs:,}")
    _row("Received", f"{recv:,}")
    _row("Success rate", f"{success:.1f}%")
    _row("Throughput", f"{throughput:,.0f} msg/s")
    _row("Total duration", f"{elapsed:.3f} s")
    _row("RAM delta", f"{ram_after - ram_before:+.1f} MB")

    for c in clients:
        c.disconnect()
    server.close_all()
    time.sleep(0.3)

    return StressResult(
        num_clients=num_clients,
        msgs_per_client=msgs_per_client,
        total_sent=total_msgs,
        total_recv=recv,
        success_rate=success,
        throughput=throughput,
        duration_s=elapsed,
        ram_delta_mb=ram_after - ram_before,
    )


# ══════════════════════════════════════════════════════════════════════════════
# README-ready summary table
# ══════════════════════════════════════════════════════════════════════════════


def _trow(label: str, value: str) -> None:
    print(f"│  {label:<21}│  {value:<43}│")


def _tdivider() -> None:
    print("├─────────────────────┼───────────────────────────────────────────────┤")


def print_summary(
    mem: Optional[MemoryResult],
    lat: Optional[LatencyStats],
    fps64: Optional[FpsResult],
    fps128: Optional[FpsResult],
    burst: Optional[BurstResult],
    stress: Optional[StressResult],
) -> None:
    _header("📋  README-READY SUMMARY")
    print()
    print("┌─────────────────────────────────────────────────────────────────────┐")
    print("│                    VELTIX PERFORMANCE RESULTS                       │")

    if mem:
        _tdivider()
        _trow("MEMORY", "")
        _trow("Idle server", format_bytes(int(mem.server_idle_kb * 1_024)))
        _trow("Per client", format_bytes(int(mem.client_cost_kb * 1_024)))
        _trow("50 clients total", format_bytes(int(mem.ram_50_clients_kb * 1_024)))

    if lat:
        _tdivider()
        _trow("LATENCY (local)", "")
        _trow("Average", f"{lat.avg:.3f} ms")
        _trow("P95", f"{lat.p95:.3f} ms")
        _trow("P99", f"{lat.p99:.3f} ms")
        _trow("Max", f"{lat.max:.3f} ms")

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
        _trow("Send", f"{burst.send_throughput:,.0f} msg/s")
        _trow("Receive", f"{burst.recv_throughput:,.0f} msg/s")
        _trow("Data", f"{burst.data_mbps:.2f} MB/s")

    if stress:
        _tdivider()
        _trow("CONCURRENT STRESS", "")
        _trow(
            f"{stress.num_clients} clients",
            f"{stress.throughput:,.0f} msg/s  –  {stress.success_rate:.0f}% success",
        )

    print("└─────────────────────┴───────────────────────────────────────────────┘")
    print()


# ══════════════════════════════════════════════════════════════════════════════
# JSON export
# ══════════════════════════════════════════════════════════════════════════════


def build_json(
    mem: Optional[MemoryResult],
    lat: Optional[LatencyStats],
    fps64: Optional[FpsResult],
    fps128: Optional[FpsResult],
    burst: Optional[BurstResult],
    stress: Optional[StressResult],
) -> dict:
    """Build a JSON-serializable dict from benchmark results."""
    return {
        "veltix_version": veltix.__version__,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "system": {
            "python": sys.version.split()[0],
            "cpu_logical": psutil.cpu_count(logical=True),
            "cpu_physical": psutil.cpu_count(logical=False),
            "cpu_model": platform.processor() or "unknown",
            "ram_gb": round(psutil.virtual_memory().total / 1_073_741_824, 1),
            "os": sys.platform,
            "os_version": platform.version(),
            "machine": platform.machine(),
        },
        "results": {
            "memory": mem.to_dict() if mem else None,
            "latency": lat.to_dict() if lat else None,
            "fps_64": fps64.to_dict() if fps64 else None,
            "fps_128": fps128.to_dict() if fps128 else None,
            "burst": burst.to_dict() if burst else None,
            "stress": stress.to_dict() if stress else None,
        },
    }


def save_json(data: dict, path: str) -> None:
    """Save benchmark results to a JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n  ✓ Results saved to {path}")


# ══════════════════════════════════════════════════════════════════════════════
# CLI entry point
# ══════════════════════════════════════════════════════════════════════════════

ALL_BENCHMARKS = ["memory", "latency", "fps", "burst", "stress"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Veltix benchmark suite",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--only",
        nargs="+",
        metavar="BENCH",
        choices=ALL_BENCHMARKS,
        default=ALL_BENCHMARKS,
        help="Run only the specified benchmarks",
    )
    p.add_argument(
        "--save",
        metavar="FILE",
        default=None,
        help="Save results to a JSON file (e.g. results.json)",
    )

    # Per-benchmark knobs
    p.add_argument("--latency-iterations", type=int, default=2_000, metavar="N")
    p.add_argument("--fps-players", type=int, default=64, metavar="N")
    p.add_argument("--fps-tick-rate", type=int, default=64, metavar="HZ")
    p.add_argument("--fps-duration", type=float, default=5.0, metavar="S")
    p.add_argument("--fps2-players", type=int, default=128, metavar="N")
    p.add_argument("--fps2-tick-rate", type=int, default=20, metavar="HZ")
    p.add_argument("--burst-count", type=int, default=10_000, metavar="N")
    p.add_argument("--burst-payload", type=int, default=64, metavar="BYTES")
    p.add_argument("--stress-clients", type=int, default=100, metavar="N")
    p.add_argument("--stress-msgs", type=int, default=100, metavar="N")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    run = set(args.only)

    # ── header ─────────────────────────────────────────────────────────────────
    print()
    _sep("═")
    print(f"  VELTIX BENCHMARK SUITE  –  v{veltix.__version__}")
    _sep("═")
    _row("Python", sys.version.split()[0])
    _row(
        "CPU",
        f"{psutil.cpu_count(logical=True)} logical cores  ({psutil.cpu_count(logical=False)} physical)",
    )
    _row("RAM", f"{psutil.virtual_memory().total / 1_073_741_824:.1f} GB")
    _row("OS", sys.platform)

    # ── run selected benchmarks ────────────────────────────────────────────────
    mem = bench_memory() if "memory" in run else None
    lat = bench_latency(args.latency_iterations) if "latency" in run else None
    fps64 = None
    fps128 = None
    if "fps" in run:
        fps64 = bench_fps(args.fps_players, args.fps_tick_rate, args.fps_duration)
        fps128 = bench_fps(args.fps2_players, args.fps2_tick_rate, args.fps_duration, port=20_006)
    burst = bench_burst(args.burst_count, args.burst_payload) if "burst" in run else None
    stress = bench_stress(args.stress_clients, args.stress_msgs) if "stress" in run else None

    # ── summary ────────────────────────────────────────────────────────────────
    print_summary(mem, lat, fps64, fps128, burst, stress)

    # ── JSON export ────────────────────────────────────────────────────────────
    if args.save:
        data = build_json(mem, lat, fps64, fps128, burst, stress)
        save_json(data, args.save)


if __name__ == "__main__":
    main()
