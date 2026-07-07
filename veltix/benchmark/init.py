from __future__ import annotations

import sys
from pathlib import Path

# ── ANSI helpers (auto-disabled when not a terminal) ─────────────────────────

_USE_COLOR = sys.stdout.isatty()

_G = "\033[32m" if _USE_COLOR else ""   # green
_D = "\033[2m" if _USE_COLOR else ""    # dim
_B = "\033[1m" if _USE_COLOR else ""    # bold
_R = "\033[0m" if _USE_COLOR else ""    # reset
_C = "\033[36m" if _USE_COLOR else ""   # cyan

# ── Templates ────────────────────────────────────────────────────────────────

DEFAULT_TOML = """\
[meta]
version = 1
# runs = 5
# delay = 5   # seconds between benchmarks (optional)

# Run all built-in benchmarks with default settings.
# To run only specific benchmarks, replace [benchmark.all]
# with individual entries like:
#
#   [benchmark.memory]
#   [benchmark.latency]
#   [benchmark.fps_64]
#   [benchmark.fps_128]
#   [benchmark.burst]
#   [benchmark.stress]
#
# You can override per-benchmark config:
#
#   [benchmark.latency]
#   pings = 2000

[benchmark.all]
"""

README = """\
# .vltxbench - Veltix benchmark configuration

## Structure

| Path | Description |
|------|-------------|
| `profiles/` | Saved benchmark profiles (TOML) |
| `profiles/default.toml` | Default profile, used when running `vltxbench` |
| `saved/` | JSON benchmark results with timestamps |
| `benchmarks/` | Custom external benchmarks (auto-detected) |

## Quick start

```bash
# Run default profile
vltxbench

# Run a specific profile
vltxbench --profile foo

# Run without project config (flags only)
vltxbench --tmp

# Re-generate this structure
vltxbench init
```
"""

_DIRS = ["profiles", "saved", "benchmarks"]
_FILES: list[tuple[str, str]] = [
    ("profiles/default.toml", DEFAULT_TOML),
    ("README.md", README),
]


def _ok(rel: str) -> str:
    return f"  {_G}OK{_R}  {_D}{rel}{_R}"


def _new(rel: str) -> str:
    return f"  {_G}+{_R}   {_D}{rel}{_R}"


def run_init(target: str = ".vltxbench") -> None:
    cwd = Path.cwd()
    base = cwd if cwd.name == ".vltxbench" else (cwd / target).resolve()

    print()

    if base.exists() and base.is_dir():
        existing = all((base / d).exists() for d in _DIRS) and all(
            (base / f).exists() for f, _ in _FILES
        )
        if existing:
            print(f"  Veltix benchmark project {_B}already initialized{_R}.")
            print(f"  {_D}Nothing to do.{_R}")
            print()
            print(f"  Run {_C}vltxbench{_R} to execute the default profile.")
            print()
            return

        print("  Updating Veltix benchmark project in")
        print()
        for d in _DIRS:
            path = base / d
            if path.exists():
                print(_ok(d + "/"))
            else:
                path.mkdir(parents=True, exist_ok=True)
                print(_new(d + "/"))
        for f, content in _FILES:
            path = base / f
            if path.exists():
                print(_ok(f))
            else:
                path.write_text(content.lstrip("\n"))
                print(_new(f))
        print()
        print(f"  {_D}Project updated.{_R}")
        print()
        print(f"  Run {_C}vltxbench{_R} to execute the default profile.")
        print()
        return

    for d in _DIRS:
        (base / d).mkdir(parents=True, exist_ok=True)
    for f, content in _FILES:
        (base / f).write_text(content.lstrip("\n"))

    print("  Initialized Veltix benchmark project in")
    print()
    print(f"  {_B}{base}{_R}")
    print()
    for d in _DIRS:
        print(_new(d + "/"))
    for f, _ in _FILES:
        print(_new(f))
    print()
    print(f"  {_D}Next steps:{_R}")
    print(f"    {_C}vltxbench{_R}          Run the default profile")
    print(f"    {_C}vltxbench --tmp{_R}    Run without project config")
    print()
