"""Result models produced by the simulation engine and returned by the API."""

from typing import Literal

from pydantic import BaseModel, Field


class Histogram(BaseModel):
    edges: list[float]
    counts: list[int]
    note: str


class IntervalEstimate(BaseModel):
    low: float
    high: float
    level: float = 0.95
    method: str
    meaning: str


class CandidateSummary(BaseModel):
    id: str
    name: str
    mean_votes: float
    median_votes: float
    std_votes: float
    vote_quantiles: dict[str, float]
    vote_mean_interval: IntervalEstimate
    mean_share: float | None
    median_share: float | None
    std_share: float | None
    share_quantiles: dict[str, float] | None
    sole_win_frequency: float
    tie_frequency: float
    sole_win_frequency_se: float
    sole_win_frequency_interval: IntervalEstimate
    mean_seats: float | None = None
    seat_frequencies: dict[str, float] | None = None


class RegionalSummary(BaseModel):
    id: str
    name: str
    eligible_voters: int
    expected_ballots: float | None
    expected_ballots_label: str
    analytical_turnout_variance: float | None
    mean_ballots: float
    std_ballots: float
    mean_turnout_rate: float | None
    mean_valid: float
    mean_blank: float
    mean_invalid: float
    mean_votes: dict[str, float]
    std_votes: dict[str, float]
    mean_shares: dict[str, float | None]


class RoundTrace(BaseModel):
    round_number: int
    votes: dict[str, int]
    continuing_ballots: int
    exhausted_ballots: int
    eliminated: list[str] = Field(default_factory=list)
    note: str = ""


class ScenarioResult(BaseModel):
    scenario_id: str
    scenario_name: str
    parameter_notes: list[str]
    voting_method: str
    seats_requested: int | None
    iterations_completed: int
    runtime_seconds: float
    eligible_voters: int
    expected_ballots: float | None
    expected_valid: float | None
    expected_votes: dict[str, float] | None
    expectation_note: str
    mean_ballots: float
    median_ballots: float
    std_ballots: float
    mean_turnout_rate: float | None
    mean_valid: float
    mean_blank: float
    mean_invalid: float
    candidates: list[CandidateSummary]
    ranking_by_mean_votes: list[str]
    regional: list[RegionalSummary]
    regional_note: str
    vote_histograms: dict[str, Histogram]
    margin_histogram: Histogram | None
    mean_exhausted_ballots: float
    runoff_iterations: int
    mean_second_round_votes: dict[str, float] | None
    single_iteration_rounds: list[RoundTrace] | None
    validation_checks: list["CheckResult"]
    hypothetical: Literal[True] = True


class CheckResult(BaseModel):
    name: str
    passed: bool
    detail: str


class CandidateDelta(BaseModel):
    id: str
    name: str
    left_mean_votes: float
    right_mean_votes: float
    vote_difference: float
    left_mean_share: float | None
    right_mean_share: float | None
    percentage_point_difference: float | None
    relative_share_change: float | None
    left_sole_win_frequency: float
    right_sole_win_frequency: float
    sole_win_frequency_difference: float
    left_mean_seats: float | None
    right_mean_seats: float | None


class ComparisonResult(BaseModel):
    left_scenario_id: str
    left_scenario_name: str
    right_scenario_id: str
    right_scenario_name: str
    explanation: str
    eligible_voters_left: int
    eligible_voters_right: int
    mean_ballots_difference: float
    turnout_percentage_point_difference: float | None
    mean_valid_difference: float
    mean_blank_difference: float
    mean_invalid_difference: float
    candidates: list[CandidateDelta]


class SimulationOutput(BaseModel):
    algorithm_version: str
    hypothetical: Literal[True] = True
    disclaimer: str
    spec_hash: str
    seed: int
    iterations: int
    scenarios: list[ScenarioResult]
    reference_comparisons: list[ComparisonResult]
    limitations: list[str]
    validation_checks: list[CheckResult]


class SensitivityVariation(BaseModel):
    parameter: str
    change: str
    applied: bool
    reason: str
    held_constant: list[str]
    max_absolute_share_percentage_points: float | None
    leading_candidate_id: str | None
    leading_share_percentage_point_change: float | None
    mean_ballots: float | None
    mean_ballots_difference: float | None
    candidate_share_percentage_points: dict[str, float | None]


class SensitivityReport(BaseModel):
    hypothetical: Literal[True] = True
    disclaimer: str
    iteration_cap: int
    seed: int
    design: str
    varied_parameters: list[str]
    held_constant: list[str]
    variations: list[SensitivityVariation]
    largest_effect_parameter: str | None
    largest_effect_change: str | None
    largest_effect_percentage_points: float | None
    note: str


ScenarioResult.model_rebuild()
