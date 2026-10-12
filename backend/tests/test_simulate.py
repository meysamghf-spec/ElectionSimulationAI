"""Monte Carlo invariants, edge cases, and reproducibility."""

from __future__ import annotations

import time

from app.config import Settings
from app.engine.simulate import run_simulation
from app.engine.validate import validate_spec
from tests.conftest import specification


def test_deterministic_plurality_matches_expectation() -> None:
    spec = specification()
    output = run_simulation(spec, Settings())
    scenario = output.scenarios[0]
    assert scenario.expected_votes == {"a": 100.0, "b": 0.0}
    assert scenario.candidates[0].mean_votes == 100
    assert scenario.candidates[0].sole_win_frequency == 1
    assert scenario.candidates[1].mean_votes == 0
    assert scenario.mean_valid == 100
    assert scenario.hypothetical is True
    assert all(check.passed for check in scenario.validation_checks)


def test_same_seed_reproduces_numerical_summaries() -> None:
    spec = specification(
        iterations=40,
        regions=[
            {
                "id": "r",
                "name": "Region",
                "eligible_voters": 500,
                "turnout_probability": 0.55,
                "preferences": {"a": 0.46, "b": 0.54},
                "blank_rate": 0.02,
                "invalid_rate": 0.03,
            }
        ],
    )
    settings = Settings()
    first = run_simulation(spec, settings)
    second = run_simulation(spec, settings)
    assert first.spec_hash == second.spec_hash
    assert first.scenarios[0].mean_ballots == second.scenarios[0].mean_ballots
    assert first.scenarios[0].candidates[0].mean_votes == second.scenarios[0].candidates[0].mean_votes
    assert first.scenarios[0].candidates[0].vote_quantiles == second.scenarios[0].candidates[0].vote_quantiles


def test_zero_eligible_voters_do_not_divide_by_zero() -> None:
    spec = specification(regions=[{
        "id": "r",
        "name": "Empty",
        "eligible_voters": 0,
        "turnout_probability": 1,
        "preferences": {"a": 1.0, "b": 0.0},
    }])
    scenario = run_simulation(spec, Settings()).scenarios[0]
    assert scenario.mean_ballots == 0
    assert scenario.mean_turnout_rate is None
    assert scenario.candidates[0].mean_share is None
    assert scenario.candidates[0].sole_win_frequency == 0


def test_all_invalid_ballots_have_no_winner() -> None:
    spec = specification(regions=[{
        "id": "r",
        "name": "Region",
        "eligible_voters": 10,
        "turnout_probability": 1,
        "preferences": {"a": 1.0, "b": 0.0},
        "blank_rate": 0,
        "invalid_rate": 1,
    }])
    scenario = run_simulation(spec, Settings()).scenarios[0]
    assert scenario.mean_invalid == 10
    assert scenario.mean_valid == 0
    assert scenario.candidates[0].sole_win_frequency == 0


def test_segments_use_fixed_largest_remainder_sizes() -> None:
    spec = specification(
        regions=[{
            "id": "r",
            "name": "Region",
            "eligible_voters": 10,
            "turnout_probability": 0.2,
            "preferences": {"a": 0.5, "b": 0.5},
            "segments": [
                {
                    "id": "s1",
                    "name": "One",
                    "share": 0.6,
                    "turnout_probability": 1,
                    "preferences": {"a": 1.0, "b": 0.0},
                },
                {
                    "id": "s2",
                    "name": "Two",
                    "share": 0.4,
                    "turnout_probability": 1,
                    "preferences": {"a": 0.0, "b": 1.0},
                },
            ],
        }],
        iterations=3,
    )
    scenario = run_simulation(spec, Settings()).scenarios[0]
    assert scenario.expected_votes == {"a": 6.0, "b": 4.0}
    assert [candidate.mean_votes for candidate in scenario.candidates] == [6, 4]


def test_probabilities_that_do_not_sum_to_one_are_rejected() -> None:
    spec = specification(regions=[{
        "id": "r",
        "name": "Region",
        "eligible_voters": 10,
        "turnout_probability": 1,
        "preferences": {"a": 0.5, "b": 0.2},
    }])
    report = validate_spec(spec, Settings())
    assert report.valid is False
    assert "sum" in report.errors[0].message


def test_plurality_rejects_multi_seat_requests() -> None:
    spec = specification(seats=5)
    report = validate_spec(spec, Settings())
    assert report.valid is False
    assert "dhondt" in report.errors[0].message


def test_dhondt_requires_seats() -> None:
    spec = specification(voting_method="dhondt", seats=None)
    report = validate_spec(spec, Settings())
    assert report.valid is False


def test_duplicate_candidate_ids_are_rejected() -> None:
    spec = specification(candidates=[{"id": "a", "name": "A"}, {"id": "a", "name": "Other"}])
    report = validate_spec(spec, Settings())
    assert report.valid is False


def test_scenario_comparison_labels_percentage_points() -> None:
    spec = specification(
        iterations=10,
        scenarios=[
            {"id": "low", "name": "Low", "turnout_multiplier": 0.5},
            {"id": "high", "name": "High", "turnout_multiplier": 1},
        ],
    )
    output = run_simulation(spec, Settings())
    comparison = output.reference_comparisons[0]
    assert "percentage point" in comparison.explanation.lower()
    assert comparison.mean_ballots_difference > 0


def test_representative_run_finishes_quickly() -> None:
    spec = specification(
        iterations=1000,
        candidates=[
            {"id": "a", "name": "A"},
            {"id": "b", "name": "B"},
            {"id": "c", "name": "C"},
            {"id": "d", "name": "D"},
        ],
        regions=[
            {
                "id": f"r{index}",
                "name": f"Region {index}",
                "eligible_voters": 20_000,
                "turnout_probability": 0.5 + index * 0.05,
                "preferences": {"a": 0.4, "b": 0.3, "c": 0.2, "d": 0.1},
                "blank_rate": 0.01,
                "invalid_rate": 0.02,
            }
            for index in range(5)
        ],
    )
    started = time.perf_counter()
    output = run_simulation(spec, Settings(max_iterations=5_000))
    elapsed = time.perf_counter() - started
    assert output.scenarios[0].iterations_completed == 1000
    assert elapsed < 15
    print(f"measured_1000_iterations_seconds={elapsed:.3f}")
