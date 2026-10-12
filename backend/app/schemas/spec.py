"""Typed election specification. Extra fields are rejected."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AssumptionSource = Literal["extracted", "inferred", "user", "default_policy", "model_proposed"]
VotingMethod = Literal["plurality", "two_round", "ranked_choice", "dhondt"]

ID_PATTERN = r"^[a-z][a-z0-9_-]{0,63}$"


class Assumption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1, max_length=120)
    source: AssumptionSource
    note: str = Field(min_length=1, max_length=2000)


class CandidateSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1, max_length=120)


class RankingBloc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ranking: list[str] = Field(min_length=1, max_length=25)
    weight: float = Field(ge=0, le=1)


class SegmentSpec(BaseModel):
    """A demographic slice of a region. Shares are proportions of eligible voters."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1, max_length=120)
    share: float = Field(ge=0, le=1)
    turnout_probability: float = Field(ge=0, le=1)
    preferences: dict[str, float]
    blank_rate: float = Field(default=0, ge=0, le=1)
    invalid_rate: float = Field(default=0, ge=0, le=1)
    ranking_blocs: list[RankingBloc] | None = Field(default=None, max_length=200)


class RegionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1, max_length=120)
    eligible_voters: int = Field(ge=0, le=1_000_000_000)
    turnout_probability: float = Field(ge=0, le=1)
    preferences: dict[str, float]
    blank_rate: float = Field(default=0, ge=0, le=1)
    invalid_rate: float = Field(default=0, ge=0, le=1)
    ranking_blocs: list[RankingBloc] | None = Field(default=None, max_length=200)
    segments: list[SegmentSpec] | None = Field(default=None, max_length=12)


class ScenarioSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    turnout_multiplier: float | None = Field(default=None, ge=0, le=5)
    turnout_by_region: dict[str, float] | None = None
    preference_overrides: dict[str, dict[str, float]] | None = None
    invalid_rate_override: float | None = Field(default=None, ge=0, le=1)
    blank_rate_override: float | None = Field(default=None, ge=0, le=1)
    voting_method_override: VotingMethod | None = None
    seats_override: int | None = Field(default=None, ge=0, le=1000)
    runoff_threshold_override: float | None = Field(default=None, gt=0, le=1)
    turnout_shock_sd_override: float | None = Field(default=None, ge=0, le=1)


class ReportingOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_regional: bool = True
    include_histograms: bool = True
    histogram_bins: int = Field(default=20, ge=1, le=100)


class ElectionSpecification(BaseModel):
    """Full configuration required to reproduce a simulation."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=8000)
    candidates: list[CandidateSpec] = Field(min_length=1, max_length=25)
    regions: list[RegionSpec] = Field(min_length=1, max_length=80)
    voting_method: VotingMethod
    seats: int | None = Field(default=None, ge=0, le=1000)
    runoff_threshold: float = Field(default=0.5, gt=0, le=1)
    runoff_transfers: dict[str, dict[str, float]] | None = None
    iterations: int = Field(ge=1, le=100_000)
    seed: int = Field(ge=0, le=4_294_967_295)
    scenarios: list[ScenarioSpec] = Field(default_factory=list, max_length=12)
    assumptions: list[Assumption] = Field(default_factory=list, max_length=200)
    empirical_data: bool = False
    turnout_shock_sd: float = Field(default=0, ge=0, le=1)
    reporting: ReportingOptions = Field(default_factory=ReportingOptions)


class ValidationIssue(BaseModel):
    field: str
    message: str
    severity: Literal["error", "warning"]


class ValidationReport(BaseModel):
    valid: bool
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]
