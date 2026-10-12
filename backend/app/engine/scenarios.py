"""Apply explicit scenario overrides without changing unrelated parameters."""

from __future__ import annotations

from app.engine.population import clip_probability
from app.errors import SpecError
from app.schemas.spec import ElectionSpecification, ScenarioSpec


def apply_scenario(
    spec: ElectionSpecification,
    scenario: ScenarioSpec | None,
) -> tuple[ElectionSpecification, list[str]]:
    if scenario is None:
        return spec, ["Baseline specification. No scenario overrides were applied."]
    resolved = spec.model_copy(deep=True)
    notes: list[str] = []
    if scenario.description:
        notes.append(scenario.description)
    if scenario.voting_method_override is not None:
        resolved.voting_method = scenario.voting_method_override
        notes.append(f"Voting method set to {scenario.voting_method_override}.")
    if scenario.seats_override is not None:
        resolved.seats = scenario.seats_override
        notes.append(f"Seat total set to {scenario.seats_override}.")
    if scenario.runoff_threshold_override is not None:
        resolved.runoff_threshold = scenario.runoff_threshold_override
        notes.append(f"Runoff threshold set to {scenario.runoff_threshold_override}.")
    if scenario.turnout_shock_sd_override is not None:
        resolved.turnout_shock_sd = scenario.turnout_shock_sd_override
        notes.append(f"Shared turnout shock standard deviation set to {scenario.turnout_shock_sd_override}.")
    if scenario.turnout_multiplier is not None:
        multiplier = scenario.turnout_multiplier
        for region in resolved.regions:
            region.turnout_probability = clip_probability(region.turnout_probability * multiplier)
            if region.segments:
                for segment in region.segments:
                    segment.turnout_probability = clip_probability(
                        segment.turnout_probability * multiplier
                    )
        notes.append(
            f"Turnout probabilities were multiplied by {multiplier} and clipped to [0, 1]."
        )
    if scenario.turnout_by_region:
        known = {region.id for region in resolved.regions}
        unknown = set(scenario.turnout_by_region) - known
        if unknown:
            raise SpecError(
                f"Scenario {scenario.id} names unknown regions: {sorted(unknown)}.",
                details=[{"field": f"scenarios.{scenario.id}", "message": "Unknown region id."}],
            )
        for region in resolved.regions:
            if region.id in scenario.turnout_by_region:
                region.turnout_probability = scenario.turnout_by_region[region.id]
        notes.append("Listed regions received an explicit turnout probability.")
    if scenario.invalid_rate_override is not None:
        for region in resolved.regions:
            region.invalid_rate = scenario.invalid_rate_override
            if region.segments:
                for segment in region.segments:
                    segment.invalid_rate = scenario.invalid_rate_override
        notes.append(f"Invalid-ballot rate set to {scenario.invalid_rate_override}.")
    if scenario.blank_rate_override is not None:
        for region in resolved.regions:
            region.blank_rate = scenario.blank_rate_override
            if region.segments:
                for segment in region.segments:
                    segment.blank_rate = scenario.blank_rate_override
        notes.append(f"Blank-ballot rate set to {scenario.blank_rate_override}.")
    if scenario.preference_overrides:
        known = {region.id for region in resolved.regions}
        unknown = set(scenario.preference_overrides) - known
        if unknown:
            raise SpecError(
                f"Scenario {scenario.id} names unknown regions in preference overrides.",
                details=[{"field": f"scenarios.{scenario.id}", "message": "Unknown region id."}],
            )
        for region in resolved.regions:
            override = scenario.preference_overrides.get(region.id)
            if override is None:
                continue
            region.preferences = dict(override)
            if region.segments:
                for segment in region.segments:
                    segment.preferences = dict(override)
                notes.append(
                    f"Preference override for {region.id} replaced every segment in that region."
                )
            else:
                notes.append(f"Preferences replaced for region {region.id}.")
    if not notes:
        notes.append("Scenario has no numeric overrides. Baseline parameters were used.")
    notes.append("Parameters not named above were held at the baseline specification.")
    return resolved, notes
