from __future__ import annotations

from pathlib import Path

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

TREE = """\
.vltxbench/
├── benchmarks/     # Custom external benchmarks
├── profiles/
│   └── default.toml   # Default benchmark profile
├── saved/          # Saved benchmark results (JSON)
└── README.md       # This file
"""


def run_init(target: str = ".vltxbench") -> None:
    cwd = Path.cwd()
    base = cwd if cwd.name == ".vltxbench" else (cwd / target).resolve()

    if base.exists():
        print(f"  {base}/ already initialized")
        return

    dirs = [
        base / "profiles",
        base / "saved",
        base / "benchmarks",
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    files: list[tuple[Path, str]] = [
        (base / "profiles" / "default.toml", DEFAULT_TOML),
        (base / "README.md", README),
    ]

    for path, content in files:
        path.write_text(content.lstrip("\n"))

    print(f"  Initialized empty Veltix benchmark project in {base}/")
    for d in dirs:
        print(f"    {d}/")
    for f, _ in files:
        print(f"    {f}")
