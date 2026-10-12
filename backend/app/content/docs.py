"""Load trusted documentation files. Names are not taken from user paths."""

from pathlib import Path

from app.errors import NotFoundError

ALLOWED_DOCS = {
    "methodology": "methodology.md",
    "privacy": "privacy.md",
}


def read_document(name: str) -> str:
    filename = ALLOWED_DOCS.get(name)
    if filename is None:
        raise NotFoundError("Document not found.")
    for candidate in _candidates(filename):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    raise NotFoundError(f"Document {filename} is not available in this installation.")


def _candidates(filename: str) -> list[Path]:
    root = Path(__file__).resolve().parents[3]
    backend = Path(__file__).resolve().parents[2]
    return [
        root / "docs" / filename,
        backend / "docs" / filename,
        Path("/app/docs") / filename,
    ]
