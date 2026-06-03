"""
cli.py
------
Argument parsing and main entry point.
Orchestrates benchmark selection, execution, summary and JSON export.
"""

from __future__ import annotations

import argparse
import sys

try:
    import psutil
except ImportError:
    raise ImportError(
        "psutil est requis pour le benchmark. Installez-le avec : pip install veltix[benchmark]"
    ) from None

import veltix

from .display import header, print_summary, row, sep
from .export import build_json, save_json

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
        help=f"Run only the specified benchmarks. Choices: {', '.join(ALL_BENCHMARKS)}",
    )
    p.add_argument(
        "--save",
        metavar="FILE",
        default=None,
        help="Save results to a JSON file (e.g. results.json)",
    )

    # ── Per-benchmark knobs ───────────────────────────────────────────────────
    g = p.add_argument_group("latency")
    g.add_argument("--latency-iterations", type=int, default=2_000, metavar="N")

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


def main() -> None:
    args = parse_args()
    run = set(args.only)

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

    # ── Run selected benchmarks ───────────────────────────────────────────────
    mem = lat = fps64 = fps128 = burst = stress = None

    if "memory" in run:
        from .benches.memory import run as run_memory

        mem = run_memory()

    if "latency" in run:
        from .benches.latency import run as run_latency

        lat = run_latency(args.latency_iterations)

    if "fps" in run:
        from .benches.fps import run as run_fps
        from .config import PORT_FPS_1, PORT_FPS_2

        fps64 = run_fps(args.fps_players, args.fps_tick_rate, args.fps_duration, PORT_FPS_1)
        fps128 = run_fps(args.fps2_players, args.fps2_tick_rate, args.fps_duration, PORT_FPS_2)

    if "burst" in run:
        from .benches.burst import run as run_burst

        burst = run_burst(args.burst_count, args.burst_payload)

    if "stress" in run:
        from .benches.stress import run as run_stress

        stress = run_stress(args.stress_clients, args.stress_msgs)

    # ── Summary + export ──────────────────────────────────────────────────────
    print_summary(mem, lat, fps64, fps128, burst, stress)

    if args.save:
        data = build_json(mem, lat, fps64, fps128, burst, stress)
        save_json(data, args.save)
