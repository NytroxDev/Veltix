"""Unit tests for the benchmark statistical core (``veltix.benchmark.stats``)."""

from __future__ import annotations

import statistics

import pytest

from veltix.benchmark import stats
from veltix.benchmark.models import LatencyStats, StressResult


class TestPercentile:
    def test_empty_is_zero(self) -> None:
        assert stats.percentile([], 50) == 0.0

    def test_single_value(self) -> None:
        assert stats.percentile([7.0], 50) == 7.0

    def test_linear_interpolation(self) -> None:
        # Median of an even-sized sample interpolates between the middle two.
        assert stats.percentile([1.0, 2.0, 3.0, 4.0], 50) == pytest.approx(2.5)
        assert stats.percentile([1.0, 2.0, 3.0, 4.0], 25) == pytest.approx(1.75)

    def test_extremes(self) -> None:
        data = [3.0, 1.0, 2.0]
        assert stats.percentile(data, 0) == 1.0
        assert stats.percentile(data, 100) == 3.0

    def test_monotonic(self) -> None:
        data = [5.0, 1.0, 3.0, 9.0, 2.0]
        previous = -1.0
        for pct in range(0, 101, 5):
            value = stats.percentile(data, float(pct))
            assert value >= previous
            previous = value


class TestBootstrapCI:
    def test_empty(self) -> None:
        assert stats.bootstrap_ci([]) == (0.0, 0.0)

    def test_single_value_collapses(self) -> None:
        assert stats.bootstrap_ci([3.0]) == (3.0, 3.0)

    def test_brackets_median(self) -> None:
        low, high = stats.bootstrap_ci([1.0, 2.0, 3.0, 4.0, 5.0])
        assert low <= statistics.median([1, 2, 3, 4, 5]) <= high

    def test_is_reproducible(self) -> None:
        values = [0.11, 0.09, 0.13, 0.10, 0.12]
        assert stats.bootstrap_ci(values) == stats.bootstrap_ci(values)


class TestSummarize:
    def test_empty(self) -> None:
        s = stats.summarize([])
        assert s.n == 0
        assert s.median == 0.0
        assert (s.ci95_low, s.ci95_high) == (0.0, 0.0)

    def test_single_value_has_zero_interval(self) -> None:
        s = stats.summarize([3.5])
        assert s.n == 1
        assert s.median == 3.5
        assert s.iqr == 0.0
        assert (s.ci95_low, s.ci95_high) == (3.5, 3.5)

    def test_median_is_central_estimate(self) -> None:
        s = stats.summarize([1.0, 2.0, 100.0])
        assert s.median == 2.0
        assert s.mean == pytest.approx(34.3333, rel=1e-3)
        assert s.ci95_low <= s.median <= s.ci95_high

    def test_iqr_and_stdev(self) -> None:
        values = [1.0, 2.0, 3.0, 4.0]
        s = stats.summarize(values)
        assert s.iqr == pytest.approx(s.p75 - s.p25)
        assert s.stdev == pytest.approx(statistics.stdev(values))

    def test_ci_can_be_disabled(self) -> None:
        s = stats.summarize([1.0, 2.0, 3.0], ci=False)
        assert (s.ci95_low, s.ci95_high) == (s.median, s.median)


def _stress(tps_stdev: float, throughput: float) -> StressResult:
    return StressResult(
        num_clients=100,
        msgs_per_client=100,
        total_sent=10_000,
        total_recv=10_000,
        success_rate=100.0,
        throughput=throughput,
        duration_s=1.0,
        ram_delta_mb=1.0,
        send_phase_s=0.5,
        drain_time_s=0.5,
        time_to_first_recv_ms=1.0,
        per_client_tps_avg=100.0,
        per_client_tps_min=90.0,
        per_client_tps_max=110.0,
        per_client_tps_stdev=tps_stdev,
    )


class TestAggregation:
    def test_uses_median_not_mean(self) -> None:
        agg = StressResult.aggregate(
            [_stress(1.0, 100.0), _stress(2.0, 200.0), _stress(3.0, 300.0)]
        )
        assert agg.per_client_tps_stdev == 2
        assert agg.throughput == 200.0

    def test_constant_fields_pass_through_and_are_not_metrics(self) -> None:
        agg = StressResult.aggregate(
            [_stress(1.0, 100.0), _stress(2.0, 200.0), _stress(3.0, 300.0)]
        )
        assert agg.num_clients == 100
        assert agg.msgs_per_client == 100
        assert "num_clients" not in agg.metrics

    def test_n_runs_and_per_metric_dispersion(self) -> None:
        agg = StressResult.aggregate(
            [_stress(1.0, 100.0), _stress(2.0, 200.0), _stress(3.0, 300.0)]
        )
        assert agg.n_runs == 3
        entry = agg.metrics["throughput"]
        assert entry["n"] == 3
        assert entry["median"] == 200.0
        assert entry["ci95"][0] <= 200.0 <= entry["ci95"][1]

    def test_to_dict_carries_run_metadata(self) -> None:
        agg = StressResult.aggregate([_stress(1.0, 100.0), _stress(2.0, 200.0)])
        data = agg.to_dict()
        assert data["n_runs"] == 2
        assert data["metrics"]["throughput"]["n"] == 2


class TestLatencyAggregation:
    @staticmethod
    def _lat(samples: list[float], jitter: float, throughput: float) -> LatencyStats:
        lat = LatencyStats()
        for value in samples:
            lat.add(value)
        lat.jitter_ms = jitter
        lat.throughput = throughput
        return lat

    def test_pools_samples_and_medians_run_metrics(self) -> None:
        a = self._lat([1.0, 2.0, 3.0], jitter=0.1, throughput=100.0)
        b = self._lat([4.0, 5.0, 6.0], jitter=0.3, throughput=200.0)
        agg = LatencyStats.aggregate([a, b])

        assert agg.count == 6
        assert agg.jitter_ms == pytest.approx(0.2)
        assert agg.throughput == pytest.approx(150.0)
        assert agg.n_runs == 2

    def test_metrics_cover_displayed_stats(self) -> None:
        a = self._lat([1.0, 2.0, 3.0], jitter=0.1, throughput=100.0)
        b = self._lat([4.0, 5.0, 6.0], jitter=0.3, throughput=200.0)
        agg = LatencyStats.aggregate([a, b])

        for key in ("avg", "median", "p95", "p99", "stdev", "jitter_ms", "throughput"):
            assert agg.metrics[key]["n"] == 2

    def test_percentile_uses_shared_definition(self) -> None:
        lat = self._lat([1.0, 2.0, 3.0, 4.0], jitter=0.0, throughput=0.0)
        assert lat.percentile(50) == pytest.approx(stats.percentile([1.0, 2.0, 3.0, 4.0], 50))
