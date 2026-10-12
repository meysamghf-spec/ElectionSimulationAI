"""CSV exports of computed results."""

from __future__ import annotations

import csv
from io import StringIO

from app.io.safety import csv_cell
from app.schemas.results import ComparisonResult, SimulationOutput


def results_csv(output: SimulationOutput, *, view: str = "candidates") -> bytes:
    buffer = StringIO()
    writer = csv.writer(buffer)
    if view == "regional":
        writer.writerow(
            [
                "scenario_id",
                "region_id",
                "region_name",
                "eligible_voters",
                "expected_ballots",
                "mean_ballots",
                "std_ballots",
                "mean_turnout_rate",
                "mean_valid",
                "mean_blank",
                "mean_invalid",
                "candidate_id",
                "mean_votes",
                "std_votes",
                "mean_share",
            ]
        )
        for scenario in output.scenarios:
            for region in scenario.regional:
                for candidate_id, mean_votes in region.mean_votes.items():
                    writer.writerow(
                        [
                            csv_cell(scenario.scenario_id),
                            csv_cell(region.id),
                            csv_cell(region.name),
                            region.eligible_voters,
                            "" if region.expected_ballots is None else region.expected_ballots,
                            region.mean_ballots,
                            region.std_ballots,
                            "" if region.mean_turnout_rate is None else region.mean_turnout_rate,
                            region.mean_valid,
                            region.mean_blank,
                            region.mean_invalid,
                            csv_cell(candidate_id),
                            mean_votes,
                            region.std_votes.get(candidate_id, ""),
                            ""
                            if region.mean_shares.get(candidate_id) is None
                            else region.mean_shares[candidate_id],
                        ]
                    )
    else:
        writer.writerow(
            [
                "scenario_id",
                "scenario_name",
                "candidate_id",
                "candidate_name",
                "mean_votes",
                "median_votes",
                "std_votes",
                "p05",
                "p50",
                "p95",
                "mean_share",
                "sole_win_frequency",
                "sole_win_frequency_se",
                "tie_frequency",
                "mean_seats",
            ]
        )
        for scenario in output.scenarios:
            for candidate in scenario.candidates:
                quantiles = candidate.vote_quantiles
                writer.writerow(
                    [
                        csv_cell(scenario.scenario_id),
                        csv_cell(scenario.scenario_name),
                        csv_cell(candidate.id),
                        csv_cell(candidate.name),
                        candidate.mean_votes,
                        candidate.median_votes,
                        candidate.std_votes,
                        quantiles.get("p05", ""),
                        quantiles.get("p50", ""),
                        quantiles.get("p95", ""),
                        "" if candidate.mean_share is None else candidate.mean_share,
                        candidate.sole_win_frequency,
                        candidate.sole_win_frequency_se,
                        candidate.tie_frequency,
                        "" if candidate.mean_seats is None else candidate.mean_seats,
                    ]
                )
    return buffer.getvalue().encode("utf-8")


def comparison_csv(comparison: ComparisonResult) -> bytes:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "candidate_id",
            "candidate_name",
            "left_mean_votes",
            "right_mean_votes",
            "vote_difference",
            "left_mean_share",
            "right_mean_share",
            "percentage_point_difference",
            "relative_share_change",
            "left_sole_win_frequency",
            "right_sole_win_frequency",
            "sole_win_frequency_difference",
        ]
    )
    for row in comparison.candidates:
        writer.writerow(
            [
                csv_cell(row.id),
                csv_cell(row.name),
                row.left_mean_votes,
                row.right_mean_votes,
                row.vote_difference,
                "" if row.left_mean_share is None else row.left_mean_share,
                "" if row.right_mean_share is None else row.right_mean_share,
                "" if row.percentage_point_difference is None else row.percentage_point_difference,
                "" if row.relative_share_change is None else row.relative_share_change,
                row.left_sole_win_frequency,
                row.right_sole_win_frequency,
                row.sole_win_frequency_difference,
            ]
        )
    return buffer.getvalue().encode("utf-8")
