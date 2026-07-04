"""
benches/fps.py
--------------
Benchmark 3 — FPS game-server simulation.

Measures:
  - Messages sent / received / lost
  - Effective throughput (msg/s) and tick accuracy (actual vs target tick rate)
  - Success rate and error count
  - RAM delta during simulation
  - Per-tick stats: avg, min, max, stdev tick duration (ms)
    (reveals scheduling jitter — a high stdev means the OS is not giving
     the process consistent time slices)
  - Tick budget compliance: % of ticks that finished within the target interval
    (a tick that overruns pushes the next one late, causing cascading lag)
  - Shoot rate: actual PLAYER_SHOOT ratio vs expected ~10%
"""

from __future__ import annotations

import gc
import statistics
import threading
import time

from veltix import Client, ClientConfig, Events, Request, Server, ServerConfig, SocketCore

from ..config import PLAYER_MOVE, PLAYER_SHOOT, PORT_FPS_1
from ..display import header, row
from ..models import FpsResult
from ..utils import incr, ram_mb


def run(
    num_players: int = 64,
    tick_rate: int = 64,
    duration_s: float = 5.0,
    port: int = PORT_FPS_1,
    socket_core: str = "async",
) -> FpsResult:
    """
    Simulates a realistic FPS server:
      - Every player sends PLAYER_MOVE each tick (32 B)
      - ~10% of players send PLAYER_SHOOT each tick (16 B)
    """
    header(f"③ FPS SERVER SIMULATION  ({num_players} players @ {tick_rate} tick/s)")

    _socket = SocketCore.THREADING if socket_core == "threading" else SocketCore.ASYNC
    recv_count = [0]
    lock = threading.Lock()

    server = Server(ServerConfig(host="127.0.0.1", port=port, socket_core=_socket))
    server.set_callback(Events.ON_RECV, lambda _c, _m: incr(recv_count, lock))
    server.start()
    time.sleep(0.5)

    # ── Connect players ───────────────────────────────────────────────────────
    clients: list[Client] = []
    print(f"  Connecting {num_players} players...", end="", flush=True)
    for _ in range(num_players):
        c = Client(ClientConfig(server_addr="127.0.0.1", port=port, retry=0, socket_core=_socket))
        c.connect()
        clients.append(c)
        time.sleep(0.005)
    time.sleep(0.5)
    print(" done")

    # Pre-resolve senders and requests outside the hot loop
    senders = [c.get_sender() for c in clients]
    req_move = [Request(PLAYER_MOVE, b"\x00" * 32) for _ in clients]
    req_shoot = [Request(PLAYER_SHOOT, b"\x00" * 16) for _ in clients]

    gc.collect()
    ram_before = ram_mb()
    tick_interval = 1.0 / tick_rate
    target_tick_ms = tick_interval * 1_000

    total_sent = errors = shoot_sent = 0
    tick_durations: list[float] = []  # ms per tick
    overrun_ticks = 0

    print(f"  Running simulation for {duration_s}s...")
    t0 = time.perf_counter()

    while time.perf_counter() - t0 < duration_s:
        tick_start = time.perf_counter()

        for i, c in enumerate(clients):
            try:
                senders[i].send(req_move[i])
                total_sent += 1
                if i % 10 == int(time.perf_counter() * 10) % 10:
                    senders[i].send(req_shoot[i])
                    total_sent += 1
                    shoot_sent += 1
            except Exception:
                errors += 1

        tick_elapsed_ms = (time.perf_counter() - tick_start) * 1_000
        tick_durations.append(tick_elapsed_ms)
        if tick_elapsed_ms > target_tick_ms:
            overrun_ticks += 1

        sleep_for = tick_interval - (tick_elapsed_ms / 1_000)
        if sleep_for > 0:
            time.sleep(sleep_for)

    actual = time.perf_counter() - t0
    time.sleep(0.5)
    gc.collect()
    ram_after = ram_mb()

    recv = recv_count[0]
    move_sent = total_sent - shoot_sent
    success = recv / total_sent * 100 if total_sent else 0.0
    msg_per_sec = total_sent / actual
    actual_tick_rate = len(tick_durations) / actual

    # ── Tick stats ────────────────────────────────────────────────────────────
    tick_avg = statistics.mean(tick_durations)
    tick_min = min(tick_durations)
    tick_max = max(tick_durations)
    tick_stdev = statistics.stdev(tick_durations) if len(tick_durations) > 1 else 0.0
    budget_pct = (1 - overrun_ticks / len(tick_durations)) * 100 if tick_durations else 0.0
    shoot_ratio = shoot_sent / move_sent * 100 if move_sent else 0.0

    # ── Display ───────────────────────────────────────────────────────────────
    row("Players", str(num_players))
    row("Target tick rate", f"{tick_rate} Hz")
    row("Actual tick rate", f"{actual_tick_rate:.1f} Hz")
    row("Duration", f"{actual:.2f} s")
    row("", "")
    row("  Messages", "")
    row("    Sent (MOVE)", f"{move_sent:,}")
    row("    Sent (SHOOT)", f"{shoot_sent:,}  ({shoot_ratio:.1f}% of MOVE)")
    row("    Sent total", f"{total_sent:,}")
    row("    Received", f"{recv:,}")
    row("    Lost", f"{total_sent - recv:,}")
    row("    Success rate", f"{success:.2f}%")
    row("    Throughput", f"{msg_per_sec:,.0f} msg/s")
    row("    Errors", str(errors))
    row("", "")
    row("  Tick duration (ms)", "")
    row("    Avg", f"{tick_avg:.3f} ms")
    row("    Min", f"{tick_min:.3f} ms")
    row("    Max", f"{tick_max:.3f} ms")
    row("    Stdev", f"{tick_stdev:.3f} ms")
    row(
        "    Budget compliance",
        f"{budget_pct:.1f}%  ({overrun_ticks} overruns / {len(tick_durations)} ticks)",
    )
    row("", "")
    row("  RAM delta", f"{ram_after - ram_before:+.2f} MB")

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
        actual_tick_rate=actual_tick_rate,
        tick_avg_ms=tick_avg,
        tick_min_ms=tick_min,
        tick_max_ms=tick_max,
        tick_stdev_ms=tick_stdev,
        tick_budget_pct=budget_pct,
        overrun_ticks=overrun_ticks,
    )
