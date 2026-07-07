from __future__ import annotations

import gc
import statistics
import threading
import time

from veltix import Client, ClientConfig, Events, Request, Server, ServerConfig, SocketCore

from ..benchmark import Benchmark
from ..config import PLAYER_MOVE, PORT_BURST
from ..display import header, row
from ..models import BurstResult
from ..utils import append_ts


class BurstBench(Benchmark):
    name = "burst"
    description = "Burst throughput measurement"
    parameters = {
        "count": {
            "type": "int",
            "default": 10_000,
            "description": "Number of messages to send",
        },
        "payload": {
            "type": "int",
            "default": 64,
            "description": "Payload size in bytes",
        },
    }
    outputs = [
        "send throughput (msg/s)",
        "receive throughput (msg/s)",
        "data throughput (MB/s)",
        "success rate",
        "pipeline drain (P50/P95/P99/max)",
        "receive inter-arrival jitter",
    ]

    def run(self, backend: SocketCore) -> BurstResult:
        port = self.config.get("port", PORT_BURST)
        count = self.config.get("count", 10_000)
        payload = self.config.get("payload", 64)
        return _run_burst(
            count=count,
            payload_size=payload,
            port=port,
            socket_core=backend.name.lower(),
            step_label=self._step_label,
        )


def run(
    count: int = 10_000,
    payload_size: int = 64,
    port: int = PORT_BURST,
    socket_core: str = "async",
) -> BurstResult:
    return _run_burst(count=count, payload_size=payload_size, port=port, socket_core=socket_core)


def _run_burst(
    count: int,
    payload_size: int,
    port: int,
    socket_core: str,
    step_label: str = "",
) -> BurstResult:
    header(f"BURST THROUGHPUT  ({count:,} msgs x {payload_size} B)", prefix=step_label)

    _socket = SocketCore.THREADING if socket_core == "threading" else SocketCore.ASYNC
    received_ts: list[float] = []
    lock = threading.Lock()

    server = Server(ServerConfig(host="127.0.0.1", port=port, socket_core=_socket))
    server.set_callback(
        Events.ON_RECV,
        lambda _c, _m: append_ts(received_ts, lock),
    )
    server.start()
    time.sleep(0.3)

    client = Client(ClientConfig(server_addr="127.0.0.1", port=port, retry=0, socket_core=_socket))
    client.connect()
    time.sleep(0.2)

    try:
        payload = b"X" * payload_size
        sender = client.sender
        request = Request(PLAYER_MOVE, payload)
        gc.collect()

        t0 = time.perf_counter()
        for _ in range(count):
            sender.send(request)
        send_done = time.perf_counter()
        send_duration = send_done - t0

        deadline = time.perf_counter() + 10.0
        while len(received_ts) < count and time.perf_counter() < deadline:
            time.sleep(0.05)
        total_elapsed = time.perf_counter() - t0

        recv_count = len(received_ts)
        send_throughput = count / send_duration
        recv_throughput = recv_count / total_elapsed
        data_mbps = (recv_count * payload_size) / total_elapsed / 1_048_576
        success = recv_count / count * 100

        drain_latencies_ms: list[float] = []
        if received_ts:
            sorted_ts = sorted(received_ts)
            drain_latencies_ms = [(ts - t0) * 1_000 for ts in sorted_ts]

        def _pct(data: list[float], p: float) -> float:
            if not data:
                return 0.0
            s = sorted(data)
            return s[int(len(s) * p / 100)]

        lat_p50 = _pct(drain_latencies_ms, 50)
        lat_p95 = _pct(drain_latencies_ms, 95)
        lat_p99 = _pct(drain_latencies_ms, 99)
        lat_max = max(drain_latencies_ms) if drain_latencies_ms else 0.0

        if len(received_ts) >= 2:
            sorted_ts = sorted(received_ts)
            gaps_ms = [(sorted_ts[i] - sorted_ts[i - 1]) * 1_000 for i in range(1, len(sorted_ts))]
            recv_jitter = statistics.stdev(gaps_ms) if len(gaps_ms) > 1 else 0.0
            recv_gap_avg = statistics.mean(gaps_ms)
        else:
            recv_jitter = 0.0
            recv_gap_avg = 0.0

        row("Messages", str(count))
        row("Payload size", f"{payload_size} B")
        row("", "")
        row("  Throughput", "")
        row("    Send", f"{send_throughput:,.0f} msg/s  ({send_duration * 1_000:.1f} ms total)")
        row("    Receive", f"{recv_throughput:,.0f} msg/s")
        row("    Data", f"{data_mbps:.3f} MB/s")
        row("    Success rate", f"{success:.2f}%  ({recv_count:,} / {count:,})")
        row("    Lost", f"{count - recv_count:,}")
        row("    Total duration", f"{total_elapsed * 1_000:.1f} ms")
        row("", "")
        row("  Pipeline drain (time from t0 to recv, ms)", "")
        row("    P50", f"{lat_p50:.1f} ms")
        row("    P95", f"{lat_p95:.1f} ms")
        row("    P99", f"{lat_p99:.1f} ms")
        row("    Max", f"{lat_max:.1f} ms")
        row("", "")
        row("  Receive inter-arrival", "")
        row("    Avg gap", f"{recv_gap_avg:.3f} ms")
        row("    Jitter (stdev)", f"{recv_jitter:.3f} ms")
    finally:
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
        send_duration_s=send_duration,
        drain_p50_ms=lat_p50,
        drain_p95_ms=lat_p95,
        drain_p99_ms=lat_p99,
        drain_max_ms=lat_max,
        drain_jitter_ms=recv_jitter,
        recv_gap_avg_ms=recv_gap_avg,
    )
