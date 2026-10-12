"""Monte Carlo election simulation.

Random draws for one iteration, in order:
1. One shared normal shock, only when turnout_shock_sd > 0.
2. For each region, then each segment if configured:
   binomial turnout, then multinomial ballot types when ballots > 0,
   then multinomial preferences or ranking blocs when valid ballots > 0.
3. Two-round transfer draws, only when a runoff happens and transfers exist,
   in specification candidate order.

Population units with a zero draw do not consume a multinomial variate.
Segment sizes are fixed by largest remainder before the first iteration.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import Counter
from collections.abc import Callable
from typing import Any, TypedDict

import numpy as np
from scipy.stats import binom

from app.config import Settings
from app.engine.allocate import MethodResult, dhondt, instant_runoff, plurality, two_round
from app.engine.compare import compare_scenarios
from app.engine.population import as_simplex, clip_probability, largest_remainder
from app.engine.scenarios import apply_scenario
from app.engine.statistics import (
    frequency_standard_error,
    histogram,
    mean_interval,
    nan_mean,
    nan_quantiles,
    nan_std,
    quantiles,
    sample_std,
    wilson_interval,
)
from app.engine.validate import ensure_valid
from app.engine.version import ALGORITHM_VERSION, DISCLAIMER
from app.errors import Cancelled, InvariantError
from app.schemas.results import (
    CandidateSummary,
    CheckResult,
    Histogram,
    RegionalSummary,
    RoundTrace,
    ScenarioResult,
    SimulationOutput,
)
from app.schemas.spec import ElectionSpecification, RankingBloc, RegionSpec, ScenarioSpec

ProgressCallback = Callable[[float], None]


class ExpectationPreview(TypedDict):
    ballots: float | None
    valid: float | None
    votes: dict[str, float] | None
    note: str


class RegionalExpectation(TypedDict):
    ballots: float | None
    variance: float | None
    label: str


class UnitDraw(TypedDict):
    ballots: int
    valid: int
    blank: int
    invalid: int
    votes: dict[str, int]
    blocs: dict[tuple[str, ...], int]


class RegionDraw(TypedDict):
    id: str
    ballots: int
    valid: int
    blank: int
    invalid: int
    votes: dict[str, int]


class IterationDraw(TypedDict):
    ballots: int
    valid: int
    blank: int
    invalid: int
    votes: dict[str, int]
    blocs: dict[tuple[str, ...], int]
    regions: list[RegionDraw]


def expectation_preview(spec: ElectionSpecification) -> ExpectationPreview:
    """Analytical expectations for the baseline specification. Not a Monte Carlo run."""

    candidate_ids = [candidate.id for candidate in spec.candidates]
    return _expectations(
        spec,
        _segment_sizes(spec),
        spec.voting_method == "ranked_choice",
        candidate_ids,
    )


def spec_hash(spec: ElectionSpecification) -> str:
    payload = json.dumps(spec.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def run_simulation(
    spec: ElectionSpecification,
    settings: Settings,
    *,
    cancel_event: threading.Event | None = None,
    progress: ProgressCallback | None = None,
) -> SimulationOutput:
    ensure_valid(spec, settings)
    scenario_inputs: list[ScenarioSpec | None] = list(spec.scenarios) if spec.scenarios else [None]
    results: list[ScenarioResult] = []
    total = len(scenario_inputs)
    for index, scenario in enumerate(scenario_inputs):
        if cancel_event is not None and cancel_event.is_set():
            raise Cancelled()

        def scenario_progress(fraction: float, *, scenario_index: int = index) -> None:
            if progress is not None:
                progress((scenario_index + fraction) / total)

        results.append(
            _run_scenario(
                spec,
                scenario,
                cancel_event=cancel_event,
                progress=scenario_progress,
            )
        )
    comparisons = [compare_scenarios(results[0], other) for other in results[1:]]
    checks = [
        CheckResult(
            name="scenario_count",
            passed=len(results) == total,
            detail=f"Completed {len(results)} of {total} configured scenarios.",
        )
    ]
    return SimulationOutput(
        algorithm_version=ALGORITHM_VERSION,
        disclaimer=DISCLAIMER,
        spec_hash=spec_hash(spec),
        seed=spec.seed,
        iterations=spec.iterations,
        scenarios=results,
        reference_comparisons=comparisons,
        limitations=limitation_statements(spec),
        validation_checks=checks,
    )


def limitation_statements(spec: ElectionSpecification) -> list[str]:
    statements = [
        "Outputs are hypothetical draws from the configured model. "
        "They are not official results and not an empirical forecast.",
        "Monte Carlo standard errors and intervals measure simulation noise. "
        "They do not measure uncertainty about a real electorate.",
        "Conditional on the configured rates, participating voters are not simulated one by one. "
        "Turnout is binomial and valid ballots are multinomial.",
        "A mathematically consistent simulation can still be a poor description of a real election "
        "when the inputs are wrong.",
        "Independent draws omit unmodeled effects such as campaigns, strategic voting beyond the "
        "configured rules, and measurement error in the inputs.",
    ]
    if spec.turnout_shock_sd > 0 or any(
        scenario.turnout_shock_sd_override not in (None, 0) for scenario in spec.scenarios
    ):
        statements.append(
            "Shared turnout shocks are additive on the probability scale and clipped to [0, 1]. "
            "Regions still have independent binomial noise after the shared shock."
        )
    else:
        statements.append(
            "Regional turnout is independent. A common political shock is not included unless turnout_shock_sd is set."
        )
    if spec.voting_method == "ranked_choice" or any(
        scenario.voting_method_override == "ranked_choice" for scenario in spec.scenarios
    ):
        statements.append(
            "Ranked-choice results use instant-runoff on the configured rankings. "
            "Incomplete rankings exhaust when no continuing preference remains."
        )
    if any(item.source == "inferred" for item in spec.assumptions):
        statements.append(
            "Inferred assumptions are placeholders, not measurements. "
            "Changing them can change the result by more than simulation noise."
        )
    if spec.iterations < 30:
        statements.append(
            "Fewer than 30 iterations makes the normal approximation to the Monte Carlo mean rough. "
            "Medians, quantiles, and frequencies are still reported from the actual draws."
        )
    return statements


def _run_scenario(
    spec: ElectionSpecification,
    scenario: ScenarioSpec | None,
    *,
    cancel_event: threading.Event | None,
    progress: ProgressCallback,
) -> ScenarioResult:
    started = time.perf_counter()
    resolved, notes = apply_scenario(spec, scenario)
    candidate_ids = [candidate.id for candidate in resolved.candidates]
    names = {candidate.id: candidate.name for candidate in resolved.candidates}
    iterations = resolved.iterations
    rng = np.random.default_rng(np.random.PCG64(resolved.seed))
    use_blocs = resolved.voting_method == "ranked_choice"
    segment_sizes = _segment_sizes(resolved)
    expectations = _expectations(resolved, segment_sizes, use_blocs, candidate_ids)

    vote_matrix = np.zeros((iterations, len(candidate_ids)), dtype=np.int64)
    ballots = np.zeros(iterations, dtype=np.int64)
    valid = np.zeros(iterations, dtype=np.int64)
    blank = np.zeros(iterations, dtype=np.int64)
    invalid = np.zeros(iterations, dtype=np.int64)
    exhausted = np.zeros(iterations, dtype=np.int64)
    region_vote_sum = np.zeros((len(resolved.regions), len(candidate_ids)))
    region_vote_sq = np.zeros_like(region_vote_sum)
    region_ballot_sum = np.zeros(len(resolved.regions))
    region_ballot_sq = np.zeros(len(resolved.regions))
    region_valid_sum = np.zeros(len(resolved.regions))
    region_blank_sum = np.zeros(len(resolved.regions))
    region_invalid_sum = np.zeros(len(resolved.regions))
    sole_wins = {candidate_id: 0 for candidate_id in candidate_ids}
    tie_counts = {candidate_id: 0 for candidate_id in candidate_ids}
    seat_counters: dict[str, Counter[int]] = {candidate_id: Counter() for candidate_id in candidate_ids}
    seat_sum = {candidate_id: 0.0 for candidate_id in candidate_ids}
    second_round_sum = {candidate_id: 0.0 for candidate_id in candidate_ids}
    runoff_iterations = 0
    single_rounds: list[RoundTrace] | None = [] if iterations == 1 else None
    unallocated_total = 0
    progress_step = max(1, iterations // 20)

    for iteration in range(iterations):
        if cancel_event is not None and cancel_event.is_set():
            raise Cancelled()
        draw = _draw_iteration(
            rng,
            resolved,
            candidate_ids,
            segment_sizes,
            use_blocs,
        )
        _check_draw(draw, resolved)
        vote_matrix[iteration, :] = [draw["votes"][candidate_id] for candidate_id in candidate_ids]
        ballots[iteration] = draw["ballots"]
        valid[iteration] = draw["valid"]
        blank[iteration] = draw["blank"]
        invalid[iteration] = draw["invalid"]
        for region_index, region_draw in enumerate(draw["regions"]):
            region_ballot_sum[region_index] += region_draw["ballots"]
            region_ballot_sq[region_index] += region_draw["ballots"] ** 2
            region_valid_sum[region_index] += region_draw["valid"]
            region_blank_sum[region_index] += region_draw["blank"]
            region_invalid_sum[region_index] += region_draw["invalid"]
            for candidate_index, candidate_id in enumerate(candidate_ids):
                count = region_draw["votes"][candidate_id]
                region_vote_sum[region_index, candidate_index] += count
                region_vote_sq[region_index, candidate_index] += count ** 2
        method_result = _apply_method(draw, resolved, candidate_ids, rng)
        _check_method(method_result, draw, resolved)
        unallocated_total += method_result.unallocated_seats
        exhausted[iteration] = method_result.exhausted
        if len(method_result.winner_ids) == 1:
            sole_wins[method_result.winner_ids[0]] += 1
        elif len(method_result.winner_ids) > 1:
            for winner_id in method_result.winner_ids:
                tie_counts[winner_id] += 1
        if method_result.seats is not None:
            for candidate_id, seats in method_result.seats.items():
                seat_sum[candidate_id] += seats
                seat_counters[candidate_id][seats] += 1
        if len(method_result.rounds) >= 2:
            runoff_iterations += 1
            second_votes = method_result.rounds[1]["votes"]
            for candidate_id in candidate_ids:
                second_round_sum[candidate_id] += float(second_votes.get(candidate_id, 0))
        if single_rounds is not None:
            single_rounds = [_round_trace(item) for item in method_result.rounds]
        if iteration % progress_step == 0:
            progress(iteration / iterations)

    progress(1.0)
    summaries = _candidate_summaries(
        candidate_ids,
        names,
        vote_matrix,
        valid,
        sole_wins,
        tie_counts,
        seat_sum if resolved.voting_method == "dhondt" else None,
        seat_counters if resolved.voting_method == "dhondt" else None,
        resolved.reporting.include_histograms,
        resolved.reporting.histogram_bins,
    )
    regional = _regional_summaries(
        resolved,
        candidate_ids,
        iterations,
        region_vote_sum,
        region_vote_sq,
        region_ballot_sum,
        region_ballot_sq,
        region_valid_sum,
        region_blank_sum,
        region_invalid_sum,
        expectations,
        segment_sizes,
    )
    margin = _margins(vote_matrix)
    checks = [
        CheckResult(
            name="non_negative_counts",
            passed=True,
            detail="Every checked iteration had non-negative ballots and votes.",
        ),
        CheckResult(
            name="ballot_reconciliation",
            passed=True,
            detail="Valid, blank, and invalid ballots summed to ballots cast in every iteration.",
        ),
        CheckResult(
            name="vote_reconciliation",
            passed=True,
            detail="Candidate votes summed to valid ballots in every iteration.",
        ),
        CheckResult(
            name="population_bound",
            passed=True,
            detail="Ballots cast never exceeded eligible voters.",
        ),
        CheckResult(
            name="seat_reconciliation",
            passed=True,
            detail=(
                "Seat totals plus explicitly unallocated seats matched the request. "
                f"Unallocated seat-iterations: {unallocated_total}."
                if resolved.voting_method == "dhondt"
                else "This method does not allocate a multi-seat vector."
            ),
        ),
        CheckResult(
            name="no_dropped_units",
            passed=len(regional) == len(resolved.regions) and len(summaries) == len(candidate_ids),
            detail="Every configured region and candidate appears in the summary.",
        ),
    ]
    if not checks[-1].passed:
        raise InvariantError("A region or candidate was missing from the summary.")
    eligible = sum(region.eligible_voters for region in resolved.regions)
    mean_ballots = float(np.mean(ballots))
    return ScenarioResult(
        scenario_id=scenario.id if scenario else "baseline",
        scenario_name=scenario.name if scenario else "Baseline",
        parameter_notes=notes,
        voting_method=resolved.voting_method,
        seats_requested=resolved.seats,
        iterations_completed=iterations,
        runtime_seconds=time.perf_counter() - started,
        eligible_voters=eligible,
        expected_ballots=expectations["ballots"],
        expected_valid=expectations["valid"],
        expected_votes=expectations["votes"],
        expectation_note=expectations["note"],
        mean_ballots=mean_ballots,
        median_ballots=float(np.median(ballots)),
        std_ballots=sample_std(ballots),
        mean_turnout_rate=(mean_ballots / eligible) if eligible else None,
        mean_valid=float(np.mean(valid)),
        mean_blank=float(np.mean(blank)),
        mean_invalid=float(np.mean(invalid)),
        candidates=summaries,
        ranking_by_mean_votes=_rank_candidates(candidate_ids, vote_matrix),
        regional=regional if resolved.reporting.include_regional else [],
        regional_note=(
            "Regional mean shares are ratios of mean votes to mean valid ballots."
            if resolved.reporting.include_regional
            else "Regional breakdown omitted by reporting.include_regional."
        ),
        vote_histograms=_vote_histograms(vote_matrix, candidate_ids, resolved),
        margin_histogram=(
            histogram(margin, resolved.reporting.histogram_bins)
            if resolved.reporting.include_histograms
            else None
        ),
        mean_exhausted_ballots=float(np.mean(exhausted)),
        runoff_iterations=runoff_iterations,
        mean_second_round_votes=(
            {candidate_id: second_round_sum[candidate_id] / iterations for candidate_id in candidate_ids}
            if resolved.voting_method == "two_round"
            else None
        ),
        single_iteration_rounds=single_rounds,
        validation_checks=checks,
    )


def _rank_candidates(candidate_ids: list[str], vote_matrix: np.ndarray) -> list[str]:
    means = {
        candidate_id: float(np.mean(vote_matrix[:, index]))
        for index, candidate_id in enumerate(candidate_ids)
    }
    return sorted(candidate_ids, key=lambda candidate_id: (-means[candidate_id], candidate_id))


def _vote_histograms(
    vote_matrix: np.ndarray,
    candidate_ids: list[str],
    spec: ElectionSpecification,
) -> dict[str, Histogram]:
    output: dict[str, Histogram] = {}
    for index, candidate_id in enumerate(candidate_ids):
        if spec.reporting.include_histograms:
            output[candidate_id] = histogram(
                vote_matrix[:, index].astype(float),
                spec.reporting.histogram_bins,
            )
        else:
            output[candidate_id] = Histogram(
                edges=[],
                counts=[],
                note="Histograms omitted by reporting options.",
            )
    return output


def _candidate_summaries(
    candidate_ids: list[str],
    names: dict[str, str],
    vote_matrix: np.ndarray,
    valid: np.ndarray,
    sole_wins: dict[str, int],
    tie_counts: dict[str, int],
    seat_sum: dict[str, float] | None,
    seat_counters: dict[str, Counter[int]] | None,
    include_histograms: bool,
    bins: int,
) -> list[CandidateSummary]:
    del include_histograms, bins
    iterations = vote_matrix.shape[0]
    shares = np.full(vote_matrix.shape, np.nan, dtype=float)
    positive = valid > 0
    if np.any(positive):
        shares[positive, :] = vote_matrix[positive, :] / valid[positive, None]
    summaries: list[CandidateSummary] = []
    for index, candidate_id in enumerate(candidate_ids):
        column = vote_matrix[:, index].astype(float)
        share_column = shares[:, index]
        successes = sole_wins[candidate_id]
        frequency = successes / iterations if iterations else 0.0
        seat_frequencies = None
        mean_seats = None
        if seat_sum is not None and seat_counters is not None:
            mean_seats = seat_sum[candidate_id] / iterations if iterations else 0.0
            seat_frequencies = {
                str(seats): count / iterations for seats, count in sorted(seat_counters[candidate_id].items())
            }
        summaries.append(
            CandidateSummary(
                id=candidate_id,
                name=names[candidate_id],
                mean_votes=float(np.mean(column)) if iterations else 0.0,
                median_votes=float(np.median(column)) if iterations else 0.0,
                std_votes=sample_std(column),
                vote_quantiles=quantiles(column),
                vote_mean_interval=mean_interval(column),
                mean_share=nan_mean(share_column),
                median_share=float(np.nanmedian(share_column)) if np.any(~np.isnan(share_column)) else None,
                std_share=nan_std(share_column),
                share_quantiles=nan_quantiles(share_column),
                sole_win_frequency=frequency,
                tie_frequency=tie_counts[candidate_id] / iterations if iterations else 0.0,
                sole_win_frequency_se=frequency_standard_error(frequency, iterations),
                sole_win_frequency_interval=wilson_interval(successes, iterations),
                mean_seats=mean_seats,
                seat_frequencies=seat_frequencies,
            )
        )
    return summaries


def _regional_summaries(
    spec: ElectionSpecification,
    candidate_ids: list[str],
    iterations: int,
    vote_sum: np.ndarray,
    vote_sq: np.ndarray,
    ballot_sum: np.ndarray,
    ballot_sq: np.ndarray,
    valid_sum: np.ndarray,
    blank_sum: np.ndarray,
    invalid_sum: np.ndarray,
    expectations: ExpectationPreview,
    segment_sizes: dict[str, list[int]],
) -> list[RegionalSummary]:
    del expectations
    regional_expectations = _regional_expectation_rows(spec, segment_sizes, candidate_ids)
    rows: list[RegionalSummary] = []
    for index, region in enumerate(spec.regions):
        mean_ballots = ballot_sum[index] / iterations
        mean_valid = valid_sum[index] / iterations
        mean_votes = {
            candidate_id: float(vote_sum[index, candidate_index] / iterations)
            for candidate_index, candidate_id in enumerate(candidate_ids)
        }
        std_votes = {}
        for candidate_index, candidate_id in enumerate(candidate_ids):
            std_votes[candidate_id] = _second_moment_std(
                vote_sum[index, candidate_index],
                vote_sq[index, candidate_index],
                iterations,
            )
        expected = regional_expectations[region.id]
        rows.append(
            RegionalSummary(
                id=region.id,
                name=region.name,
                eligible_voters=region.eligible_voters,
                expected_ballots=expected["ballots"],
                expected_ballots_label=expected["label"],
                analytical_turnout_variance=expected["variance"],
                mean_ballots=float(mean_ballots),
                std_ballots=_second_moment_std(ballot_sum[index], ballot_sq[index], iterations),
                mean_turnout_rate=(
                    float(mean_ballots / region.eligible_voters) if region.eligible_voters else None
                ),
                mean_valid=float(mean_valid),
                mean_blank=float(blank_sum[index] / iterations),
                mean_invalid=float(invalid_sum[index] / iterations),
                mean_votes=mean_votes,
                std_votes=std_votes,
                mean_shares={
                    candidate_id: (votes / mean_valid if mean_valid > 0 else None)
                    for candidate_id, votes in mean_votes.items()
                },
            )
        )
    return rows


def _second_moment_std(total: float, total_squares: float, iterations: int) -> float:
    if iterations < 2:
        return 0.0
    mean = total / iterations
    variance = (total_squares - iterations * mean * mean) / (iterations - 1)
    return float(math_sqrt(max(0.0, variance)))


def math_sqrt(value: float) -> float:
    return value**0.5


def _margins(vote_matrix: np.ndarray) -> np.ndarray:
    if vote_matrix.shape[1] == 0:
        return np.zeros(vote_matrix.shape[0])
    ordered = np.sort(vote_matrix, axis=1)
    if ordered.shape[1] == 1:
        return ordered[:, 0].astype(float)
    return (ordered[:, -1] - ordered[:, -2]).astype(float)


def _round_trace(item: dict[str, Any]) -> RoundTrace:
    votes = item["votes"]
    eliminated = item["eliminated"]
    return RoundTrace(
        round_number=int(item["round_number"]),
        votes={str(key): int(value) for key, value in votes.items()},
        continuing_ballots=int(item["continuing_ballots"]),
        exhausted_ballots=int(item["exhausted_ballots"]),
        eliminated=[str(candidate) for candidate in eliminated],
        note=str(item.get("note", "")),
    )


def _segment_sizes(spec: ElectionSpecification) -> dict[str, list[int]]:
    sizes: dict[str, list[int]] = {}
    for region in spec.regions:
        if region.segments:
            sizes[region.id] = largest_remainder(
                region.eligible_voters,
                [segment.share for segment in region.segments],
            )
    return sizes


def _expectations(
    spec: ElectionSpecification,
    segment_sizes: dict[str, list[int]],
    use_blocs: bool,
    candidate_ids: list[str],
) -> ExpectationPreview:
    if spec.turnout_shock_sd > 0:
        return {
            "ballots": None,
            "valid": None,
            "votes": None,
            "note": (
                "Closed-form expectations are withheld because the shared turnout shock is clipped. "
                "Clipping makes E[turnout] differ from the configured probability."
            ),
        }
    expected_ballots = 0.0
    expected_valid = 0.0
    expected_votes = {candidate_id: 0.0 for candidate_id in candidate_ids}
    for region in spec.regions:
        units = _units(region, segment_sizes)
        for eligible, turnout, blank_rate, invalid_rate, preferences, blocs in units:
            ballots_mean = eligible * turnout
            valid_probability = 1.0 - blank_rate - invalid_rate
            valid_mean = ballots_mean * valid_probability
            expected_ballots += ballots_mean
            expected_valid += valid_mean
            sampling = _sampling_preferences(preferences, candidate_ids, blocs, use_blocs)
            for candidate_id in candidate_ids:
                expected_votes[candidate_id] += valid_mean * sampling[candidate_id]
    return {
        "ballots": expected_ballots,
        "valid": expected_valid,
        "votes": expected_votes,
        "note": (
            "Expected values use E[ballots] = N × turnout and E[votes] = E[valid] × preference. "
            "They can be fractional. They are not observed integer counts. "
            "Segment sizes are the fixed largest-remainder allocation."
        ),
    }


def _regional_expectation_rows(
    spec: ElectionSpecification,
    segment_sizes: dict[str, list[int]],
    candidate_ids: list[str],
) -> dict[str, RegionalExpectation]:
    del candidate_ids
    rows: dict[str, RegionalExpectation] = {}
    shocked = spec.turnout_shock_sd > 0
    for region in spec.regions:
        if shocked:
            rows[region.id] = {
                "ballots": None,
                "variance": None,
                "label": "Withheld because a clipped turnout shock is configured.",
            }
            continue
        expected = 0.0
        variance = 0.0
        units = _units(region, segment_sizes)
        for eligible, turnout, _blank, _invalid, _prefs, _blocs in units:
            expected += eligible * turnout
            variance += float(binom.var(eligible, turnout))
        rows[region.id] = {
            "ballots": expected,
            "variance": variance,
            "label": "Expected ballot count under independent binomial turnout. Not an observed count.",
        }
    return rows


def _units(
    region: RegionSpec,
    segment_sizes: dict[str, list[int]],
) -> list[tuple[int, float, float, float, dict[str, float], list[RankingBloc] | None]]:
    if region.segments:
        sizes = segment_sizes[region.id]
        return [
            (
                size,
                segment.turnout_probability,
                segment.blank_rate,
                segment.invalid_rate,
                segment.preferences,
                segment.ranking_blocs,
            )
            for size, segment in zip(sizes, region.segments, strict=True)
        ]
    return [
        (
            region.eligible_voters,
            region.turnout_probability,
            region.blank_rate,
            region.invalid_rate,
            region.preferences,
            region.ranking_blocs,
        )
    ]


def _sampling_preferences(
    preferences: dict[str, float],
    candidate_ids: list[str],
    blocs: list[RankingBloc] | None,
    use_blocs: bool,
) -> dict[str, float]:
    if use_blocs and blocs:
        implied = {candidate_id: 0.0 for candidate_id in candidate_ids}
        for bloc in blocs:
            implied[bloc.ranking[0]] += bloc.weight
        return implied
    return {candidate_id: preferences[candidate_id] for candidate_id in candidate_ids}


def _draw_iteration(
    rng: np.random.Generator,
    spec: ElectionSpecification,
    candidate_ids: list[str],
    segment_sizes: dict[str, list[int]],
    use_blocs: bool,
) -> IterationDraw:
    shock = float(rng.normal(0.0, spec.turnout_shock_sd)) if spec.turnout_shock_sd > 0 else 0.0
    regions: list[RegionDraw] = []
    votes = {candidate_id: 0 for candidate_id in candidate_ids}
    blocs: dict[tuple[str, ...], int] = {}
    ballots = valid = blank = invalid = 0
    for region in spec.regions:
        region_votes = {candidate_id: 0 for candidate_id in candidate_ids}
        region_ballots = region_valid = region_blank = region_invalid = 0
        for eligible, turnout, blank_rate, invalid_rate, preferences, ranking in _units(
            region, segment_sizes
        ):
            draw = _draw_unit(
                rng,
                eligible,
                clip_probability(turnout + shock),
                blank_rate,
                invalid_rate,
                preferences,
                candidate_ids,
                ranking,
                use_blocs,
            )
            region_ballots += draw["ballots"]
            region_valid += draw["valid"]
            region_blank += draw["blank"]
            region_invalid += draw["invalid"]
            for candidate_id, count in draw["votes"].items():
                region_votes[candidate_id] += count
                votes[candidate_id] += count
            for key, count in draw["blocs"].items():
                blocs[key] = blocs.get(key, 0) + count
        if region_ballots > region.eligible_voters:
            raise InvariantError(f"Region {region.id} produced more ballots than eligible voters.")
        regions.append(
            {
                "id": region.id,
                "ballots": region_ballots,
                "valid": region_valid,
                "blank": region_blank,
                "invalid": region_invalid,
                "votes": region_votes,
            }
        )
        ballots += region_ballots
        valid += region_valid
        blank += region_blank
        invalid += region_invalid
    return {
        "ballots": ballots,
        "valid": valid,
        "blank": blank,
        "invalid": invalid,
        "votes": votes,
        "blocs": blocs,
        "regions": regions,
    }


def _draw_unit(
    rng: np.random.Generator,
    eligible: int,
    turnout: float,
    blank_rate: float,
    invalid_rate: float,
    preferences: dict[str, float],
    candidate_ids: list[str],
    blocs: list[RankingBloc] | None,
    use_blocs: bool,
) -> UnitDraw:
    ballots = int(rng.binomial(eligible, turnout))
    votes = {candidate_id: 0 for candidate_id in candidate_ids}
    bloc_counts: dict[tuple[str, ...], int] = {}
    if ballots == 0:
        return {
            "ballots": 0,
            "valid": 0,
            "blank": 0,
            "invalid": 0,
            "votes": votes,
            "blocs": bloc_counts,
        }
    valid_probability = 1.0 - blank_rate - invalid_rate
    composition = rng.multinomial(
        ballots,
        as_simplex([valid_probability, blank_rate, invalid_rate]),
    )
    valid = int(composition[0])
    blank = int(composition[1])
    invalid = int(composition[2])
    if valid > 0:
        if use_blocs and blocs:
            weights = as_simplex([bloc.weight for bloc in blocs])
            drawn = rng.multinomial(valid, weights)
            for bloc, count_value in zip(blocs, drawn, strict=True):
                count = int(count_value)
                if count == 0:
                    continue
                bloc_counts[tuple(bloc.ranking)] = bloc_counts.get(tuple(bloc.ranking), 0) + count
                votes[bloc.ranking[0]] += count
        else:
            weights = as_simplex([preferences[candidate_id] for candidate_id in candidate_ids])
            drawn = rng.multinomial(valid, weights)
            for candidate_id, count_value in zip(candidate_ids, drawn, strict=True):
                count = int(count_value)
                votes[candidate_id] = count
                if use_blocs and count:
                    bloc_counts[(candidate_id,)] = count
    return {
        "ballots": ballots,
        "valid": valid,
        "blank": blank,
        "invalid": invalid,
        "votes": votes,
        "blocs": bloc_counts,
    }


def _check_draw(draw: IterationDraw, spec: ElectionSpecification) -> None:
    ballots = draw["ballots"]
    valid = draw["valid"]
    blank = draw["blank"]
    invalid = draw["invalid"]
    votes = draw["votes"]
    if min(ballots, valid, blank, invalid) < 0 or any(value < 0 for value in votes.values()):
        raise InvariantError("A negative count was produced.")
    if valid + blank + invalid != ballots:
        raise InvariantError("Ballot types did not reconcile with ballots cast.")
    if sum(votes.values()) != valid:
        raise InvariantError("Candidate votes did not reconcile with valid ballots.")
    eligible = sum(region.eligible_voters for region in spec.regions)
    if ballots > eligible:
        raise InvariantError("Ballots cast exceeded eligible voters.")
    if len(draw["regions"]) != len(spec.regions):
        raise InvariantError("A region was dropped from the iteration.")


def _apply_method(
    draw: IterationDraw,
    spec: ElectionSpecification,
    candidate_ids: list[str],
    rng: np.random.Generator,
) -> MethodResult:
    votes = {candidate_id: draw["votes"][candidate_id] for candidate_id in candidate_ids}
    method = spec.voting_method
    if method == "plurality":
        return plurality(votes)
    if method == "two_round":
        return two_round(votes, spec.runoff_transfers, spec.runoff_threshold, rng, candidate_ids)
    if method == "ranked_choice":
        bloc_counts = dict(draw["blocs"])
        return instant_runoff(bloc_counts, candidate_ids)
    if method == "dhondt":
        if spec.seats is None:
            raise InvariantError("D'Hondt reached execution without seats.")
        return dhondt(votes, spec.seats)
    raise InvariantError(f"Unsupported voting method {method}.")


def _check_method(
    result: MethodResult,
    draw: IterationDraw,
    spec: ElectionSpecification,
) -> None:
    votes = draw["votes"]
    if any(int(value) < 0 for value in votes.values()):
        raise InvariantError("Negative votes reached the election method.")
    if spec.voting_method == "dhondt":
        if result.seats is None or spec.seats is None:
            raise InvariantError("D'Hondt did not return a seat allocation.")
        if any(seats < 0 for seats in result.seats.values()):
            raise InvariantError("Negative seat allocation.")
        if sum(result.seats.values()) + result.unallocated_seats != spec.seats:
            raise InvariantError("Seat allocation did not reconcile.")
        if result.unallocated_seats and not result.seat_explanation:
            raise InvariantError("Unallocated seats require an explanation.")
    elif result.seats is not None:
        raise InvariantError("A single-winner method returned a seat vector.")
    known = set(votes)
    if set(result.ranking) != known and set(result.ranking) - known:
        raise InvariantError("The result ranking named an unknown candidate.")
