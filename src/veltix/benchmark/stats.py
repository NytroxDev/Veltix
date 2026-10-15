"""
stats.py
--------
Robust statistical helpers shared by the benchmark suite.

Benchmarks must never publish a bare number: the reader has to be able to tell
a real difference from run-to-run noise. Every aggregation therefore goes
through :func:`summarize`, which reports the **median** as the central estimate
(not the mean, and never a mean of per-run standard deviations) and carries the
run-to-run dispersion and a 95% confidence interval.

``n = 1`` is still supported (single-run mode): the summary then collapses to
the single observed value with a zero-width interval.
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

# Number of bootstrap resamples used for the median's 95% confidence interval.
BOOTSTRAP_RESAMPLES = 2000

# Fixed seed so the interval is reproducible from the same samples.
BOOTSTRAP_SEED = 0x5E17C5

# A run-to-run 95% CI half-width wider than this fraction of the median means
# the metric is too unstable to publish as a single number. It is only
# assessable with n >= 2 runs: a lone run cannot reveal run-to-run noise.
NOISY_CI_RATIO = 0.10


def percentile(values: Sequence[float], pct: float) -> float:
    """Return the ``pct``-th percentile of ``values`` (linear interpolation).

    This is the single percentile definition used across the suite - the
    per-benchmark copies are gone so latency, burst and memory numbers can be
    compared without worrying about the interpolation method.

    Args:
        values: Sample values. An empty sequence yields ``0.0``.
        pct: Percentile in ``[0, 100]``.

    Returns:
        The interpolated percentile as a float.
    """
    ordered = sorted(float(v) for v in values)
    n = len(ordered)
    if n == 0:
        return 0.0
    if n == 1:
        return ordered[0]
    if pct <= 0:
        return ordered[0]
    if pct >= 100:
        return ordered[-1]
    rank = (pct / 100.0) * (n - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[int(rank)]
    frac = rank - low
    return ordered[low] * (1.0 - frac) + ordered[high] * frac


def bootstrap_ci(
    values: Sequence[float],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    alpha: float = 0.05,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float]:
    """Return the percentile-bootstrap confidence interval of the median.

    Args:
        values: Sample values.
        resamples: Number of bootstrap resamples.
        alpha: Significance level (``0.05`` gives a 95% interval).
        seed: RNG seed, kept fixed so the interval is reproducible.

    Returns:
        ``(low, high)`` bounds. Empty input yields ``(0.0, 0.0)``; a single
        value yields ``(value, value)``.
    """
    data = [float(v) for v in values]
    n = len(data)
    if n == 0:
        return (0.0, 0.0)
    if n == 1:
        return (data[0], data[0])

    rng = random.Random(seed)
    medians: list[float] = []
    for _ in range(resamples):
        sample = [data[rng.randrange(n)] for _ in range(n)]
        medians.append(statistics.median(sample))

    return (
        percentile(medians, alpha / 2.0 * 100.0),
        percentile(medians, (1.0 - alpha / 2.0) * 100.0),
    )


@dataclass(frozen=True)
class Summary:
    """Dispersion summary of one metric across runs."""

    n: int
    median: float
    mean: float
    stdev: float
    p25: float
    p75: float
    iqr: float
    min: float
    max: float
    ci95_low: float
    ci95_high: float

    @property
    def ci95_half(self) -> float:
        """Half-width of the 95% confidence interval."""
        return (self.ci95_high - self.ci95_low) / 2.0

    @property
    def relative_ci(self) -> float | None:
        """95% CI half-width as a fraction of the median.

        Returns:
            The relative half-width, or None when the median is zero (the ratio
            is undefined and the metric is not flagged).
        """
        if self.median == 0:
            return None
        return self.ci95_half / abs(self.median)

    @property
    def is_noisy(self) -> bool:
        """Whether run-to-run dispersion exceeds the publication threshold.

        A single run (``n < 2``) reveals no run-to-run noise and is never
        flagged; it simply cannot be assessed.
        """
        if self.n < 2:
            return False
        ratio = self.relative_ci
        return ratio is not None and ratio > NOISY_CI_RATIO

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        relative = self.relative_ci
        return {
            "n": self.n,
            "median": round(self.median, 6),
            "mean": round(self.mean, 6),
            "stdev": round(self.stdev, 6),
            "p25": round(self.p25, 6),
            "p75": round(self.p75, 6),
            "iqr": round(self.iqr, 6),
            "min": round(self.min, 6),
            "max": round(self.max, 6),
            "ci95": [round(self.ci95_low, 6), round(self.ci95_high, 6)],
            "rel_ci": round(relative, 6) if relative is not None else None,
            "noisy": self.is_noisy,
        }


def summarize(values: Sequence[float], *, ci: bool = True) -> Summary:
    """Summarize a metric observed once per run.

    The central estimate is the median (robust to a single noisy run); the
    dispersion is reported as the inter-quartile range plus a 95% bootstrap
    confidence interval on the median.

    Args:
        values: One value per run.
        ci: Compute the bootstrap confidence interval (disable to save time
            when only the median and IQR are needed).

    Returns:
        A :class:`Summary`. Empty input yields an all-zero summary.
    """
    data = [float(v) for v in values]
    n = len(data)
    if n == 0:
        return Summary(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    median = statistics.median(data)
    if n == 1:
        return Summary(1, median, median, 0.0, median, median, 0.0, median, median, median, median)

    p25 = percentile(data, 25.0)
    p75 = percentile(data, 75.0)
    mean = statistics.fmean(data)
    stdev = statistics.stdev(data)
    if ci:
        low, high = bootstrap_ci(data)
    else:
        low = high = median
    return Summary(
        n=n,
        median=median,
        mean=mean,
        stdev=stdev,
        p25=p25,
        p75=p75,
        iqr=p75 - p25,
        min=min(data),
        max=max(data),
        ci95_low=low,
        ci95_high=high,
    )
