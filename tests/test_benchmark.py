from __future__ import annotations

from typing import Optional

import pytest

from veltix.benchmark.benchmark import Benchmark
from veltix.benchmark.runner import BenchRunner, _resolve_backends
from veltix.socket_core.core import SocketCore


class _DummyBench(Benchmark):
    name = "dummy"
    description = "A test benchmark"

    def __init__(self, config: Optional[dict] = None, name: Optional[str] = None):
        super().__init__(config=config, name=name)
        self.run_called = False
        self.last_backend = None

    def run(self, backend: SocketCore) -> str:
        self.run_called = True
        self.last_backend = backend
        return f"ok-{backend.name.lower()}"


class TestBenchmarkRegistry:
    def test_register_and_get(self):
        cls = Benchmark.get("dummy")
        assert cls is _DummyBench

    def test_get_unknown_raises(self):
        with pytest.raises(KeyError, match="Unknown benchmark"):
            Benchmark.get("nonexistent")

    def test_all_includes_dummy(self):
        names = [b.name for b in Benchmark.all()]
        assert "dummy" in names

    def test_names(self):
        all_names = Benchmark.names()
        assert "dummy" in all_names

    def test_instance_creation(self):
        bench = _DummyBench(config={"key": "val"})
        assert bench.config == {"key": "val"}

    def test_instance_name_override(self):
        bench = _DummyBench(name="custom_name")
        assert bench.benchmark_name == "custom_name"

    def test_class_name_fallback(self):
        bench = _DummyBench()
        assert bench.benchmark_name == "dummy"


class TestBenchRunner:
    def test_run_single_backend(self):
        bench = _DummyBench()
        runner = BenchRunner([bench], backend="async", runs=1)
        results = runner.run_all()

        assert bench.run_called is True
        assert bench.last_backend == SocketCore.ASYNC
        assert results["dummy"] == ["ok-async"]

    def test_run_both_backends(self):
        bench = _DummyBench()
        runner = BenchRunner([bench], backend="both", runs=1)
        results = runner.run_all()

        assert results["dummy"] == ["ok-threading", "ok-async"]

    def test_run_multiple_runs(self):
        bench = _DummyBench()
        runner = BenchRunner([bench], backend="async", runs=3)
        results = runner.run_all()

        assert bench.run_called is True
        assert results["dummy"] == ["ok-async", "ok-async", "ok-async"]

    def test_multiple_benches(self):
        bench_a = _DummyBench(name="bench_a")
        bench_b = _DummyBench(name="bench_b")
        runner = BenchRunner([bench_a, bench_b], backend="async", runs=1)
        results = runner.run_all()

        assert "bench_a" in results
        assert "bench_b" in results
        assert results["bench_a"] == ["ok-async"]
        assert results["bench_b"] == ["ok-async"]

    def test_empty_benches(self):
        runner = BenchRunner([], backend="async", runs=1)
        results = runner.run_all()
        assert results == {}

    def test_resolve_backends(self):
        assert _resolve_backends("async") == [SocketCore.ASYNC]
        assert _resolve_backends("threading") == [SocketCore.THREADING]
        assert _resolve_backends("both") == [SocketCore.THREADING, SocketCore.ASYNC]

    def test_resolve_backends_unknown(self):
        with pytest.raises(ValueError, match="Unknown socket core"):
            _resolve_backends("nope")
