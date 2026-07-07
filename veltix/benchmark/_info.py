from __future__ import annotations

from .benchmark import Benchmark
from .display import _B as _BOLD
from .display import _R as _RESET


def cmd_info(name: str) -> None:
    cls = Benchmark.get(name)
    desc = cls.description or ""

    print()
    print(f"  {_BOLD}{name}{_RESET}")
    print()
    print("  Description:")
    print(f"    {desc}")
    print()

    params = cls.parameters
    if params:
        print("  Parameters:")
        for pname, meta in params.items():
            ptype = meta.get("type", "")
            pdefault = meta.get("default", "")
            pdesc = meta.get("description", "")
            line = f"    {pname}"
            if ptype:
                line += f"  ({ptype}"
                if pdefault != "":
                    line += f", default: {pdefault}"
                line += ")"
            else:
                if pdefault != "":
                    line += f"  (default: {pdefault})"
            print(line)
            if pdesc:
                print(f"      {pdesc}")
        print()

    outputs = cls.outputs
    if outputs:
        print("  Output:")
        for out in outputs:
            print(f"    - {out}")
        print()

    print()
