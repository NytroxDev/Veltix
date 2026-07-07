from __future__ import annotations

import json as _json
from pathlib import Path
from typing import Any

from .display import _B as _BOLD
from .display import _DIM
from .display import _R as _RESET


def _benchmark_list() -> list[dict[str, Any]]:
    from .benchmark import Benchmark
    from .profile import _INSTANCES

    all_benches = Benchmark.all()
    named: dict[str, type[Benchmark]] = {c.name: c for c in all_benches if c.name}
    entries: list[dict[str, Any]] = []

    for name in ["memory", "latency", "fps", "burst", "stress"]:
        cls = named.get(name)
        if cls is None:
            continue
        entry: dict[str, Any] = {
            "name": name,
            "description": cls.description or "",
        }
        instances = [
            {"name": inst_name, "config": defaults}
            for inst_name, (cls_name, defaults) in _INSTANCES.items()
            if cls_name == name
        ]
        if instances:
            entry["instances"] = instances
        entries.append(entry)

    return entries


def _profile_list() -> list[dict[str, Any]]:
    vltx_dir = Path(".vltxbench")
    profiles_dir = vltx_dir / "profiles"

    if not vltx_dir.exists() or not profiles_dir.exists():
        return []

    tomls = sorted(profiles_dir.glob("*.toml"))
    entries: list[dict[str, Any]] = []
    for path in tomls:
        entries.append({
            "name": path.stem,
            "path": str(path),
        })
    return entries


def _render_benchmarks_text() -> None:
    entries = _benchmark_list()
    print(f"  {_BOLD}Benchmarks{_RESET}")
    print()
    for entry in entries:
        desc = f"  -- {entry['description']}" if entry["description"] else ""
        print(f"    {_BOLD}{entry['name']}{_RESET}{desc}")
        for inst in entry.get("instances", []):
            parts = ", ".join(f"{k}={v}" for k, v in inst["config"].items())
            print(f"      {_DIM}{inst['name']}{_RESET}  ({parts})")
    print()


def _render_profiles_text() -> None:
    entries = _profile_list()
    print(f"  {_BOLD}Profiles{_RESET}")
    print()
    if not entries:
        print("    No profiles found. Run 'vltxbench init' to create one.")
        print()
        return
    for entry in entries:
        label = f"    {_BOLD}{entry['name']}{_RESET}"
        if entry["name"] == "default":
            label += f"  {_DIM}(auto-loaded){_RESET}"
        print(label)
    print()


def cmd_list(
    show_benchmarks: bool = True,
    show_profiles: bool = True,
    as_json: bool = False,
) -> None:
    if as_json:
        payload: dict[str, Any] = {}
        if show_benchmarks:
            payload["benchmarks"] = _benchmark_list()
        if show_profiles:
            payload["profiles"] = _profile_list()
        print(_json.dumps(payload, indent=2))
        return

    if show_benchmarks:
        _render_benchmarks_text()
    if show_profiles:
        if show_benchmarks and show_profiles:
            print()
        _render_profiles_text()
