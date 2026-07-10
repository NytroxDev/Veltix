"""
cli.py
------
Argument parsing and main entry point.
Orchestrates benchmark selection, execution, summary and JSON export.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import veltix
from veltix import Logger, LogLevel

from .display import print_summary, row, sep
from .export import build_json, save_json

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
        "--runs",
        type=int,
        default=1,
        metavar="N",
        help="Run each benchmark N times and average the results",
    )

    # ── Per-benchmark knobs ───────────────────────────────────────────────────
    g = p.add_argument_group("latency")
    g.add_argument("--latency-iterations", type=int, default=50_000, metavar="N")

    g = p.add_argument_group("fps (run 1)")
    g.add_argument("--fps-players", type=int, default=64, metavar="N")
    g.add_argument("--fps-tick-rate", type=int, default=64, metavar="HZ")
    g.add_argument("--fps-duration", type=float, default=5.0, metavar="S")

    g = p.add_argument_group("fps (run 2)")
    g.add_argument("--fps2-players", type=int, default=128, metavar="N")
    g.add_argument("--fps2-tick-rate", type=int, default=20, metavar="HZ")

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


def _run_for_backends(
    runner: Any,
    backends: list[str],
    step_counter: list[int],
    bench_name: str,
    *args: Any,
) -> list[Any]:
    results = []
    for backend in backends:
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
) -> list[Any]:
    """Run a bench across backends, averaging over N runs."""
    if runs <= 1:
        return _run_for_backends(runner, backends, step_counter, bench_name, *args)

    all_backend_results: list[list] = []
    for _run_idx in range(runs):
        all_backend_results.append(
            _run_for_backends(runner, backends, step_counter, bench_name, *args)
        )

    num_backends = len(all_backend_results[0])
    averaged = []
    for b_idx in range(num_backends):
        run_specific = [run[b_idx] for run in all_backend_results]
        avg = run_specific[0].average(run_specific)
        averaged.append(avg)
    return averaged


def main() -> None:
    try:
        import psutil  # type: ignore[import-untyped]  # noqa: F401
    except ImportError:
        print(
            "psutil is required for benchmarks.\n"
            "Install it with:  pip install veltix[bench]"
        )
        sys.exit(1)

    Logger.get_instance().set_level(LogLevel.ERROR)

    args = parse_args()

    if args.compare:
        from .compare import cmd_compare

        cmd_compare(args.compare[0], args.compare[1])
        return

    run = set(args.only)
    backends = _backends_from_args(args.socket_core)

    # ── Suite header ──────────────────────────────────────────────────────────
    print()
    sep("═")
    print(f"  VELTIX BENCHMARK SUITE  –  v{veltix.__version__}")
    sep("═")
    row("Python", sys.version.split()[0])
    row(
        "CPU",
        f"{psutil.cpu_count(logical=True)} logical cores"
        f"  ({psutil.cpu_count(logical=False)} physical)",
    )
    row("RAM", f"{psutil.virtual_memory().total / 1_073_741_824:.1f} GB")
    row("OS", sys.platform)
    row("Socket backend", args.socket_core)
    if args.runs > 1:
        row("Runs (avg)", str(args.runs))

    # ── Step counter ────────────────────────────────────────────────────────────
    selected_benches = [b for b in ["memory", "latency", "fps", "burst", "stress"] if b in run]
    total_steps = len(selected_benches) * len(backends) * args.runs
    step_counter: list[int] = [0, total_steps]

    # ── Run selected benchmarks ───────────────────────────────────────────────
    mem = lat = fps64 = fps128 = burst = stress = None

    if "memory" in run:
        from .benches.memory import run as run_memory

        mem = _run_runs(run_memory, backends, args.runs, step_counter, "memory")

    if "latency" in run:
        from .benches.latency import run as run_latency

        lat = _run_runs(
            run_latency, backends, args.runs, step_counter, "latency", args.latency_iterations
        )

    if "fps" in run:
        from .benches.fps import run as run_fps
        from .config import PORT_FPS_1, PORT_FPS_2

        fps64 = _run_runs(
            run_fps,
            backends,
            args.runs,
            step_counter,
            "fps",
            args.fps_players,
            args.fps_tick_rate,
            args.fps_duration,
            PORT_FPS_1,
        )
        fps128 = _run_runs(
            run_fps,
            backends,
            args.runs,
            step_counter,
            "fps",
            args.fps2_players,
            args.fps2_tick_rate,
            args.fps_duration,
            PORT_FPS_2,
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
        )

    # ── Summary + export ──────────────────────────────────────────────────────
    print_summary(mem, lat, fps64, fps128, burst, stress)

    if args.save:
        data = build_json(mem, lat, fps64, fps128, burst, stress)
        save_json(data, args.save)
