"""Compare stored scenario summaries without re-drawing the election."""

from __future__ import annotations

from app.schemas.results import CandidateDelta, ComparisonResult, ScenarioResult


def compare_scenarios(left: ScenarioResult, right: ScenarioResult) -> ComparisonResult:
    right_by_id = {candidate.id: candidate for candidate in right.candidates}
    rows: list[CandidateDelta] = []
    for candidate in left.candidates:
        other = right_by_id.get(candidate.id)
        if other is None:
            continue
        percentage_points = _share_points(candidate.mean_share, other.mean_share)
        rows.append(
            CandidateDelta(
                id=candidate.id,
                name=candidate.name,
                left_mean_votes=candidate.mean_votes,
                right_mean_votes=other.mean_votes,
                vote_difference=other.mean_votes - candidate.mean_votes,
                left_mean_share=candidate.mean_share,
                right_mean_share=other.mean_share,
                percentage_point_difference=percentage_points,
                relative_share_change=_relative(candidate.mean_share, other.mean_share),
                left_sole_win_frequency=candidate.sole_win_frequency,
                right_sole_win_frequency=other.sole_win_frequency,
                sole_win_frequency_difference=(
                    other.sole_win_frequency - candidate.sole_win_frequency
                ),
                left_mean_seats=candidate.mean_seats,
                right_mean_seats=other.mean_seats,
            )
        )
    turnout_points = _share_points(left.mean_turnout_rate, right.mean_turnout_rate)
    return ComparisonResult(
        left_scenario_id=left.scenario_id,
        left_scenario_name=left.scenario_name,
        right_scenario_id=right.scenario_id,
        right_scenario_name=right.scenario_name,
        explanation=(
            "Differences compare stored Monte Carlo means. "
            "percentage_point_difference is (right share - left share) × 100, an absolute "
            "change in percentage points. relative_share_change is (right - left) / left "
            "when the left share is nonzero, a relative change. "
            "Neither quantity is an estimate of a real-world effect."
        ),
        eligible_voters_left=left.eligible_voters,
        eligible_voters_right=right.eligible_voters,
        mean_ballots_difference=right.mean_ballots - left.mean_ballots,
        turnout_percentage_point_difference=turnout_points,
        mean_valid_difference=right.mean_valid - left.mean_valid,
        mean_blank_difference=right.mean_blank - left.mean_blank,
        mean_invalid_difference=right.mean_invalid - left.mean_invalid,
        candidates=rows,
    )


def _share_points(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return (right - left) * 100.0


def _relative(left: float | None, right: float | None) -> float | None:
    if left is None or right is None or abs(left) < 1e-12:
        return None
    return (right - left) / left
