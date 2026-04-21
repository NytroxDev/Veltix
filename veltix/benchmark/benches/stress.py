"""
benches/stress.py
-----------------
Benchmark 5 — Concurrent stress.

Measures:
  - Total sent / received / lost
  - Success rate and overall throughput (msg/s)
  - RAM delta
  - Per-client throughput: avg, min, max, stdev
    (reveals hot/cold spots — if stdev is high, some clients are being
     starved while others blast through)
  - Thread pool saturation: time from last future submitted to all futures
    resolved (measures executor overhead under full concurrency)
  - Drain time: how long after all sends until the last message arrives
    (measures server-side queue depth under burst load)
  - Time-to-first-receive: latency from t0 until the very first message
    lands on the server (cold-start overhead)
"""

from __future__ import annotations

import gc
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from veltix import Client, ClientConfig, Events, Request, Server, ServerConfig

from ..config import PLAYER_MOVE, PORT_STRESS
from ..display import header, row
from ..models import StressResult
from ..utils import incr, ram_mb


def run(
    num_clients: int = 100,
    msgs_per_client: int = 100,
    port: int = PORT_STRESS,
) -> StressResult:
    header(f"⑤ CONCURRENT STRESS  ({num_clients} clients × {msgs_per_client} msgs)")

    recv_count = [0]
    first_recv_ts: list[float] = []
    last_recv_ts: list[float] = []
    lock = threading.Lock()

    def on_recv(_c, _m) -> None:
        incr(recv_count, lock)
        ts = time.perf_counter()
        with lock:
            if not first_recv_ts:
                first_recv_ts.append(ts)
            last_recv_ts.clear()
            last_recv_ts.append(ts)

    server = Server(ServerConfig(host="127.0.0.1", port=port))
    server.set_callback(Events.ON_RECV, on_recv)
    server.start()
    time.sleep(0.5)

    # ── Connect clients ───────────────────────────────────────────────────────
    clients: list[Client] = []
    print(f"  Connecting {num_clients} clients...", end="", flush=True)
    for _ in range(num_clients):
        c = Client(ClientConfig(server_addr="127.0.0.1", port=port, retry=0))
        c.connect()
        clients.append(c)
        time.sleep(0.003)
    time.sleep(0.5)
    print(" done")

    total_msgs = num_clients * msgs_per_client
    gc.collect()
    ram_before = ram_mb()

    # ── Per-client send tracking ──────────────────────────────────────────────
    client_send_times: list[float] = [0.0] * num_clients

    senders = [c.get_sender() for c in clients]
    req_move = Request(PLAYER_MOVE, b"\x00" * 32)  # shared immutable request

    def _blast(idx: int, c: Client) -> None:
        t = time.perf_counter()
        s = senders[idx]
        for _ in range(msgs_per_client):
            s.send(req_move)
        client_send_times[idx] = time.perf_counter() - t

    # ── Fire ──────────────────────────────────────────────────────────────────
    print(f"  Firing {total_msgs:,} messages simultaneously...")
    t0 = time.perf_counter()

    with ThreadPoolExecutor(max_workers=num_clients) as pool:
        futures = [pool.submit(_blast, i, c) for i, c in enumerate(clients)]
        for f in futures:
            f.result()

    sends_done_ts = time.perf_counter()

    # ── Wait for all messages to arrive (up to 15 s) ──────────────────────────
    deadline = time.perf_counter() + 15.0
    while recv_count[0] < total_msgs and time.perf_counter() < deadline:
        time.sleep(0.05)

    elapsed = time.perf_counter() - t0
    gc.collect()
    ram_after = ram_mb()

    recv = recv_count[0]
    success = recv / total_msgs * 100
    throughput = recv / elapsed

    # ── Derived stats ─────────────────────────────────────────────────────────
    send_phase_duration = sends_done_ts - t0
    drain_time = elapsed - send_phase_duration

    ttfr = (first_recv_ts[0] - t0) * 1_000 if first_recv_ts else 0.0
    last_recv_offset = (last_recv_ts[0] - t0) * 1_000 if last_recv_ts else 0.0

    per_client_tps = [msgs_per_client / t for t in client_send_times if t > 0]
    ct_avg = statistics.mean(per_client_tps) if per_client_tps else 0.0
    ct_min = min(per_client_tps) if per_client_tps else 0.0
    ct_max = max(per_client_tps) if per_client_tps else 0.0
    ct_stdev = statistics.stdev(per_client_tps) if len(per_client_tps) > 1 else 0.0

    # ── Display ───────────────────────────────────────────────────────────────
    row("Clients", str(num_clients))
    row("Messages / client", str(msgs_per_client))
    row("Total messages", f"{total_msgs:,}")
    row("", "")
    row("  Results", "")
    row("    Received", f"{recv:,}")
    row("    Lost", f"{total_msgs - recv:,}")
    row("    Success rate", f"{success:.2f}%")
    row("    Throughput", f"{throughput:,.0f} msg/s")
    row("    Total duration", f"{elapsed * 1_000:.1f} ms")
    row("", "")
    row("  Timing breakdown", "")
    row("    Send phase", f"{send_phase_duration * 1_000:.1f} ms")
    row("    Drain time", f"{drain_time * 1_000:.1f} ms  (server queue after sends)")
    row("    Time-to-first-recv", f"{ttfr:.1f} ms")
    row("    Last recv at", f"{last_recv_offset:.1f} ms")
    row("", "")
    row("  Per-client send throughput (msg/s)", "")
    row("    Avg", f"{ct_avg:,.0f}")
    row("    Min", f"{ct_min:,.0f}")
    row("    Max", f"{ct_max:,.0f}")
    row(
        "    Stdev",
        f"{ct_stdev:,.0f}  {'✓ balanced' if ct_stdev / ct_avg < 0.2 else '⚠ uneven'}"
        if ct_avg
        else "n/a",
    )
    row("", "")
    row("  RAM delta", f"{ram_after - ram_before:+.2f} MB")

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
        send_phase_s=send_phase_duration,
        drain_time_s=drain_time,
        time_to_first_recv_ms=ttfr,
        per_client_tps_avg=ct_avg,
        per_client_tps_min=ct_min,
        per_client_tps_max=ct_max,
        per_client_tps_stdev=ct_stdev,
    )
