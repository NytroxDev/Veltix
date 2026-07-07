from __future__ import annotations

import dataclasses
from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .benchmark import Benchmark

# TOML loader: try tomllib (3.11+), fallback to tomli, else error

_LOADER: Optional[str] = None

try:
    import tomllib  # type: ignore[import-not-found,unused-ignore]

    _LOADER = "tomllib"
except ImportError:
    try:
        import tomli  # type: ignore[import-not-found,unused-ignore]

        _LOADER = "tomli"
    except ImportError:
        pass


def _parse_toml(path: Path) -> dict[str, Any]:
    if _LOADER == "tomllib":
        with path.open("rb") as f:
            return tomllib.load(f)  # type: ignore[no-any-return]  # noqa: F821
    if _LOADER == "tomli":
        with path.open("rb") as f:
            return tomli.load(f)  # type: ignore[no-any-return]  # noqa: F821
    raise ImportError(
        "TOML support requires Python 3.11+ or the `tomli` package.\n"
        "  Install: pip install veltix[benchmark]"
    )


# ── Profile data ──────────────────────────────────────────────────────────────


@dataclasses.dataclass
class Profile:
    runs: int
    benches: list[Benchmark]


# ── Mappings ───────────────────────────────────────────────────────────────────

_BUILTIN = ["memory", "latency", "fps", "burst", "stress"]

# Instance-based benches: each maps to the class name + config defaults
_INSTANCES: dict[str, tuple[str, dict[str, Any]]] = {
    "fps_64": (
        "fps",
        {"players": 64, "tick_rate": 64, "duration": 5.0},
    ),
    "fps_128": (
        "fps",
        {"players": 128, "tick_rate": 20, "duration": 5.0},
    ),
}


def _build_benches_from_sections(
    sections: dict[str, dict[str, Any]],
) -> list[Benchmark]:
    from .benchmark import Benchmark

    # Collect per-bench config overrides, but don't expand yet
    overrides: dict[str, dict[str, Any]] = {}
    has_all = False
    for raw_key, cfg in sections.items():
        if raw_key == "all":
            has_all = True
        elif raw_key in _BUILTIN or raw_key in _INSTANCES:
            overrides[raw_key] = dict(cfg)
        else:
            raise KeyError(
                f"Unknown benchmark: {raw_key!r}. Available: {_BUILTIN + list(_INSTANCES)}"
            )

    benches: list[Benchmark] = []
    handled: set[str] = set()

    if has_all:
        for name in _BUILTIN:
            if name == "fps":
                for inst_name, (cls_name, defaults) in _INSTANCES.items():
                    if inst_name not in handled:
                        cfg = {**defaults, **overrides.get(inst_name, {})}
                        benches.append(Benchmark.get(cls_name)(cfg, name=inst_name))
                        handled.add(inst_name)
            elif name not in handled:
                cfg = dict(overrides.get(name, {}))
                benches.append(Benchmark.get(name)(cfg))
                handled.add(name)

    # Add any remaining named benches (not yet handled by "all")
    for raw_key, cfg in overrides.items():
        if raw_key in handled:
            continue
        if raw_key in _INSTANCES:
            cls_name, defaults = _INSTANCES[raw_key]
            merged = {**defaults, **cfg}
            benches.append(Benchmark.get(cls_name)(merged, name=raw_key))
            handled.add(raw_key)
        elif raw_key in _BUILTIN:
            benches.append(Benchmark.get(raw_key)(dict(cfg)))
            handled.add(raw_key)

    return benches


# ── Public API ────────────────────────────────────────────────────────────────


def load_profile(path: Path) -> Profile:
    data = _parse_toml(path)

    meta = data.get("meta", {})
    runs = int(meta.get("runs", 1))
    version = meta.get("version", 1)

    if version != 1:
        raise ValueError(
            f"Unsupported profile version {version}. This version of vltxbench supports version 1."
        )

    bench_sections_raw = data.get("benchmark", {})
    bench_sections: dict[str, dict[str, Any]] = {
        k: dict(v) if isinstance(v, dict) else {} for k, v in bench_sections_raw.items()
    }

    benches: list[Benchmark] = []
    if bench_sections:
        benches = _build_benches_from_sections(bench_sections)

    return Profile(runs=runs, benches=benches)


def find_profile(name: str, base: Path) -> Path:
    """Locate a profile file by name (with or without .toml suffix)."""
    path = base / name
    if path.suffix == ".toml":
        return path if path.exists() else path
    with_toml = path.with_suffix(".toml")
    if with_toml.exists():
        return with_toml
    return path  # let caller handle FileNotFoundError
