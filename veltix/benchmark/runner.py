from __future__ import annotations

import sys
import traceback
from typing import TYPE_CHECKING, Any, Optional, Sequence

from veltix.socket_core.core import SocketCore

if TYPE_CHECKING:
    from .benchmark import Benchmark

BACKEND_NAMES: dict[str, SocketCore] = {
    "async": SocketCore.ASYNC,
    "threading": SocketCore.THREADING,
}


def _resolve_backends(value: str) -> list[SocketCore]:
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
        self.errors: list[dict[str, Any]] = []

    def _cancel(self) -> None:
        """Print cancellation message and skip remaining benches."""
        self._cancelled = True
        print()
        print("  Canceled by user.")
        print()

    def run_all(self) -> dict[str, Any]:
        """Run every benchmark and return a ``{name: result_or_list}`` dict."""
        results: dict[str, Any] = {}
        total = len(self.benches) * len(self.backends) * self.runs
        step = 0
        self._cancelled = False
        for bench in self.benches:
            if self._cancelled:
                break
            bench_results = self._run_bench(bench, total, step)
            if bench_results is not None:
                results[bench.benchmark_name] = bench_results
                step += len(self.backends) * self.runs
        return results

    def _run_bench(
        self,
        bench: Benchmark,
        total: int,
        start_step: int,
    ) -> Optional[list[Any]]:
        """Run a single benchmark across all backends and runs."""
        per_backend: list[list[Any]] = []
        step = start_step

        for backend in self.backends:
            if self._cancelled:
                break
            run_results: list[Any] = []
            for run_idx in range(self.runs):
                if self._cancelled:
                    break
                step += 1
                label = f"[{step}/{total}]"
                if self.runs > 1:
                    label += f" run {run_idx + 1}/{self.runs}"
                bench._step_label = f"{label} {bench.benchmark_name} ({backend.name.lower()})"
                try:
                    result = bench.run(backend)
                    if hasattr(result, "backend") and not isinstance(
                        type(result).backend, property
                    ):
                        result.backend = backend.name.lower()
                    run_results.append(result)
                except KeyboardInterrupt:
                    self._cancel()
                    break
                except Exception:
                    print(
                        f"  ERROR: benchmark {bench.benchmark_name} failed on {backend.name.lower()}:"
                    )
                    traceback.print_exc(file=sys.stdout)
                    self.errors.append(
                        {
                            "benchmark": bench.benchmark_name,
                            "backend": backend.name.lower(),
                            "run": run_idx + 1,
                        }
                    )
                    continue

            if not run_results:
                per_backend.append([])
            elif self.runs > 1 and hasattr(run_results[0], "average"):
                avg = run_results[0].average(run_results)
                per_backend.append([avg])
            else:
                per_backend.append(run_results)

        flattened: list[Any] = []
        for items in per_backend:
            flattened.extend(items)
        return flattened if flattened else None
