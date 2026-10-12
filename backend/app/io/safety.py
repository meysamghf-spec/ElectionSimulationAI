"""Upload and spreadsheet safety helpers."""

from __future__ import annotations

import re
from pathlib import Path


def safe_filename(name: str | None) -> str:
    base = Path(name or "upload").name
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", base)[:200]
    if cleaned in {"", ".", ".."}:
        return "upload"
    return cleaned


def csv_cell(value: object) -> object:
    """Prevent spreadsheet formula injection in string cells.

    Numbers stay numbers. Strings that begin with a formula trigger are prefixed
    with a single quote.
    """

    if isinstance(value, bool) or value is None:
        return "" if value is None else value
    if isinstance(value, int | float):
        return value
    text = str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text
