"""Monte Carlo summaries.

Intervals here estimate simulation error under the configured model. They are
not confidence intervals for a real-world election.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.stats import norm

from app.schemas.results import Histogram, IntervalEstimate

MEAN_INTERVAL_MEANING = (
    "Approximate 95% interval for the expected value under this simulation model, "
    "using a normal approximation to the Monte Carlo mean. It is not an interval "
    "for an official election result."
)
WILSON_MEANING = (
    "95% Wilson interval for the Monte Carlo estimate of this model's sole-win "
    "frequency. It is not a confidence interval for a real electorate."
)


def sample_std(values: np.ndarray) -> float:
    if values.size < 2:
        return 0.0
    return float(np.std(values, ddof=1))


def quantiles(values: np.ndarray) -> dict[str, float]:
    if values.size == 0:
        return {key: 0.0 for key in ("p05", "p25", "p50", "p75", "p95")}
    points = np.quantile(values, [0.05, 0.25, 0.5, 0.75, 0.95])
    return {
        "p05": float(points[0]),
        "p25": float(points[1]),
        "p50": float(points[2]),
        "p75": float(points[3]),
        "p95": float(points[4]),
    }


def mean_interval(values: np.ndarray) -> IntervalEstimate:
    n = int(values.size)
    mean = float(np.mean(values)) if n else 0.0
    if n < 2:
        return IntervalEstimate(
            low=mean,
            high=mean,
            method="undefined_small_sample",
            meaning="Fewer than two iterations, so no Monte Carlo standard error was computed.",
        )
    standard_error = sample_std(values) / math.sqrt(n)
    z_value = float(norm.ppf(0.975))
    return IntervalEstimate(
        low=mean - z_value * standard_error,
        high=mean + z_value * standard_error,
        method="normal_monte_carlo_mean",
        meaning=MEAN_INTERVAL_MEANING,
    )


def wilson_interval(successes: int, trials: int) -> IntervalEstimate:
    if trials <= 0:
        return IntervalEstimate(
            low=0.0,
            high=0.0,
            method="wilson_monte_carlo",
            meaning=WILSON_MEANING,
        )
    z_value = float(norm.ppf(0.975))
    proportion = successes / trials
    z_squared = z_value * z_value
    denominator = 1.0 + z_squared / trials
    center = (proportion + z_squared / (2.0 * trials)) / denominator
    half = (z_value / denominator) * math.sqrt(
        proportion * (1.0 - proportion) / trials + z_squared / (4.0 * trials * trials)
    )
    return IntervalEstimate(
        low=max(0.0, center - half),
        high=min(1.0, center + half),
        method="wilson_monte_carlo",
        meaning=WILSON_MEANING,
    )


def frequency_standard_error(proportion: float, trials: int) -> float:
    if trials <= 0:
        return 0.0
    return math.sqrt(proportion * (1.0 - proportion) / trials)


def histogram(values: np.ndarray, bins: int) -> Histogram:
    if values.size == 0:
        return Histogram(edges=[], counts=[], note="No simulated values.")
    lowest = float(np.min(values))
    highest = float(np.max(values))
    if lowest == highest:
        return Histogram(
            edges=[lowest, highest],
            counts=[int(values.size)],
            note="All simulated values were identical, so the histogram is a single point mass.",
        )
    bin_count = max(1, min(bins, values.size))
    counts, edges = np.histogram(values, bins=bin_count)
    return Histogram(
        edges=[float(edge) for edge in edges],
        counts=[int(count) for count in counts],
        note="Empirical histogram of simulated iteration outcomes.",
    )


def nan_mean(values: np.ndarray) -> float | None:
    if values.size == 0 or np.all(np.isnan(values)):
        return None
    return float(np.nanmean(values))


def nan_std(values: np.ndarray) -> float | None:
    finite = values[~np.isnan(values)]
    if finite.size == 0:
        return None
    if finite.size == 1:
        return 0.0
    return float(np.std(finite, ddof=1))


def nan_quantiles(values: np.ndarray) -> dict[str, float] | None:
    finite = values[~np.isnan(values)]
    if finite.size == 0:
        return None
    return quantiles(finite)
