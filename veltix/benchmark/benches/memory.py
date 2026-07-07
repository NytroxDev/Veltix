from __future__ import annotations

import gc
import statistics
import time
from typing import Any, Dict, Optional

from veltix import Client, ClientConfig, Server, ServerConfig, SocketCore, format_bytes

from ..benchmark import Benchmark
from ..config import PORT_MEMORY
from ..display import header, row
from ..models import MemoryResult
from ..utils import ram_kb


class MemoryBench(Benchmark):
    name = "memory"
    description = "Baseline memory footprint"

    def run(self, backend: SocketCore) -> MemoryResult:
        port = self.config.get("port", PORT_MEMORY)
        return _run_memory(port=port, socket_core=backend.name.lower())


def run(port: int = PORT_MEMORY, socket_core: str = "async") -> MemoryResult:
    return _run_memory(port=port, socket_core=socket_core)


def _run_memory(port: int, socket_core: str) -> MemoryResult:
    header("\u2460 BASELINE MEMORY FOOTPRINT")

    gc.collect()
    baseline = ram_kb()
    row("Python process baseline", format_bytes(int(baseline * 1_024)))

    _socket = SocketCore.THREADING if socket_core == "threading" else SocketCore.ASYNC
    server = Server(ServerConfig(host="127.0.0.1", port=port, socket_core=_socket))
    server.start()
    time.sleep(0.3)
    gc.collect()
    server_ram = ram_kb()
    server_cost = server_ram - baseline
    row(
        "Idle server (0 clients)",
        f"{format_bytes(int(server_ram * 1_024))}  (+{format_bytes(int(server_cost * 1_024))})",
    )

    clients: list[Client] = []
    costs: list[float] = []

    for _ in range(10):
        gc.collect()
        before = ram_kb()
        c = Client(ClientConfig(server_addr="127.0.0.1", port=port, retry=0, socket_core=_socket))
        c.connect()
        time.sleep(0.05)
        gc.collect()
        costs.append(ram_kb() - before)
        clients.append(c)

    ram_10 = ram_kb()

    cost_avg = statistics.mean(costs)
    cost_min = min(costs)
    cost_max = max(costs)
    cost_median = statistics.median(costs)
    cost_stdev = statistics.stdev(costs) if len(costs) > 1 else 0.0

    row("Cost per client -- avg", format_bytes(int(cost_avg * 1_024)))
    row("Cost per client -- min", format_bytes(int(cost_min * 1_024)))
    row("Cost per client -- max", format_bytes(int(cost_max * 1_024)))
    row("Cost per client -- median", format_bytes(int(cost_median * 1_024)))
    row("Cost per client -- stdev", format_bytes(int(cost_stdev * 1_024)))
    row("Server + 10 clients", format_bytes(int(ram_10 * 1_024)))

    for _ in range(40):
        c = Client(ClientConfig(server_addr="127.0.0.1", port=port, retry=0, socket_core=_socket))
        c.connect()
        time.sleep(0.01)
        clients.append(c)

    time.sleep(0.5)
    gc.collect()
    ram_50 = ram_kb()
    row("Server + 50 clients", format_bytes(int(ram_50 * 1_024)))

    scale_cost = (ram_50 - ram_10) / 40
    row("Cost per client (10->50 avg)", format_bytes(int(scale_cost * 1_024)))

    for c in clients:
        c.disconnect()
    server.close_all()
    time.sleep(0.5)
    gc.collect()

    ram_after = ram_kb()
    leak = ram_after - baseline
    row(
        "RSS after full teardown",
        f"{format_bytes(int(ram_after * 1_024))}  (leak delta: {'' if leak >= 0 else '-'}{format_bytes(int(abs(leak) * 1_024))}{'  V' if abs(leak) < 512 else '  possible leak'})",
    )

    return MemoryResult(
        baseline_kb=baseline,
        server_idle_kb=server_cost,
        client_cost_kb=cost_avg,
        client_cost_min_kb=cost_min,
        client_cost_max_kb=cost_max,
        client_cost_median_kb=cost_median,
        client_cost_stdev_kb=cost_stdev,
        ram_10_clients_kb=ram_10,
        ram_50_clients_kb=ram_50,
        ram_after_teardown_kb=ram_after,
        leak_kb=leak,
    )
