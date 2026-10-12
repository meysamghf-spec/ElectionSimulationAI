"""One-at-a-time sweeps and a small turnout grid.

The baseline inside a sensitivity report uses the same iteration cap as the
variations, so differences are not confounded by a longer original run.
"""

from __future__ import annotations

from app.config import Settings
from app.engine.population import clip_probability
from app.engine.simulate import run_simulation
from app.engine.version import DISCLAIMER
from app.schemas.results import SensitivityReport, SensitivityVariation
from app.schemas.spec import ElectionSpecification

HELD = [
    "eligible population",
    "regional structure",
    "voting method",
    "random seed",
    "blank-ballot rates, except when a variation would otherwise be invalid",
]


def run_sensitivity(spec: ElectionSpecification, settings: Settings) -> SensitivityReport:
    cap = min(spec.iterations, settings.sensitivity_iteration_cap)
    baseline_spec = spec.model_copy(deep=True)
    baseline_spec.iterations = cap
    baseline_spec.scenarios = []
    baseline_spec.reporting.include_histograms = False
    baseline_spec.reporting.include_regional = False
    baseline = run_simulation(baseline_spec, settings).scenarios[0]
    variations: list[SensitivityVariation] = []
    variations.extend(_turnout_sweep(baseline_spec, settings, baseline.mean_ballots, baseline))
    variations.extend(_invalid_sweep(baseline_spec, settings, baseline.mean_ballots, baseline))
    variations.extend(_preference_sweep(baseline_spec, settings, baseline.mean_ballots, baseline))
    applied = [item for item in variations if item.applied and item.max_absolute_share_percentage_points is not None]
    largest = max(applied, key=lambda item: item.max_absolute_share_percentage_points or 0.0, default=None)
    return SensitivityReport(
        disclaimer=DISCLAIMER,
        iteration_cap=cap,
        seed=spec.seed,
        design=(
            "Turnout is varied on a fixed additive grid. Invalid-ballot rates and a "
            "preference shift are varied one at a time. Each variation is a fresh "
            f"Monte Carlo run of {cap} iterations with the same seed."
        ),
        varied_parameters=[
            "turnout_probability additive delta",
            "invalid_rate replacement",
            "preference shift from the first candidate to the second",
        ],
        held_constant=HELD + ["candidate preferences, except in the preference-shift variations"],
        variations=variations,
        largest_effect_parameter=largest.parameter if largest else None,
        largest_effect_change=largest.change if largest else None,
        largest_effect_percentage_points=(
            largest.max_absolute_share_percentage_points if largest else None
        ),
        note=(
            "The largest effect is the biggest absolute percentage-point change in a "
            "candidate's mean simulated share inside this sweep. It is not a causal "
            "estimate for a real election. Share changes from turnout or invalid-rate "
            "variations can be near zero because those parameters scale participation "
            "without changing conditional preferences."
        ),
    )


def _turnout_sweep(
    baseline_spec: ElectionSpecification,
    settings: Settings,
    baseline_ballots: float,
    baseline: object,
) -> list[SensitivityVariation]:
    rows = []
    for delta in (-0.10, -0.05, 0.05, 0.10):
        varied = baseline_spec.model_copy(deep=True)
        for region in varied.regions:
            region.turnout_probability = clip_probability(region.turnout_probability + delta)
            if region.segments:
                for segment in region.segments:
                    segment.turnout_probability = clip_probability(segment.turnout_probability + delta)
        result = run_simulation(varied, settings).scenarios[0]
        rows.append(
            _variation(
                parameter="turnout_probability",
                change=f"additive {delta:+.2f}, clipped to [0, 1]",
                applied=True,
                reason="Applied to every region and segment.",
                held=_without("turnout"),
                baseline=baseline,
                result=result,
                baseline_ballots=baseline_ballots,
            )
        )
    return rows


def _invalid_sweep(
    baseline_spec: ElectionSpecification,
    settings: Settings,
    baseline_ballots: float,
    baseline: object,
) -> list[SensitivityVariation]:
    rows = []
    for rate in (0.0, 0.02, 0.05):
        varied = baseline_spec.model_copy(deep=True)
        blocked = False
        for region in varied.regions:
            if region.blank_rate + rate > 1:
                blocked = True
            region.invalid_rate = rate
            if region.segments:
                for segment in region.segments:
                    if segment.blank_rate + rate > 1:
                        blocked = True
                    segment.invalid_rate = rate
        if blocked:
            rows.append(
                SensitivityVariation(
                    parameter="invalid_rate",
                    change=f"replacement {rate:.2f}",
                    applied=False,
                    reason="Rejected because blank_rate + invalid_rate would exceed 1.",
                    held_constant=_without("invalid ballots"),
                    max_absolute_share_percentage_points=None,
                    leading_candidate_id=None,
                    leading_share_percentage_point_change=None,
                    mean_ballots=None,
                    mean_ballots_difference=None,
                    candidate_share_percentage_points={},
                )
            )
            continue
        result = run_simulation(varied, settings).scenarios[0]
        rows.append(
            _variation(
                parameter="invalid_rate",
                change=f"replacement {rate:.2f}",
                applied=True,
                reason="Applied to every region and segment.",
                held=_without("invalid ballots"),
                baseline=baseline,
                result=result,
                baseline_ballots=baseline_ballots,
            )
        )
    return rows


def _preference_sweep(
    baseline_spec: ElectionSpecification,
    settings: Settings,
    baseline_ballots: float,
    baseline: object,
) -> list[SensitivityVariation]:
    if len(baseline_spec.candidates) < 2:
        return [
            SensitivityVariation(
                parameter="preferences",
                change="shift toward the second candidate",
                applied=False,
                reason="A preference shift needs at least two candidates.",
                held_constant=_without("preferences"),
                max_absolute_share_percentage_points=None,
                leading_candidate_id=None,
                leading_share_percentage_point_change=None,
                mean_ballots=None,
                mean_ballots_difference=None,
                candidate_share_percentage_points={},
            )
        ]
    source = baseline_spec.candidates[0].id
    target = baseline_spec.candidates[1].id
    rows = []
    for shift in (0.05, 0.10):
        varied = baseline_spec.model_copy(deep=True)
        if not _shift_preferences(varied, source, target, shift):
            rows.append(
                SensitivityVariation(
                    parameter="preferences",
                    change=f"move {shift:.2f} from {source} to {target}",
                    applied=False,
                    reason=f"{source} does not have {shift:.2f} probability in every population unit.",
                    held_constant=_without("preferences"),
                    max_absolute_share_percentage_points=None,
                    leading_candidate_id=None,
                    leading_share_percentage_point_change=None,
                    mean_ballots=None,
                    mean_ballots_difference=None,
                    candidate_share_percentage_points={},
                )
            )
            continue
        result = run_simulation(varied, settings).scenarios[0]
        rows.append(
            _variation(
                parameter="preferences",
                change=f"move {shift:.2f} from {source} to {target}",
                applied=True,
                reason="Other preference weights were left unchanged, so the distribution still sums to 1.",
                held=_without("preferences"),
                baseline=baseline,
                result=result,
                baseline_ballots=baseline_ballots,
            )
        )
    return rows


def _shift_preferences(spec: ElectionSpecification, source: str, target: str, shift: float) -> bool:
    def shift_map(preferences: dict[str, float]) -> bool:
        if preferences.get(source, 0.0) < shift:
            return False
        preferences[source] -= shift
        preferences[target] += shift
        return True

    for region in spec.regions:
        if region.segments:
            for segment in region.segments:
                if not shift_map(segment.preferences):
                    return False
        elif not shift_map(region.preferences):
            return False
    return True


def _without(topic: str) -> list[str]:
    return [item for item in HELD if topic not in item] + [
        "all parameters other than the one named in this variation"
    ]


def _variation(
    *,
    parameter: str,
    change: str,
    applied: bool,
    reason: str,
    held: list[str],
    baseline: object,
    result: object,
    baseline_ballots: float,
) -> SensitivityVariation:
    from app.schemas.results import ScenarioResult

    if not isinstance(baseline, ScenarioResult) or not isinstance(result, ScenarioResult):
        raise TypeError("Sensitivity comparison expected scenario results.")
    points: dict[str, float | None] = {}
    max_abs = 0.0
    any_share = False
    leading_id = None
    leading_change = None
    best_left = -1.0
    left_by_id = {candidate.id: candidate for candidate in baseline.candidates}
    for candidate in result.candidates:
        left = left_by_id[candidate.id]
        if left.mean_share is None or candidate.mean_share is None:
            points[candidate.id] = None
            continue
        any_share = True
        delta = (candidate.mean_share - left.mean_share) * 100.0
        points[candidate.id] = delta
        max_abs = max(max_abs, abs(delta))
        if left.mean_share > best_left:
            best_left = left.mean_share
            leading_id = candidate.id
            leading_change = delta
    return SensitivityVariation(
        parameter=parameter,
        change=change,
        applied=applied,
        reason=reason,
        held_constant=held,
        max_absolute_share_percentage_points=max_abs if any_share else None,
        leading_candidate_id=leading_id,
        leading_share_percentage_point_change=leading_change,
        mean_ballots=result.mean_ballots,
        mean_ballots_difference=result.mean_ballots - baseline_ballots,
        candidate_share_percentage_points=points,
    )
