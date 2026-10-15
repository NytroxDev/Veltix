"""
cli.py
------
Argument parsing and main entry point.
Orchestrates benchmark selection, execution, summary and JSON export.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
import time
from typing import TYPE_CHECKING, Any

import veltix
from veltix import Logger, LogLevel
from veltix.network import _rust

from . import utils
from .display import print_summary, row, sep
from .export import build_json, save_json

if TYPE_CHECKING:
    from collections.abc import Callable

ALL_BENCHMARKS = ["memory", "latency", "fps", "burst", "stress"]
BACKENDS = ["threading", "async"]


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
        help=f"Run only the specified benchmarks. Choices: {', '.join(ALL_BENCHMARKS)}",
    )
    p.add_argument(
        "--compare",
        nargs=2,
        metavar=("A", "B"),
        default=None,
        help="Compare two saved benchmark JSON result files",
    )
    p.add_argument(
        "--save",
        metavar="FILE",
        default=None,
        help="Save results to a JSON file (e.g. results.json)",
    )
    p.add_argument(
        "--socket-core",
        choices=BACKENDS + ["both"],
        default="async",
        help="Socket backend to benchmark ('threading', 'async', or 'both')",
    )
    p.add_argument(
        "--engine",
        choices=["rust", "python", "auto"],
        default="auto",
        metavar="ENGINE",
        help="Protocol engine to benchmark ('rust', 'python', or 'auto' - use the available one)",
    )
    p.add_argument(
        "--runs",
        type=int,
        default=1,
        metavar="N",
        help="Run each benchmark N times and aggregate the results",
    )
    p.add_argument(
        "--warmup",
        type=int,
        default=1,
        metavar="N",
        help="Discarded warmup passes before measuring (0 to disable)",
    )
    p.add_argument(
        "--cooldown",
        type=float,
        default=0.5,
        metavar="S",
        help="Seconds to wait between measured runs",
    )
    p.add_argument(
        "--pin",
        type=int,
        default=None,
        metavar="N",
        help="Restrict the benchmark process to the first N logical CPUs (best-effort)",
    )

    # ── Per-benchmark knobs ───────────────────────────────────────────────────
    g = p.add_argument_group("latency")
    g.add_argument("--latency-iterations", type=int, default=50_000, metavar="N")

    g = p.add_argument_group("fps")
    g.add_argument("--fps-players", type=int, default=64, metavar="N")
    g.add_argument("--fps-tick-rate", type=int, default=64, metavar="HZ")
    g.add_argument("--fps-duration", type=float, default=5.0, metavar="S")

    g = p.add_argument_group("burst")
    g.add_argument("--burst-count", type=int, default=10_000, metavar="N")
    g.add_argument("--burst-payload", type=int, default=64, metavar="BYTES")

    g = p.add_argument_group("stress")
    g.add_argument("--stress-clients", type=int, default=100, metavar="N")
    g.add_argument("--stress-msgs", type=int, default=100, metavar="N")

    return p.parse_args()


def _backends_from_args(socket_core: str) -> list[str]:
    if socket_core == "both":
        return BACKENDS
    return [socket_core]


def _apply_engine(engine: str) -> str:
    """Force the requested protocol engine and return its effective name.

    The engine decision is cached at ``veltix.network._rust`` import time, so
    the module is reloaded after adjusting the environment.

    Args:
        engine: "rust", "python" or "auto".

    Returns:
        "rust" when the compiled engine is active, "python" otherwise.
    """
    if engine == "python":
        os.environ["VELTIX_DISABLE_RUST"] = "1"
        importlib.reload(_rust)
    elif engine == "rust":
        os.environ.pop("VELTIX_DISABLE_RUST", None)
        importlib.reload(_rust)
    return _rust.engine_name()


def _run_for_backends(
    runner: Any,
    backends: list[str],
    step_counter: list[int],
    bench_name: str,
    *args: Any,
    warmup: bool = False,
) -> list[Any]:
    results = []
    for backend in backends:
        if warmup:
            step_label = f"warmup {bench_name} ({backend})"
        else:
            step_counter[0] += 1
            step_label = f"[{step_counter[0]}/{step_counter[1]}] {bench_name} ({backend})"
        result = runner(*args, socket_core=backend, step_label=step_label)
        result.backend = backend
        results.append(result)
    return results


def _run_runs(
    runner: Any,
    backends: list[str],
    runs: int,
    step_counter: list[int],
    bench_name: str,
    *args: Any,
    warmup: int = 0,
    cooldown: float = 0.0,
    sleep: Callable[[float], None] = time.sleep,
) -> list[Any]:
    """Run a bench across backends and aggregate N runs per backend.

    A discarded warmup pass runs first so cache/page-fault/TCP-window effects
    settle, and each measured run alternates the backend order so a monotonic
    drift (thermal, background load) cannot systematically favour one backend.
    Per-backend results are collected by name before aggregation.

    Args:
        runner: Benchmark callable, invoked with ``socket_core`` and
            ``step_label`` keywords plus any extra positional ``args``.
        backends: Backends to benchmark, in canonical order.
        runs: Number of measured runs per backend.
        step_counter: Mutable ``[current, total]`` progress counter.
        bench_name: Benchmark name for the progress label.
        *args: Extra positional arguments forwarded to ``runner``.
        warmup: Number of discarded warmup passes.
        cooldown: Seconds to wait between measured runs.
        sleep: Sleep implementation (injectable for tests).

    Returns:
        One result per backend: the raw result when ``runs <= 1``, otherwise
        the aggregated result.
    """
    for _ in range(warmup):
        _run_for_backends(runner, backends, step_counter, bench_name, *args, warmup=True)

    if runs <= 1:
        return _run_for_backends(runner, backends, step_counter, bench_name, *args)

    per_backend: dict[str, list[Any]] = {backend: [] for backend in backends}
    for run_idx in range(runs):
        if run_idx and cooldown > 0:
            sleep(cooldown)
        order = backends if run_idx % 2 == 0 else list(reversed(backends))
        for backend in order:
            step_counter[0] += 1
            step_label = f"[{step_counter[0]}/{step_counter[1]}] {bench_name} ({backend})"
            result = runner(*args, socket_core=backend, step_label=step_label)
            result.backend = backend
            per_backend[backend].append(result)

    return [per_backend[backend][0].aggregate(per_backend[backend]) for backend in backends]


def main() -> None:
    try:
        _main_impl()
    except KeyboardInterrupt:
        from .utils import cleanup

        cleanup()
        print("\n  Interrupted - cleaned up benchmark servers", file=sys.stderr)
        sys.exit(130)


def _main_impl() -> None:
    try:
        import psutil  # type: ignore[import-untyped]
    except ImportError:
        print("psutil is required for benchmarks.\nInstall it with:  pip install veltix[benchmark]")
        sys.exit(1)

    Logger.get_instance().set_level(LogLevel.ERROR)

    args = parse_args()

    if args.compare:
        from .compare import cmd_compare

        cmd_compare(args.compare[0], args.compare[1])
        return

    run = set(args.only)
    backends = _backends_from_args(args.socket_core)

    engine_name = _apply_engine(args.engine)
    if args.engine == "rust" and engine_name != "rust":
        print(
            "Rust engine requested but unavailable (compiled veltix._rust extension not installed)."
        )
        sys.exit(1)

    pinned_cpus = utils.pin_to_cpus(args.pin) if args.pin is not None else None

    # ── Suite header ──────────────────────────────────────────────────────────
    print()
    sep("═")
    print(f"  VELTIX BENCHMARK SUITE  -  v{veltix.__version__}")
    sep("═")
    row("Python", sys.version.split()[0])
    engine_label = "rust (compiled)" if engine_name == "rust" else "python (pure)"
    row("Engine", engine_label)
    row(
        "CPU",
        f"{psutil.cpu_count(logical=True)} logical cores"
        f"  ({psutil.cpu_count(logical=False)} physical)",
    )
    row("RAM", f"{psutil.virtual_memory().total / 1_073_741_824:.1f} GB")
    row("OS", sys.platform)
    row("CPU governor", utils.cpu_governor() or "n/a")
    load = utils.load_average()
    row("Load average", " / ".join(f"{value:.2f}" for value in load) if load else "n/a")
    if args.pin is None:
        row("CPU pinning", "off")
    elif pinned_cpus:
        row("CPU pinning", f"{len(pinned_cpus)} CPU(s), first={pinned_cpus[0]}")
    else:
        row("CPU pinning", "requested but unsupported on this platform")
    row("Socket backend", args.socket_core)
    row("Runs (n)", str(args.runs))
    row("Warmup", f"{args.warmup} discarded pass(es)")
    row("Cooldown", f"{args.cooldown:g} s between runs")
    row("Aggregation", "median across runs (IQR + 95% CI)" if args.runs > 1 else "single run")

    # ── Step counter ────────────────────────────────────────────────────────────
    selected_benches = [b for b in ["memory", "latency", "fps", "burst", "stress"] if b in run]
    total_steps = len(selected_benches) * len(backends) * args.runs
    step_counter: list[int] = [0, total_steps]

    # ── Run selected benchmarks ───────────────────────────────────────────────
    mem = lat = fps = burst = stress = None

    if "memory" in run:
        from .benches.memory import run as run_memory

        mem = _run_runs(
            run_memory,
            backends,
            args.runs,
            step_counter,
            "memory",
            warmup=args.warmup,
            cooldown=args.cooldown,
        )

    if "latency" in run:
        from .benches.latency import run as run_latency

        lat = _run_runs(
            run_latency,
            backends,
            args.runs,
            step_counter,
            "latency",
            args.latency_iterations,
            warmup=args.warmup,
            cooldown=args.cooldown,
        )

    if "fps" in run:
        from .benches.fps import run as run_fps
        from .config import PORT_FPS

        fps = _run_runs(
            run_fps,
            backends,
            args.runs,
            step_counter,
            "fps",
            args.fps_players,
            args.fps_tick_rate,
            args.fps_duration,
            PORT_FPS,
            warmup=args.warmup,
            cooldown=args.cooldown,
        )

    if "burst" in run:
        from .benches.burst import run as run_burst

        burst = _run_runs(
            run_burst,
            backends,
            args.runs,
            step_counter,
            "burst",
            args.burst_count,
            args.burst_payload,
            warmup=args.warmup,
            cooldown=args.cooldown,
        )

    if "stress" in run:
        from .benches.stress import run as run_stress

        stress = _run_runs(
            run_stress,
            backends,
            args.runs,
            step_counter,
            "stress",
            args.stress_clients,
            args.stress_msgs,
            warmup=args.warmup,
            cooldown=args.cooldown,
        )

    # ── Summary + export ──────────────────────────────────────────────────────
    print_summary(mem, lat, fps, burst, stress)

    if args.save:
        data = build_json(
            mem,
            lat,
            fps,
            burst,
            stress,
            harness={
                "runs": args.runs,
                "warmup": args.warmup,
                "cooldown": args.cooldown,
                "socket_backend": args.socket_core,
                "backends": backends,
                "pin_requested": args.pin,
                "affinity": utils.process_affinity(),
            },
        )
        save_json(data, args.save)
