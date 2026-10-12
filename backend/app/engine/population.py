"""Population allocation and probability helpers."""

from __future__ import annotations

import math

PROBABILITY_TOLERANCE = 1e-6


def probability_issue(values: list[float], field: str) -> str | None:
    """Return an error message when values are not a valid probability distribution."""

    if any(value < -1e-12 for value in values):
        return f"{field} contains a negative probability."
    if any(value > 1 + 1e-9 for value in values):
        return f"{field} contains a probability greater than 1."
    total = math.fsum(values)
    if abs(total - 1.0) > PROBABILITY_TOLERANCE:
        return (
            f"{field} probabilities sum to {total:.8f}. They must sum to 1 "
            f"within {PROBABILITY_TOLERANCE:g}. The server does not renormalize invalid inputs."
        )
    return None


def as_simplex(values: list[float]) -> list[float]:
    """Scale a validated distribution so NumPy receives weights that sum to 1.

    Validation already rejected sums outside 1e-6. Dividing by the sum only
    removes that residual so the multinomial generator accepts the vector.
    """

    total = math.fsum(values)
    if abs(total - 1.0) > PROBABILITY_TOLERANCE:
        raise ValueError("probabilities are not a valid distribution")
    if total <= 0:
        raise ValueError("probabilities sum to 0")
    return [value / total for value in values]


def equal_weights(count: int) -> list[float]:
    """Equal probabilities that sum to 1 in floating point."""

    if count < 1:
        raise ValueError("count must be positive")
    weights = [1.0 / count] * count
    weights[-1] = 1.0 - math.fsum(weights[:-1])
    return weights


def largest_remainder(total: int, weights: list[float]) -> list[int]:
    """Hamilton apportionment.

    Integer parts are assigned first. Leftover units go to the largest
    fractional parts. Exact fractional ties go to the earlier index.
    """

    if total < 0:
        raise ValueError("total must be non-negative")
    if not weights:
        if total == 0:
            return []
        raise ValueError("weights are required")
    if any(weight < 0 for weight in weights):
        raise ValueError("weights must be non-negative")
    weight_sum = math.fsum(weights)
    if abs(weight_sum - 1.0) > PROBABILITY_TOLERANCE:
        raise ValueError("weights must sum to 1")
    if total == 0:
        return [0 for _ in weights]
    raw = [total * weight for weight in weights]
    floors = [math.floor(value + 1e-12) for value in raw]
    remaining = total - sum(floors)
    order = sorted(
        range(len(weights)),
        key=lambda index: (raw[index] - floors[index], -index),
        reverse=True,
    )
    for index in order[:remaining]:
        floors[index] += 1
    if sum(floors) != total:
        raise RuntimeError("largest-remainder allocation did not reconcile")
    return floors


def clip_probability(value: float) -> float:
    return min(1.0, max(0.0, value))
