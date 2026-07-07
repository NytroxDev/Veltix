from __future__ import annotations

import gc
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from veltix import Client, ClientConfig, Events, Request, Server, ServerConfig, SocketCore

from ..benchmark import Benchmark
from ..config import PLAYER_MOVE, PORT_STRESS
from ..display import header, row
from ..models import StressResult
from ..utils import incr, ram_mb


class StressBench(Benchmark):
    name = "stress"
    description = "Concurrent stress test"
    parameters = {
        "clients": {
            "type": "int",
            "default": 100,
            "description": "Number of concurrent clients",
        },
        "msgs": {
            "type": "int",
            "default": 100,
            "description": "Messages per client",
        },
    }
    outputs = [
        "received / lost",
        "success rate",
        "throughput (msg/s)",
        "send phase / drain time",
        "time-to-first-recv",
        "per-client send throughput (avg/min/max/stdev)",
        "RAM delta",
    ]

    def run(self, backend: SocketCore) -> StressResult:
        port = self.config.get("port", PORT_STRESS)
        clients = self.config.get("clients", 100)
        msgs = self.config.get("msgs", 100)
        return _run_stress(
            num_clients=clients,
            msgs_per_client=msgs,
            port=port,
            socket_core=backend.name.lower(),
            step_label=self._step_label,
        )


def run(
    num_clients: int = 100,
    msgs_per_client: int = 100,
    port: int = PORT_STRESS,
    socket_core: str = "async",
) -> StressResult:
    return _run_stress(
        num_clients=num_clients,
        msgs_per_client=msgs_per_client,
        port=port,
        socket_core=socket_core,
    )


def _run_stress(
    num_clients: int,
    msgs_per_client: int,
    port: int,
    socket_core: str,
    step_label: str = "",
) -> StressResult:
    header(
        f"CONCURRENT STRESS  ({num_clients} clients x {msgs_per_client} msgs)", prefix=step_label
    )

    _socket = SocketCore.THREADING if socket_core == "threading" else SocketCore.ASYNC
    recv_count = [0]
    first_recv_ts: list[float] = []
    last_recv_ts: list[float] = []
    lock = threading.Lock()

    def on_recv(_c: Any, _m: Any) -> None:
        incr(recv_count, lock)
        ts = time.perf_counter()
        with lock:
            if not first_recv_ts:
                first_recv_ts.append(ts)
            last_recv_ts.clear()
            last_recv_ts.append(ts)

    server = Server(ServerConfig(host="127.0.0.1", port=port, socket_core=_socket))
    server.set_callback(Events.ON_RECV, on_recv)
    server.start()
    time.sleep(0.5)

    clients: list[Client] = []
    try:
        print(f"  Connecting {num_clients} clients...", end="", flush=True)
        for _ in range(num_clients):
            c = Client(
                ClientConfig(server_addr="127.0.0.1", port=port, retry=0, socket_core=_socket)
            )
            c.connect()
            clients.append(c)
            time.sleep(0.003)
        time.sleep(0.5)
        print(" done")

        total_msgs = num_clients * msgs_per_client
        gc.collect()
        ram_before = ram_mb()

        client_send_times: list[float] = [0.0] * num_clients

        senders = [c.sender for c in clients]
        req_move = Request(PLAYER_MOVE, b"\x00" * 32)

        def _blast(idx: int, c: Client) -> None:
            t = time.perf_counter()
            s = senders[idx]
            for _ in range(msgs_per_client):
                s.send(req_move)
            client_send_times[idx] = time.perf_counter() - t

        print(f"  Firing {total_msgs:,} messages simultaneously...")
        t0 = time.perf_counter()

        with ThreadPoolExecutor(max_workers=num_clients) as pool:
            futures = [pool.submit(_blast, i, c) for i, c in enumerate(clients)]
            for f in futures:
                f.result()

        sends_done_ts = time.perf_counter()

        deadline = time.perf_counter() + 15.0
        while recv_count[0] < total_msgs and time.perf_counter() < deadline:
            time.sleep(0.05)

        elapsed = time.perf_counter() - t0
        gc.collect()
        ram_after = ram_mb()

        recv = recv_count[0]
        success = recv / total_msgs * 100
        throughput = recv / elapsed

        send_phase_duration = sends_done_ts - t0
        drain_time = elapsed - send_phase_duration

        ttfr = (first_recv_ts[0] - t0) * 1_000 if first_recv_ts else 0.0
        last_recv_offset = (last_recv_ts[0] - t0) * 1_000 if last_recv_ts else 0.0

        per_client_tps = [msgs_per_client / t for t in client_send_times if t > 0]
        ct_avg = statistics.mean(per_client_tps) if per_client_tps else 0.0
        ct_min = min(per_client_tps) if per_client_tps else 0.0
        ct_max = max(per_client_tps) if per_client_tps else 0.0
        ct_stdev = statistics.stdev(per_client_tps) if len(per_client_tps) > 1 else 0.0

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
            f"{ct_stdev:,.0f}  {'balanced' if ct_stdev / ct_avg < 0.2 else 'uneven'}"
            if ct_avg
            else "n/a",
        )
        row("", "")
        row("  RAM delta", f"{ram_after - ram_before:+.2f} MB")
    finally:
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
