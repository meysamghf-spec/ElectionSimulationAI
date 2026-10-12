"""Cross-field validation. Invalid inputs are rejected, not rewritten."""

from __future__ import annotations

from collections.abc import Callable

from app.config import Settings
from app.engine.population import PROBABILITY_TOLERANCE, probability_issue
from app.errors import SpecError
from app.schemas.spec import (
    ElectionSpecification,
    RankingBloc,
    RegionSpec,
    ScenarioSpec,
    SegmentSpec,
    ValidationIssue,
    ValidationReport,
    VotingMethod,
)

SINGLE_WINNER: set[VotingMethod] = {"plurality", "two_round", "ranked_choice"}


def validate_spec(spec: ElectionSpecification, settings: Settings) -> ValidationReport:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    def error(field: str, message: str) -> None:
        errors.append(ValidationIssue(field=field, message=message, severity="error"))

    def warn(field: str, message: str) -> None:
        warnings.append(ValidationIssue(field=field, message=message, severity="warning"))

    if spec.iterations > settings.max_iterations:
        error(
            "iterations",
            f"Iterations {spec.iterations} exceed the configured limit of {settings.max_iterations}.",
        )
    if len(spec.candidates) > settings.max_candidates:
        error(
            "candidates",
            f"{len(spec.candidates)} candidates exceed the configured limit of {settings.max_candidates}.",
        )
    if len(spec.regions) > settings.max_regions:
        error(
            "regions",
            f"{len(spec.regions)} regions exceed the configured limit of {settings.max_regions}.",
        )
    if len(spec.scenarios) > settings.max_scenarios:
        error(
            "scenarios",
            f"{len(spec.scenarios)} scenarios exceed the configured limit of {settings.max_scenarios}.",
        )

    candidate_ids = [candidate.id for candidate in spec.candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        error("candidates", "Candidate ids must be unique.")
    names = [candidate.name for candidate in spec.candidates]
    if len(names) != len(set(names)):
        warn("candidates", "Two candidates share a display name. Ids still distinguish them.")
    candidate_set = set(candidate_ids)

    region_ids = [region.id for region in spec.regions]
    if len(region_ids) != len(set(region_ids)):
        error("regions", "Region ids must be unique.")

    scenario_ids = [scenario.id for scenario in spec.scenarios]
    if len(scenario_ids) != len(set(scenario_ids)):
        error("scenarios", "Scenario ids must be unique.")

    _check_method(spec.voting_method, spec.seats, "seats", error)
    _check_transfers(spec, candidate_set, error)

    total_eligible = 0
    for region in spec.regions:
        total_eligible += region.eligible_voters
        _check_region(region, candidate_set, spec.voting_method, error, warn)

    if total_eligible == 0:
        warn(
            "regions",
            "Eligible voters sum to zero. The simulation will return empty counts and no winner.",
        )
    if all(region.turnout_probability == 0 and not region.segments for region in spec.regions):
        warn("turnout_probability", "Every region has turnout probability 0, so no ballots will be cast.")

    for scenario in spec.scenarios:
        _check_scenario(spec, scenario, candidate_set, error, warn)

    if spec.voting_method == "two_round" and spec.runoff_transfers is None:
        warn(
            "runoff_transfers",
            "No second-preference transfers were configured. The runoff uses the "
            "retention-abstention rule: finalists keep first-round votes and other ballots abstain.",
        )
    if spec.voting_method == "ranked_choice" and all(
        not region.ranking_blocs and not (region.segments and any(segment.ranking_blocs for segment in region.segments))
        for region in spec.regions
    ):
        warn(
            "ranking_blocs",
            "No ranking blocs were configured. Ranked-choice will use first preferences only, "
            "so a ballot is exhausted when its first choice is eliminated.",
        )
    if spec.turnout_shock_sd > 0:
        warn(
            "turnout_shock_sd",
            "A shared normal shock is added to every turnout probability and then clipped to [0, 1]. "
            "Clipping means the expected turnout can differ from the configured probability.",
        )
    inferred = [item for item in spec.assumptions if item.source == "inferred"]
    if inferred:
        warn(
            "assumptions",
            f"{len(inferred)} assumption(s) are inferred rather than extracted from the prompt or supplied as data.",
        )
    if spec.empirical_data and inferred:
        warn(
            "empirical_data",
            "empirical_data is true while some assumptions are inferred. "
            "Inferred values are not measurements.",
        )
    return ValidationReport(valid=not errors, errors=errors, warnings=warnings)


def ensure_valid(spec: ElectionSpecification, settings: Settings) -> ValidationReport:
    report = validate_spec(spec, settings)
    if not report.valid:
        raise SpecError(
            "The election specification is invalid.",
            details=[{"field": issue.field, "message": issue.message} for issue in report.errors],
        )
    return report


def _check_method(
    method: VotingMethod,
    seats: int | None,
    field: str,
    error: Callable[[str, str], None],
) -> None:
    if method == "dhondt":
        if seats is None:
            error(field, "D'Hondt requires seats. The server will not assume a seat total.")
        return
    if seats not in (None, 1):
        error(
            field,
            f"{method} is implemented as a single-winner method. "
            "Use seats of 1 or omit seats. Use dhondt for multi-seat allocation. "
            "The server will not approximate a different electoral system.",
        )


def _check_transfers(
    spec: ElectionSpecification,
    candidate_set: set[str],
    error: Callable[[str, str], None],
) -> None:
    transfers = spec.runoff_transfers
    if transfers is None:
        return
    if set(transfers) != candidate_set:
        error(
            "runoff_transfers",
            "runoff_transfers must contain exactly one row for every candidate id.",
        )
        return
    for source, row in transfers.items():
        unknown = set(row) - candidate_set
        if unknown:
            error("runoff_transfers", f"Transfer row {source} names unknown candidates: {sorted(unknown)}.")
        if any(value < 0 for value in row.values()):
            error("runoff_transfers", f"Transfer row {source} contains a negative probability.")
        if sum(row.values()) > 1 + PROBABILITY_TOLERANCE:
            error(
                "runoff_transfers",
                f"Transfer row {source} sums to more than 1. The remainder must be abstention, "
                "and the server will not rescale a row that already exceeds 1.",
            )


def _check_region(
    region: RegionSpec,
    candidate_set: set[str],
    method: VotingMethod,
    error: Callable[[str, str], None],
    warn: Callable[[str, str], None],
) -> None:
    prefix = f"regions.{region.id}"
    if region.blank_rate + region.invalid_rate > 1 + 1e-12:
        error(prefix, "blank_rate + invalid_rate cannot exceed 1. They are conditional on a cast ballot.")
    _check_preference_map(region.preferences, candidate_set, f"{prefix}.preferences", error)
    if region.ranking_blocs is not None:
        _check_blocs(region.ranking_blocs, candidate_set, f"{prefix}.ranking_blocs", error)
        if method == "ranked_choice":
            _warn_bloc_mismatch(region.ranking_blocs, region.preferences, prefix, warn)
    if region.segments:
        shares = [segment.share for segment in region.segments]
        issue = probability_issue(shares, f"{prefix}.segments shares")
        if issue:
            error(prefix, issue)
        segment_ids = [segment.id for segment in region.segments]
        if len(segment_ids) != len(set(segment_ids)):
            error(prefix, "Segment ids must be unique within a region.")
        for segment in region.segments:
            _check_segment(segment, candidate_set, f"{prefix}.segments.{segment.id}", error, warn, method)
        warn(
            prefix,
            "Segment populations are fixed with the largest-remainder method. "
            "Region-level turnout and preferences are not used for sampling when segments exist.",
        )


def _check_segment(
    segment: SegmentSpec,
    candidate_set: set[str],
    field: str,
    error: Callable[[str, str], None],
    warn: Callable[[str, str], None],
    method: VotingMethod,
) -> None:
    if segment.blank_rate + segment.invalid_rate > 1 + 1e-12:
        error(field, "blank_rate + invalid_rate cannot exceed 1.")
    _check_preference_map(segment.preferences, candidate_set, f"{field}.preferences", error)
    if segment.ranking_blocs is not None:
        _check_blocs(segment.ranking_blocs, candidate_set, f"{field}.ranking_blocs", error)
        if method == "ranked_choice":
            _warn_bloc_mismatch(segment.ranking_blocs, segment.preferences, field, warn)


def _check_preference_map(
    preferences: dict[str, float],
    candidate_set: set[str],
    field: str,
    error: Callable[[str, str], None],
) -> None:
    if set(preferences) != candidate_set:
        error(field, "Preferences must contain exactly the configured candidate ids, and no others.")
        return
    issue = probability_issue([preferences[candidate] for candidate in sorted(preferences)], field)
    if issue:
        error(field, issue)


def _check_blocs(
    blocs: list[RankingBloc],
    candidate_set: set[str],
    field: str,
    error: Callable[[str, str], None],
) -> None:
    if not blocs:
        error(field, "ranking_blocs is empty. Omit the field or provide at least one bloc.")
        return
    issue = probability_issue([bloc.weight for bloc in blocs], field)
    if issue:
        error(field, issue)
    for index, bloc in enumerate(blocs):
        if len(bloc.ranking) != len(set(bloc.ranking)):
            error(field, f"Bloc {index} repeats a candidate in its ranking.")
        unknown = set(bloc.ranking) - candidate_set
        if unknown:
            error(field, f"Bloc {index} names unknown candidates: {sorted(unknown)}.")


def _warn_bloc_mismatch(
    blocs: list[RankingBloc],
    preferences: dict[str, float],
    field: str,
    warn: Callable[[str, str], None],
) -> None:
    implied = {candidate: 0.0 for candidate in preferences}
    for bloc in blocs:
        first = bloc.ranking[0]
        if first in implied:
            implied[first] += bloc.weight
    for candidate, probability in preferences.items():
        if abs(implied.get(candidate, 0.0) - probability) > 1e-6:
            warn(
                field,
                "First-choice probabilities and ranking-bloc weights disagree. "
                "Ranked-choice sampling uses the blocs. Plurality sampling uses preferences.",
            )
            return


def _check_scenario(
    spec: ElectionSpecification,
    scenario: ScenarioSpec,
    candidate_set: set[str],
    error: Callable[[str, str], None],
    warn: Callable[[str, str], None],
) -> None:
    field = f"scenarios.{scenario.id}"
    method = scenario.voting_method_override or spec.voting_method
    seats = spec.seats if scenario.seats_override is None else scenario.seats_override
    _check_method(method, seats, f"{field}.seats", error)
    if scenario.turnout_by_region:
        unknown = set(scenario.turnout_by_region) - {region.id for region in spec.regions}
        if unknown:
            error(field, f"turnout_by_region names unknown regions: {sorted(unknown)}.")
        for region_id, turnout in scenario.turnout_by_region.items():
            if turnout < 0 or turnout > 1:
                error(field, f"Turnout for {region_id} must be between 0 and 1.")
    if scenario.preference_overrides:
        unknown = set(scenario.preference_overrides) - {region.id for region in spec.regions}
        if unknown:
            error(field, f"preference_overrides names unknown regions: {sorted(unknown)}.")
        for region_id, preferences in scenario.preference_overrides.items():
            _check_preference_map(preferences, candidate_set, f"{field}.preferences.{region_id}", error)
    for region in spec.regions:
        blank = region.blank_rate if scenario.blank_rate_override is None else scenario.blank_rate_override
        invalid = region.invalid_rate if scenario.invalid_rate_override is None else scenario.invalid_rate_override
        if blank + invalid > 1 + 1e-12:
            error(field, f"Scenario overrides make blank + invalid exceed 1 in region {region.id}.")
        if region.segments:
            for segment in region.segments:
                seg_blank = segment.blank_rate if scenario.blank_rate_override is None else scenario.blank_rate_override
                seg_invalid = (
                    segment.invalid_rate
                    if scenario.invalid_rate_override is None
                    else scenario.invalid_rate_override
                )
                if seg_blank + seg_invalid > 1 + 1e-12:
                    error(
                        field,
                        f"Scenario overrides make blank + invalid exceed 1 in segment {segment.id}.",
                    )
    if scenario.voting_method_override == "two_round" and spec.runoff_transfers is None:
        warn(
            field,
            "This scenario uses two-round voting without transfer probabilities, "
            "so retention-abstention applies.",
        )
