"""Prompt interpretation and sensitivity sweeps."""

from __future__ import annotations

from app.config import Settings
from app.engine.sensitivity import run_sensitivity
from app.engine.validate import validate_spec
from app.errors import SpecError
from app.interpreter.deterministic import interpret_prompt
from app.interpreter.llm import specification_from_model_text
from app.interpreter.service import interpret
from tests.conftest import specification

EXAMPLE = (
    "Simulate an election with four candidates, 2 million eligible voters, five regions, "
    "regional turnout differences, candidate preferences, 2% invalid ballots, and 10,000 "
    "Monte Carlo iterations. Compare three turnout scenarios."
)


def test_example_prompt_extracts_quantities_and_labels_inferences() -> None:
    spec, _notices = interpret_prompt(EXAMPLE)
    report = validate_spec(spec, Settings(max_iterations=50_000))
    assert report.valid
    assert len(spec.candidates) == 4
    assert len(spec.regions) == 5
    assert sum(region.eligible_voters for region in spec.regions) == 2_000_000
    assert spec.iterations == 10_000
    assert spec.regions[0].invalid_rate == 0.02
    assert [scenario.turnout_multiplier for scenario in spec.scenarios] == [0.85, 1.0, 1.15]
    assert spec.voting_method == "plurality"
    sources = {assumption.field: assumption.source for assumption in spec.assumptions}
    assert sources["population.eligible"] == "extracted"
    assert sources["simulation.iterations"] == "extracted"
    assert sources["ballots.invalid_rate"] == "extracted"
    assert sources["turnout"] == "inferred"
    assert sources["preferences"] == "inferred"
    assert sources["voting_method"] == "default_policy"
    assert spec.empirical_data is False


def test_named_two_round_prompt() -> None:
    spec, _notices = interpret_prompt(
        'Run a two-round election titled "Harbor City Council". Candidates Alice, Bob, and Carol. '
        "10000 eligible voters. One region. Turnout of 60%. Alice 45%, Bob 35%, Carol 20%. "
        "1% blank ballots and 1% invalid ballots. 500 iterations. Seed 7."
    )
    assert spec.title == "Harbor City Council"
    assert [candidate.name for candidate in spec.candidates] == ["Alice", "Bob", "Carol"]
    assert spec.regions[0].preferences == {"alice": 0.45, "bob": 0.35, "carol": 0.2}
    assert spec.seed == 7
    assert spec.voting_method == "two_round"


def test_invalid_percentage_is_not_clamped() -> None:
    try:
        interpret_prompt("150% invalid ballots and 2 candidates and 100 eligible voters and 10 iterations.")
    except SpecError as exc:
        assert "was not changed" in exc.message
    else:
        raise AssertionError("expected a validation error")


def test_model_output_cannot_claim_extracted_facts(monkeypatch: object) -> None:
    del monkeypatch
    raw = """
    {
      "title": "Model election",
      "candidates": [{"id": "a", "name": "A"}],
      "regions": [{
        "id": "r", "name": "R", "eligible_voters": 10, "turnout_probability": 1,
        "preferences": {"a": 1}
      }],
      "voting_method": "plurality",
      "iterations": 2,
      "seed": 1,
      "empirical_data": true,
      "assumptions": [{"field": "population", "source": "extracted", "note": "measured"}]
    }
    """
    spec = specification_from_model_text(raw)
    assert spec.empirical_data is False
    assert all(item.source == "model_proposed" for item in spec.assumptions)


def test_model_code_is_not_executed() -> None:
    try:
        specification_from_model_text('import os; os.system("echo hacked")')
    except SpecError as exc:
        assert "JSON" in exc.message
    else:
        raise AssertionError("non-JSON model output must be rejected")


class _FakeModel:
    def __init__(self, text: str) -> None:
        self.text = text

    def complete_json(self, system_prompt: str, user_prompt: str) -> str:
        del system_prompt, user_prompt
        return self.text


def test_invalid_model_response_falls_back(monkeypatch: object) -> None:
    del monkeypatch
    settings = Settings(llm_api_key="test-key", llm_base_url="http://invalid.example")
    result = interpret(
        "four candidates and 100 eligible voters and 10 iterations",
        settings,
        client=_FakeModel("not json"),
    )
    assert result.interpreter_mode == "deterministic_fallback"
    assert result.specification.iterations == 10


def test_preference_shift_changes_shares() -> None:
    spec = specification(
        iterations=80,
        regions=[{
            "id": "r",
            "name": "Region",
            "eligible_voters": 4000,
            "turnout_probability": 1,
            "preferences": {"a": 0.7, "b": 0.3},
        }],
    )
    report = run_sensitivity(spec, Settings(sensitivity_iteration_cap=80))
    applied = [item for item in report.variations if item.parameter == "preferences" and item.applied]
    assert applied
    shift = next(item for item in applied if "0.10" in item.change)
    assert shift.candidate_share_percentage_points["a"] is not None
    assert shift.candidate_share_percentage_points["a"] < -5
    assert report.largest_effect_parameter == "preferences"
    assert "held" in report.note or report.held_constant
