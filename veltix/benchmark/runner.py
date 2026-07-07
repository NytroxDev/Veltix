from __future__ import annotations

import sys
import traceback
from typing import Any, Dict, List, Optional, Sequence

from veltix.socket_core.core import SocketCore

from .benchmark import Benchmark

BACKEND_NAMES: Dict[str, SocketCore] = {
    "async": SocketCore.ASYNC,
    "threading": SocketCore.THREADING,
}


def _resolve_backends(value: str) -> List[SocketCore]:
    if value == "both":
        return [SocketCore.THREADING, SocketCore.ASYNC]
    if value in BACKEND_NAMES:
        return [BACKEND_NAMES[value]]
    raise ValueError(f"Unknown socket core: {value!r}")


class BenchRunner:
    """Orchestrates benchmark execution across backends and runs.

    Handles lifecycle, error recovery, and averaging.
    """

    def __init__(
        self,
        benches: Sequence[Benchmark],
        backend: str = "async",
        runs: int = 1,
    ) -> None:
        self.benches = list(benches)
        self.backends = _resolve_backends(backend)
        self.runs = runs
        self.errors: List[Dict[str, Any]] = []

    def run_all(self) -> Dict[str, Any]:
        """Run every benchmark and return a ``{name: result_or_list}`` dict."""
        results: Dict[str, Any] = {}
        for bench in self.benches:
            bench_results = self._run_bench(bench)
            if bench_results is not None:
                results[bench.name] = bench_results
        return results

    def _run_bench(self, bench: Benchmark) -> Optional[List[Any]]:
        """Run a single benchmark across all backends and runs."""
        per_backend: List[List[Any]] = []

        for backend in self.backends:
            run_results: List[Any] = []
            for run_idx in range(self.runs):
                if self.runs > 1:
                    print(f"\n  -- Run {run_idx + 1}/{self.runs} --")
                try:
                    result = bench.run(backend)
                    result.backend = backend.name.lower()
                    run_results.append(result)
                except Exception:
                    print(f"  ERROR: benchmark {bench.name} failed on {backend.name.lower()}:")
                    traceback.print_exc(file=sys.stdout)
                    self.errors.append({
                        "benchmark": bench.name,
                        "backend": backend.name.lower(),
                        "run": run_idx + 1,
                    })
                    continue

            if not run_results:
                per_backend.append([])
            elif self.runs > 1:
                avg = run_results[0].average(run_results)
                per_backend.append([avg])
            else:
                per_backend.append(run_results)

        flattened: List[Any] = []
        for items in per_backend:
            flattened.extend(items)
        return flattened if flattened else None
