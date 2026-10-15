"""Unit tests for the benchmark run scheduler (warmup, cooldown, ordering)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from veltix.benchmark.cli import _run_runs

if TYPE_CHECKING:
    import pytest


class _Result:
    """Minimal stand-in for a benchmark result with an ``aggregate`` method."""

    def __init__(self, backend: str | None = None) -> None:
        self.backend = backend
        self.n = 0

    def aggregate(self, results: list[Any]) -> _Result:
        aggregated = _Result(self.backend)
        aggregated.n = len(results)
        return aggregated


def _runner_calls() -> tuple[Any, list[tuple[str, str]]]:
    calls: list[tuple[str, str]] = []

    def runner(*args: Any, socket_core: str, step_label: str) -> _Result:
        calls.append((socket_core, step_label))
        return _Result(socket_core)

    return runner, calls


def _noop_sleep(record: list[float]) -> Any:
    def sleep(seconds: float) -> None:
        record.append(seconds)

    return sleep


class TestWarmup:
    def test_warmup_runs_are_discarded(self) -> None:
        runner, calls = _runner_calls()
        results = _run_runs(
            runner, ["threading", "async"], 1, [0, 2], "bench", warmup=1, sleep=_noop_sleep([])
        )
        assert len(calls) == 4
        assert [backend for backend, _ in calls[:2]] == ["threading", "async"]
        assert all(label.startswith("warmup") for _, label in calls[:2])
        assert all(not label.startswith("warmup") for _, label in calls[2:])
        assert len(results) == 2

    def test_warmup_zero_has_no_warmup_calls(self) -> None:
        runner, calls = _runner_calls()
        _run_runs(
            runner, ["threading", "async"], 1, [0, 2], "bench", warmup=0, sleep=_noop_sleep([])
        )
        assert len(calls) == 2
        assert all(not label.startswith("warmup") for _, label in calls)


class TestOrdering:
    def test_backend_order_alternates_between_runs(self) -> None:
        runner, calls = _runner_calls()
        _run_runs(
            runner,
            ["threading", "async"],
            3,
            [0, 6],
            "bench",
            warmup=0,
            cooldown=0.0,
            sleep=_noop_sleep([]),
        )
        measured = [backend for backend, _ in calls]
        assert measured == ["threading", "async", "async", "threading", "threading", "async"]


class TestCooldown:
    def test_sleeps_between_runs_only(self) -> None:
        runner, _ = _runner_calls()
        sleeps: list[float] = []
        _run_runs(
            runner,
            ["threading", "async"],
            3,
            [0, 6],
            "bench",
            warmup=0,
            cooldown=0.25,
            sleep=_noop_sleep(sleeps),
        )
        assert sleeps == [0.25, 0.25]

    def test_no_sleep_for_single_run(self) -> None:
        runner, _ = _runner_calls()
        sleeps: list[float] = []
        _run_runs(
            runner,
            ["threading", "async"],
            1,
            [0, 2],
            "bench",
            warmup=0,
            cooldown=0.5,
            sleep=_noop_sleep(sleeps),
        )
        assert sleeps == []


class TestAggregation:
    def test_aggregates_per_backend(self) -> None:
        runner, _ = _runner_calls()
        results = _run_runs(
            runner,
            ["threading", "async"],
            2,
            [0, 4],
            "bench",
            warmup=0,
            cooldown=0.0,
            sleep=_noop_sleep([]),
        )
        assert [result.backend for result in results] == ["threading", "async"]
        assert all(result.n == 2 for result in results)

    def test_single_run_returns_raw_results(self) -> None:
        runner, _ = _runner_calls()
        results = _run_runs(
            runner, ["threading", "async"], 1, [0, 2], "bench", warmup=0, sleep=_noop_sleep([])
        )
        assert all(result.n == 0 for result in results)


class TestStepCounter:
    def test_counts_measured_runs_only(self) -> None:
        runner, _ = _runner_calls()
        counter = [0, 4]
        _run_runs(
            runner,
            ["threading", "async"],
            2,
            counter,
            "bench",
            warmup=1,
            cooldown=0.0,
            sleep=_noop_sleep([]),
        )
        assert counter[0] == 4


class TestWarmupQuiet:
    def test_warmup_report_is_swallowed(self, capsys: pytest.CaptureFixture[str]) -> None:
        def runner(*args: Any, socket_core: str, step_label: str) -> _Result:
            print(f"REPORT {step_label}")
            return _Result(socket_core)

        _run_runs(runner, ["threading"], 1, [0, 1], "bench", warmup=1, sleep=_noop_sleep([]))
        out = capsys.readouterr().out

        assert "REPORT warmup" not in out
        assert "REPORT [1/1]" in out
        assert "warmup bench (threading) ... done" in out
