from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Optional

try:
    import psutil
except ImportError:
    raise ImportError(
        "psutil is required for the benchmark suite. Install with: pip install veltix[benchmark]"
    ) from None

import veltix
from veltix.logger.core import Logger
from veltix.logger.levels import LogLevel

from .benches import burst, fps, latency, memory, stress  # noqa: F401 - populate registry
from .benchmark import Benchmark
from .config import PORT_FPS_1, PORT_FPS_2
from .display import _B as _BOLD
from .display import _R as _RESET
from .display import print_summary, row, sep
from .export import build_json, save_json
from .runner import BenchRunner

ALL_BENCHMARKS = ["memory", "latency", "fps", "burst", "stress"]
_BENCH_NAMES = "memory latency fps burst stress"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Veltix benchmark suite",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    sub = p.add_subparsers(dest="command", metavar="")
    sub.add_parser("init", help="Initialize a .vltxbench/ project")
    p_list = sub.add_parser("list", help="List benchmarks and/or profiles")
    p_list.add_argument(
        "-b",
        "--benchmarks",
        action="store_true",
        default=False,
        help="Show benchmarks only",
    )
    p_list.add_argument(
        "-p",
        "--profiles",
        action="store_true",
        default=False,
        help="Show profiles only",
    )
    p_list.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output in JSON format",
    )
    p_info = sub.add_parser("info", help="Show details about a benchmark")
    p_info.add_argument(
        "name",
        metavar="NAME",
        choices=ALL_BENCHMARKS,
        help=f"Benchmark name. Choices: {_BENCH_NAMES}",
    )

    p.add_argument(
        "--only",
        nargs="+",
        metavar="BENCH",
        choices=ALL_BENCHMARKS,
        default=ALL_BENCHMARKS,
        help=f"Run only the specified benchmarks. Choices: {_BENCH_NAMES}",
    )
    p.add_argument(
        "--save",
        metavar="FILE",
        default=None,
        help="Save results to a JSON file (e.g. results.json)",
    )
    p.add_argument(
        "--profile",
        metavar="NAME",
        default=None,
        help="Profile name in .vltxbench/profiles/ (e.g. 'default' for default.toml)",
    )
    p.add_argument(
        "--tmp",
        action="store_true",
        default=False,
        help="Ignore .vltxbench/ configuration, use flags only",
    )
    p.add_argument(
        "--socket-core",
        choices=["threading", "async", "both"],
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

    return p


def _build_benches(args: argparse.Namespace) -> list[Benchmark]:
    """Create Benchmark instances from parsed CLI arguments."""
    benches: list[Benchmark] = []
    selected = set(args.only)

    if "memory" in selected:
        benches.append(Benchmark.get("memory")())
    if "latency" in selected:
        benches.append(Benchmark.get("latency")({"iterations": args.latency_iterations}))
    if "fps" in selected:
        benches.append(
            Benchmark.get("fps")(
                {
                    "players": args.fps_players,
                    "tick_rate": args.fps_tick_rate,
                    "duration": args.fps_duration,
                    "port": PORT_FPS_1,
                },
                name="fps_64",
            )
        )
        benches.append(
            Benchmark.get("fps")(
                {
                    "players": args.fps2_players,
                    "tick_rate": args.fps2_tick_rate,
                    "duration": args.fps_duration,
                    "port": PORT_FPS_2,
                },
                name="fps_128",
            )
        )
    if "burst" in selected:
        benches.append(
            Benchmark.get("burst")({"count": args.burst_count, "payload": args.burst_payload})
        )
    if "stress" in selected:
        benches.append(
            Benchmark.get("stress")({"clients": args.stress_clients, "msgs": args.stress_msgs})
        )
    return benches


def _print_header(
    args: argparse.Namespace,
    profile_name: str = "",
) -> None:
    print()
    sep("=")
    print(f"  {_BOLD}VELTIX BENCHMARK SUITE  -  v{veltix.__version__}{_RESET}")
    sep("=")
    row("Python", sys.version.split()[0])
    row(
        "CPU",
        f"{psutil.cpu_count(logical=True)} logical cores"
        f"  ({psutil.cpu_count(logical=False)} physical)",
    )
    row("RAM", f"{psutil.virtual_memory().total / 1_073_741_824:.1f} GB")
    row("OS", sys.platform)
    row("Socket backend", args.socket_core)
    if profile_name:
        row("Profile", profile_name)
    elif args.tmp:
        row("Config", "temporary (--tmp)")
    if args.runs > 1:
        row("Runs (avg)", str(args.runs))


def _results_map(results: dict[str, Any]) -> dict[str, Any]:
    """Map benchmark result names to ``print_summary`` variable names."""
    mapping: dict[str, str] = {
        "memory": "mem",
        "latency": "lat",
        "burst": "burst",
        "stress": "stress",
    }
    out: dict[str, Any] = {
        "mem": None,
        "lat": None,
        "fps64": None,
        "fps128": None,
        "burst": None,
        "stress": None,
    }
    for key, value in results.items():
        var = mapping.get(key, key)
        out[var] = value
    return out


def _resolve_profile(args: argparse.Namespace) -> tuple[Optional[Any], str]:
    """Load profile if applicable. Returns (Profile or None, display name)."""
    vltx_dir = Path(".vltxbench")

    if args.tmp:
        return None, ""

    if args.profile:
        from .profile import find_profile, load_profile

        profiles_dir = vltx_dir / "profiles"
        profile_path = find_profile(args.profile, profiles_dir)
        if not profile_path.exists():
            sys.exit(
                f"Profile not found: {args.profile}\n"
                f"  Looked in: {profile_path}\n"
                f"  Run 'vltxbench init' to create the default profile."
            )
        profile = load_profile(profile_path)
        return profile, args.profile

    if vltx_dir.exists():
        default = vltx_dir / "profiles" / "default.toml"
        if default.exists():
            from .profile import load_profile

            profile = load_profile(default)
            return profile, "default"

    return None, ""


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "init":
        from .init import run_init

        run_init()
        return

    if args.command == "list":
        from ._list import cmd_list

        cmd_list(
            show_benchmarks=not args.profiles,
            show_profiles=not args.benchmarks,
            as_json=args.json,
        )
        return

    if args.command == "info":
        from ._info import cmd_info

        cmd_info(args.name)
        return

    Logger.get_instance().set_level(LogLevel.ERROR)

    profile, profile_name = _resolve_profile(args)
    benches: list[Benchmark]
    runs: int = args.runs

    if profile is not None:
        benches = profile.benches
        if runs == 1:
            runs = profile.runs
    else:
        benches = _build_benches(args)

    _print_header(args, profile_name=profile_name)

    runner = BenchRunner(benches, backend=args.socket_core, runs=runs)
    results = runner.run_all()

    mapped = _results_map(results)

    print_summary(
        mapped["mem"],
        mapped["lat"],
        mapped["fps64"],
        mapped["fps128"],
        mapped["burst"],
        mapped["stress"],
    )

    if args.save:
        save_path = args.save
        vltx_dir = Path(".vltxbench")
        if vltx_dir.exists():
            saved_dir = vltx_dir / "saved"
            saved_dir.mkdir(parents=True, exist_ok=True)
            save_path = str(saved_dir / args.save)
        data = build_json(
            mapped["mem"],
            mapped["lat"],
            mapped["fps64"],
            mapped["fps128"],
            mapped["burst"],
            mapped["stress"],
        )
        save_json(data, save_path)
