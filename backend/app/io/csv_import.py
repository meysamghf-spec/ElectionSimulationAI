"""Aggregate region CSV import. Cells are data, never code."""

from __future__ import annotations

import re
from io import BytesIO

import pandas as pd

from app.engine.population import probability_issue
from app.errors import SpecError
from app.io.safety import safe_filename
from app.schemas.spec import Assumption, CandidateSpec, ElectionSpecification, RegionSpec

MAX_ROWS = 5000
MAX_COLUMNS = 40
REQUIRED = [
    "region_id",
    "name",
    "eligible_voters",
    "turnout_probability",
    "blank_rate",
    "invalid_rate",
]
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


def import_regions_csv(
    content: bytes,
    *,
    filename: str,
    title: str,
    voting_method: str,
    iterations: int,
    seed: int,
    seats: int | None = None,
    description: str = "",
) -> tuple[ElectionSpecification, list[str]]:
    if not content:
        raise SpecError("The uploaded file is empty.")
    if len(content) > 2_000_000:
        raise SpecError("The uploaded file exceeds the 2 MB limit.")
    try:
        frame = pd.read_csv(BytesIO(content), dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except (UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise SpecError(f"The CSV could not be parsed: {exc}.") from exc
    if frame.shape[0] > MAX_ROWS:
        raise SpecError(f"CSV imports are limited to {MAX_ROWS} region rows.")
    if frame.shape[1] > MAX_COLUMNS:
        raise SpecError(f"CSV imports are limited to {MAX_COLUMNS} columns.")
    if frame.shape[0] == 0:
        raise SpecError("The CSV has headers but no data rows.")
    columns = [str(column).strip() for column in frame.columns]
    frame.columns = columns
    missing = [column for column in REQUIRED if column not in columns]
    if missing:
        raise SpecError(
            "The CSV is missing required columns.",
            details=[{"field": "columns", "message": f"Missing: {', '.join(missing)}."}],
        )
    preference_columns = [column for column in columns if column.startswith("pref_")]
    if not preference_columns:
        raise SpecError("The CSV needs at least one pref_<candidate_id> column.")
    unknown = [
        column
        for column in columns
        if column not in REQUIRED and not column.startswith("pref_")
    ]
    if unknown:
        raise SpecError(
            "The CSV has columns that this schema does not use. Remove them so data is not silently ignored.",
            details=[{"field": "columns", "message": ", ".join(unknown)}],
        )
    candidate_ids = []
    for column in preference_columns:
        candidate_id = column.removeprefix("pref_")
        if not ID_PATTERN.fullmatch(candidate_id):
            raise SpecError(
                f"Preference column {column} must use a lowercase candidate id matching {ID_PATTERN.pattern}.",
                details=[{"field": column, "message": "Invalid candidate id."}],
            )
        candidate_ids.append(candidate_id)
    if len(candidate_ids) != len(set(candidate_ids)):
        raise SpecError("Preference columns repeat a candidate id.")

    warnings: list[str] = []
    regions: list[RegionSpec] = []
    seen: set[str] = set()
    details: list[dict[str, str]] = []
    for offset, row in frame.iterrows():
        row_number = int(offset) + 2
        region_id = str(row["region_id"]).strip()
        if not ID_PATTERN.fullmatch(region_id):
            details.append({"field": f"row {row_number}", "message": f"Invalid region_id {region_id!r}."})
            continue
        if region_id in seen:
            details.append({"field": f"row {row_number}", "message": f"Duplicate region_id {region_id}."})
            continue
        seen.add(region_id)
        try:
            eligible = int(str(row["eligible_voters"]).strip())
            turnout = float(str(row["turnout_probability"]).strip())
            blank = float(str(row["blank_rate"]).strip())
            invalid = float(str(row["invalid_rate"]).strip())
            preferences = {
                candidate_id: float(str(row[f"pref_{candidate_id}"]).strip())
                for candidate_id in candidate_ids
            }
        except ValueError:
            details.append(
                {
                    "field": f"row {row_number}",
                    "message": "A numeric column is not a number. Formulas and text are not evaluated.",
                }
            )
            continue
        if eligible < 0:
            details.append({"field": f"row {row_number}", "message": "eligible_voters cannot be negative."})
            continue
        if not 0 <= turnout <= 1 or not 0 <= blank <= 1 or not 0 <= invalid <= 1:
            details.append({"field": f"row {row_number}", "message": "Rates must be between 0 and 1."})
            continue
        if blank + invalid > 1:
            details.append({"field": f"row {row_number}", "message": "blank_rate + invalid_rate exceeds 1."})
            continue
        issue = probability_issue(list(preferences.values()), f"row {row_number} preferences")
        if issue:
            details.append({"field": f"row {row_number}", "message": issue})
            continue
        name = str(row["name"]).strip()
        if not name or len(name) > 120:
            details.append({"field": f"row {row_number}", "message": "Region name must be 1 to 120 characters."})
            continue
        regions.append(
            RegionSpec(
                id=region_id,
                name=name,
                eligible_voters=eligible,
                turnout_probability=turnout,
                preferences=preferences,
                blank_rate=blank,
                invalid_rate=invalid,
            )
        )
    if details:
        raise SpecError("The CSV was rejected.", details=details[:50])
    if not regions:
        raise SpecError("The CSV did not contain a usable region.")
    candidates = [
        CandidateSpec(id=candidate_id, name=_display_name(candidate_id))
        for candidate_id in candidate_ids
    ]
    warnings.append(
        "Candidate display names were derived from column ids. Rename them in the editor if needed."
    )
    specification = ElectionSpecification(
        title=title,
        description=description or f"Imported from {safe_filename(filename)}.",
        candidates=candidates,
        regions=regions,
        voting_method=voting_method,  # type: ignore[arg-type]
        seats=seats,
        iterations=iterations,
        seed=seed,
        empirical_data=True,
        assumptions=[
            Assumption(
                field="regions",
                source="user",
                note=(
                    "Regions, populations, turnout, ballot rates, and preferences were read from "
                    f"{safe_filename(filename)}."
                ),
            ),
            Assumption(
                field="candidates.names",
                source="inferred",
                note="Display names were derived from preference column ids.",
            ),
            Assumption(
                field="voting_method",
                source="user",
                note="Voting method, iterations, and seed came from the import form.",
            ),
        ],
    )
    return specification, warnings


def _display_name(candidate_id: str) -> str:
    return " ".join(part.capitalize() for part in candidate_id.split("-"))
