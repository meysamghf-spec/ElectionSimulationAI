"""Deterministic prompt parser.

Extracted fields are numbers or names that appear in the prompt. Anything else
is labeled inferred or default_policy. Invalid combinations are rejected
instead of being repaired.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import cast

from pydantic import ValidationError

from app.engine.population import equal_weights, largest_remainder
from app.errors import SpecError
from app.schemas.spec import (
    Assumption,
    AssumptionSource,
    CandidateSpec,
    ElectionSpecification,
    RankingBloc,
    RegionSpec,
    ScenarioSpec,
)

AssumeFn = Callable[[str, str, str], None]

WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "fifteen": 15,
    "twenty": 20,
}
WORD_PATTERN = "|".join(WORDS)
SCALES = {"million": 1_000_000, "billion": 1_000_000_000, "thousand": 1_000, "m": 1_000_000, "k": 1_000}
DEFAULT_SEED = 20241105
DEFAULT_ITERATIONS = 2000


def interpret_prompt(prompt: str) -> tuple[ElectionSpecification, list[str]]:
    text = prompt.strip()
    if not text:
        raise SpecError("Enter a description of the election before interpreting it.")
    if text.startswith("{"):
        return _from_json(text), ["The prompt was parsed as JSON, not as prose."]
    notices: list[str] = []
    assumptions: list[Assumption] = []

    def assume(field: str, source: str, note: str) -> None:
        assumptions.append(
            Assumption(field=field, source=cast(AssumptionSource, source), note=note)
        )

    title, title_source = _title(text)
    assume(
        "title",
        title_source,
        "Title taken from the prompt."
        if title_source == "extracted"
        else "No title was stated. A neutral placeholder is used.",
    )

    names = _names(text)
    counts = _word_or_int(rf"\b(\d+|{WORD_PATTERN})\s+candidates?\b", text)
    if len(set(counts)) > 1:
        raise SpecError("The prompt states more than one candidate count.")
    stated_count = counts[0] if counts else None
    if names and stated_count is not None and stated_count != len(names):
        raise SpecError(
            f"The prompt names {len(names)} candidates but also says there are {stated_count}.",
            details=[{"field": "candidates", "message": "Candidate count and names disagree."}],
        )
    if names:
        assume("candidates.names", "extracted", f"Named candidates: {', '.join(names)}.")
        candidate_names = names
    elif stated_count is not None:
        assume("candidates.count", "extracted", f"The prompt requests {stated_count} candidates without naming them.")
        candidate_names = [f"Candidate {index}" for index in range(1, stated_count + 1)]
        assume(
            "candidates.names",
            "inferred",
            "Placeholder names were generated. They are not names from the prompt.",
        )
    else:
        candidate_names = ["Candidate 1", "Candidate 2"]
        assume(
            "candidates",
            "inferred",
            "No candidate count or names were stated. Two placeholders were created.",
        )
    if stated_count == 0 or (names is not None and len(names) == 0):
        raise SpecError("At least one candidate is required.")
    candidates = _unique_candidates(candidate_names)

    region_counts = _word_or_int(rf"\b(\d+|{WORD_PATTERN})\s+regions?\b", text)
    if len(set(region_counts)) > 1:
        raise SpecError("The prompt states more than one region count.")
    region_count = region_counts[0] if region_counts else 1
    if region_counts:
        assume("regions.count", "extracted", f"The prompt requests {region_count} regions.")
    else:
        assume("regions.count", "inferred", "No region count was stated. One region is used.")
    if region_count < 1:
        raise SpecError("The region count must be at least 1.")
    if region_count > 80:
        raise SpecError("Region count exceeds the supported maximum of 80.")

    eligible = _eligible(text, assume)
    populations = largest_remainder(eligible, equal_weights(region_count))
    if region_count > 1 and region_counts:
        assume(
            "regions.population",
            "inferred",
            "Eligible voters are split equally across regions with the largest-remainder method. "
            "The prompt did not give a regional population distribution.",
        )

    turnout = _percent_after(r"turnout of\s+(\d+(?:\.\d+)?)\s*(?:%|percent)", text)
    if turnout is None:
        turnout = _percent_after(r"\bturnout\s+(\d+(?:\.\d+)?)\s*(?:%|percent)", text)
    differences = re.search(r"regional turnout differences", text, re.I) is not None
    turnouts = _turnouts(region_count, turnout, differences, assume, notices)

    invalid_rate = _rate(r"(\d+(?:\.\d+)?)\s*(?:%|percent)\s*invalid", text)
    blank_rate = _rate(r"(\d+(?:\.\d+)?)\s*(?:%|percent)\s*blank", text)
    if invalid_rate is not None and not 0 <= invalid_rate <= 1:
        raise SpecError(
            f"The invalid-ballot rate is {invalid_rate:.4g}, outside [0, 1]. It was not changed.",
            details=[{"field": "ballots.invalid_rate", "message": "Invalid rate must be between 0 and 1."}],
        )
    if blank_rate is not None and not 0 <= blank_rate <= 1:
        raise SpecError(
            f"The blank-ballot rate is {blank_rate:.4g}, outside [0, 1]. It was not changed.",
            details=[{"field": "ballots.blank_rate", "message": "Blank rate must be between 0 and 1."}],
        )
    if invalid_rate is None:
        invalid_rate = 0.0
        assume("ballots.invalid_rate", "default_policy", "No invalid-ballot rate was stated. The rate is 0.")
    else:
        assume("ballots.invalid_rate", "extracted", f"Invalid ballots are {invalid_rate:.4g} of ballots cast.")
    if blank_rate is None:
        blank_rate = 0.0
        assume("ballots.blank_rate", "default_policy", "No blank-ballot rate was stated. The rate is 0.")
    else:
        assume("ballots.blank_rate", "extracted", f"Blank ballots are {blank_rate:.4g} of ballots cast.")
    if blank_rate + invalid_rate > 1:
        raise SpecError(
            "Blank and invalid rates extracted from the prompt sum to more than 1.",
            details=[{"field": "ballots", "message": "blank_rate + invalid_rate cannot exceed 1."}],
        )

    method, method_source = _method(text)
    assume(
        "voting_method",
        method_source,
        "Voting method read from the prompt."
        if method_source == "extracted"
        else "No voting method was stated. Plurality is the default single-winner method.",
    )
    seats = _first_int(r"\b(\d+)\s+seats?\b", text)
    if seats is not None:
        assume("seats", "extracted", f"The prompt requests {seats} seats.")
    elif method == "dhondt":
        notices.append(
            "D'Hondt was requested without a seat total. "
            "Validation will reject the specification until seats are set."
        )

    ranking_blocs, preferences, _preference_source = _preferences(text, candidates, assume)
    iterations = _iterations(text, assume)
    seed = _first_int(r"\bseed\s+(\d+)\b", text)
    if seed is None:
        seed = DEFAULT_SEED
        assume("simulation.seed", "default_policy", f"No seed was stated. The reproducible default is {DEFAULT_SEED}.")
    else:
        assume("simulation.seed", "extracted", f"Seed {seed} was stated.")

    shock = _shock(text, assume, notices)
    scenarios = _scenarios(text, assume)

    regions = []
    for index, population in enumerate(populations):
        regions.append(
            RegionSpec(
                id=f"r{index + 1}",
                name=f"Region {index + 1}",
                eligible_voters=population,
                turnout_probability=turnouts[index],
                preferences=preferences,
                blank_rate=blank_rate,
                invalid_rate=invalid_rate,
                ranking_blocs=ranking_blocs,
            )
        )
    try:
        specification = ElectionSpecification(
            title=title[:200],
            description=text[:8000],
            candidates=candidates,
            regions=regions,
            voting_method=method,  # type: ignore[arg-type]
            seats=seats,
            iterations=iterations,
            seed=seed,
            scenarios=scenarios,
            assumptions=assumptions,
            empirical_data=False,
            turnout_shock_sd=shock,
        )
    except ValidationError as exc:
        raise SpecError(
            "The prompt produced a specification that failed schema validation.",
            details=_pydantic_details(exc),
        ) from exc
    return specification, notices


def _from_json(text: str) -> ElectionSpecification:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SpecError(f"The prompt starts with '{{' but is not valid JSON: {exc.msg}.") from exc
    if not isinstance(payload, dict):
        raise SpecError("JSON specifications must be an object.")
    try:
        specification = ElectionSpecification.model_validate(payload)
    except ValidationError as exc:
        raise SpecError("The JSON specification is invalid.", details=_pydantic_details(exc)) from exc
    if not specification.assumptions:
        specification.assumptions.append(
            Assumption(
                field="specification",
                source="user",
                note="The specification was supplied as JSON by the user.",
            )
        )
    return specification


def _title(text: str) -> tuple[str, str]:
    quoted = re.search(r"\btitled\s+\"([^\"]+)\"", text, re.I)
    if quoted:
        return quoted.group(1).strip(), "extracted"
    plain = re.search(r"\btitled\s+([^.\n]+)", text, re.I)
    if plain:
        return plain.group(1).strip(), "extracted"
    return "Hypothetical election", "inferred"


def _names(text: str) -> list[str] | None:
    match = re.search(r"\b[Cc]andidates?\s+([A-Z][^.\n]+)", text)
    if not match:
        return None
    chunk = re.split(
        r"\b(eligible|turnout|region|seat|iteration|seed|ranking|preference|compare)\b",
        match.group(1),
        maxsplit=1,
        flags=re.I,
    )[0]
    parts = re.split(r",|\band\b", chunk)
    names = []
    for part in parts:
        cleaned = part.strip(" .;")
        if re.fullmatch(r"[A-Z][A-Za-z.'-]*(?:\s+[A-Z][A-Za-z.'-]*)?", cleaned):
            names.append(cleaned)
    return names or None


def _unique_candidates(names: list[str]) -> list[CandidateSpec]:
    used: set[str] = set()
    candidates: list[CandidateSpec] = []
    for name in names:
        base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        if not base or not base[0].isalpha():
            base = f"c-{base}" if base else "candidate"
        base = base[:60]
        candidate_id = base
        suffix = 2
        while candidate_id in used:
            candidate_id = f"{base}-{suffix}"
            suffix += 1
        used.add(candidate_id)
        candidates.append(CandidateSpec(id=candidate_id, name=name))
    return candidates


def _eligible(text: str, assume: AssumeFn) -> int:
    pattern = re.compile(
        r"(?P<num>\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(?P<scale>million|billion|thousand|m|k)?\s+eligible\s+voters?",
        re.I,
    )
    found: list[int] = []
    for match in pattern.finditer(text):
        number = float(match.group("num").replace(",", ""))
        scale_name = match.group("scale")
        if scale_name:
            number *= SCALES[scale_name.lower()]
        if abs(number - round(number)) > 1e-6:
            raise SpecError("Eligible voters must be a whole number.")
        found.append(int(round(number)))
    if len(set(found)) > 1:
        raise SpecError("The prompt states more than one eligible-voter total.")
    if not found:
        assume(
            "population.eligible",
            "inferred",
            "No eligible population was stated. 1000 voters is a placeholder, not a measurement.",
        )
        return 1000
    assume("population.eligible", "extracted", f"Eligible voters stated as {found[0]}.")
    return found[0]


def _turnouts(
    region_count: int,
    turnout: float | None,
    differences: bool,
    assume: AssumeFn,
    notices: list[str],
) -> list[float]:
    if differences and turnout is not None:
        notices.append(
            "The prompt mentions regional turnout differences but also states one turnout rate. "
            "No separate rates were given, so the stated rate is used in every region."
        )
        assume("turnout", "extracted", f"Turnout probability {turnout:.4g} is used in every region.")
        return [turnout] * region_count
    if differences:
        values = [_illustrative_turnout(index, region_count) for index in range(region_count)]
        assume(
            "turnout",
            "inferred",
            "The prompt asks for regional turnout differences without numbers. "
            f"An illustrative gradient from {values[0]:.2f} to {values[-1]:.2f} is used. "
            "It is not an empirical turnout estimate.",
        )
        return values
    if turnout is not None:
        assume("turnout", "extracted", f"Turnout probability {turnout:.4g} was stated.")
        return [turnout] * region_count
    assume(
        "turnout",
        "inferred",
        "No turnout was stated. 0.60 is a placeholder probability, not a measurement.",
    )
    return [0.6] * region_count


def _illustrative_turnout(index: int, count: int) -> float:
    if count <= 1:
        return 0.65
    return round(0.50 + 0.30 * index / (count - 1), 4)


def _preferences(
    text: str,
    candidates: list[CandidateSpec],
    assume: AssumeFn,
) -> tuple[list[RankingBloc] | None, dict[str, float], str]:
    ranking_pattern = re.compile(
        r"(\d+(?:\.\d+)?)\s*%\s+((?:[A-Za-z][A-Za-z'-]*\s*>\s*)+[A-Za-z][A-Za-z'-]*)"
    )
    blocs: list[RankingBloc] = []
    for match in ranking_pattern.finditer(text):
        percent = float(match.group(1))
        ranking_names = [part.strip() for part in match.group(2).split(">")]
        ranking_ids = [_id_for_name(name, candidates) for name in ranking_names]
        if any(item is None for item in ranking_ids):
            raise SpecError(
                f"A ranking names a candidate that was not declared: {match.group(2)}.",
                details=[{"field": "ranking_blocs", "message": "Unknown candidate in a ranking."}],
            )
        blocs.append(
            RankingBloc(
                ranking=[item for item in ranking_ids if item is not None],
                weight=percent / 100.0,
            )
        )
    if blocs:
        weights = [bloc.weight for bloc in blocs]
        if abs(sum(weights) - 1.0) > 1e-6:
            assume(
                "ranking_blocs",
                "extracted",
                "Ranking weights were read from the prompt and were not rescaled. "
                "Validation will reject them if they do not sum to 1.",
            )
        else:
            assume("ranking_blocs", "extracted", "Ranking blocs were read from the prompt.")
        preferences = {candidate.id: 0.0 for candidate in candidates}
        for bloc in blocs:
            preferences[bloc.ranking[0]] += bloc.weight
        assume(
            "preferences",
            "extracted",
            "First-choice preferences were derived from the stated rankings.",
        )
        return blocs, preferences, "extracted"

    pref_pattern = re.compile(r"\b([A-Z][A-Za-z.'-]*)\s+(\d+(?:\.\d+)?)\s*%")
    found: dict[str, float] = {}
    for match in pref_pattern.finditer(text):
        candidate_id = _id_for_name(match.group(1), candidates)
        if candidate_id is None:
            continue
        found[candidate_id] = float(match.group(2)) / 100.0
    if found:
        preferences = {candidate.id: found.get(candidate.id, 0.0) for candidate in candidates}
        assume(
            "preferences",
            "extracted",
            "Candidate percentages were read from the prompt and divided by 100. They were not renormalized.",
        )
        return None, preferences, "extracted"
    weights = equal_weights(len(candidates))
    preferences = {candidate.id: weight for candidate, weight in zip(candidates, weights, strict=True)}
    assume(
        "preferences",
        "inferred",
        "No candidate percentages were stated. Preferences are equal. "
        "The last candidate absorbs the binary residual so the weights sum to 1. "
        "This is not a measurement of support.",
    )
    return None, preferences, "inferred"


def _id_for_name(name: str, candidates: list[CandidateSpec]) -> str | None:
    for candidate in candidates:
        if candidate.name.lower() == name.lower():
            return candidate.id
    return None


def _iterations(text: str, assume: AssumeFn) -> int:
    pattern = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+)\s+(?:monte\s+carlo\s+)?iterations?", re.I)
    found = [int(match.group(1).replace(",", "")) for match in pattern.finditer(text)]
    if len(set(found)) > 1:
        raise SpecError("The prompt states more than one iteration count.")
    if not found:
        assume(
            "simulation.iterations",
            "default_policy",
            f"No iteration count was stated. The default is {DEFAULT_ITERATIONS}.",
        )
        return DEFAULT_ITERATIONS
    assume("simulation.iterations", "extracted", f"{found[0]} Monte Carlo iterations were requested.")
    return found[0]


def _scenarios(text: str, assume: AssumeFn) -> list[ScenarioSpec]:
    found = _word_or_int(rf"\bcompare\s+(\d+|{WORD_PATTERN})\s+turnout scenarios?\b", text)
    if len(set(found)) > 1:
        raise SpecError("The prompt states more than one scenario count.")
    if not found:
        return []
    count = found[0]
    if count < 2 or count > 12:
        raise SpecError("Turnout scenario comparisons must request between 2 and 12 scenarios.")
    if count == 3:
        multipliers = [0.85, 1.0, 1.15]
    elif count == 2:
        multipliers = [0.9, 1.1]
    else:
        multipliers = [0.8 + 0.4 * index / (count - 1) for index in range(count)]
    assume(
        "scenarios",
        "inferred",
        f"The prompt asks to compare {count} turnout scenarios without stating the rates. "
        f"Multipliers {', '.join(f'{value:.3g}' for value in multipliers)} are illustrative, "
        "applied to the baseline turnout and clipped to [0, 1].",
    )
    return [
        ScenarioSpec(
            id=f"scenario-{index + 1}",
            name=f"Turnout scenario {index + 1}",
            description=f"Illustrative turnout multiplier {multiplier:.3g}. Not an empirical scenario.",
            turnout_multiplier=multiplier,
        )
        for index, multiplier in enumerate(multipliers)
    ]


def _method(text: str) -> tuple[str, str]:
    flags = {
        "ranked_choice": re.search(r"ranked[- ]choice|instant[- ]runoff|\bIRV\b", text, re.I),
        "two_round": re.search(r"two[- ]round|\brunoff\b", text, re.I),
        "dhondt": re.search(r"d['’]?hondt|proportional", text, re.I),
        "plurality": re.search(r"plurality|first[- ]past[- ]the[- ]post|\bFPTP\b", text, re.I),
    }
    selected = [name for name, match in flags.items() if match]
    if len(selected) > 1:
        raise SpecError(
            f"The prompt names more than one voting method: {', '.join(selected)}.",
            details=[{"field": "voting_method", "message": "Choose one voting method."}],
        )
    if not selected:
        return "plurality", "default_policy"
    return selected[0], "extracted"


def _shock(text: str, assume: AssumeFn, notices: list[str]) -> float:
    match = re.search(
        r"shared turnout shock(?: standard deviation| sd)?\s+(\d+(?:\.\d+)?)",
        text,
        re.I,
    )
    if match:
        value = float(match.group(1))
        assume("turnout_shock_sd", "extracted", f"Shared turnout shock standard deviation {value} was stated.")
        return value
    if re.search(r"correlated (?:regional )?turnout", text, re.I):
        notices.append(
            "The prompt mentions correlated turnout but does not give a shared shock standard deviation. "
            "Regional turnout stays independent."
        )
    return 0.0


def _rate(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, re.I)
    if not match:
        return None
    return float(match.group(1)) / 100.0


def _percent_after(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, re.I)
    if not match:
        return None
    return float(match.group(1)) / 100.0


def _first_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text, re.I)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


def _word_or_int(pattern: str, text: str) -> list[int]:
    values = []
    for match in re.finditer(pattern, text, re.I):
        token = match.group(1).lower()
        values.append(WORDS[token] if token in WORDS else int(token))
    return values


def _pydantic_details(exc: ValidationError) -> list[dict[str, str]]:
    details = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        details.append({"field": location or "specification", "message": error["msg"]})
    return details
