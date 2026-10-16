"""CSV import -> saved simulation -> execution -> results -> export, on SQLite and (when configured) PostgreSQL."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient

# Persian region names check that UTF-8 survives the import, the database, and the CSV export.
PERSIAN_CSV = (
    "region_id,name,eligible_voters,turnout_probability,blank_rate,invalid_rate,pref_alpha,pref_beta\n"
    "north,منطقه شمال,1200,0.6,0.01,0.02,0.55,0.45\n"
    "south,منطقه جنوب,800,0.5,0.0,0.03,0.40,0.60\n"
).encode()


def _database_urls() -> list[str]:
    urls = ["sqlite"]
    if os.getenv("DATABASE_URL", "").startswith("postgresql"):
        urls.append("postgresql")
    return urls


@pytest.fixture(params=_database_urls())
def any_db_client(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[TestClient]:
    if request.param == "sqlite":
        url = f"sqlite:///{tmp_path}/csv-e2e.db"
    else:
        url = os.environ["DATABASE_URL"]
    settings = Settings(
        database_url=url,
        environment="test",
        api_token=None,
        rate_limit_per_minute=10_000,
        max_iterations=5_000,
    )
    with TestClient(create_app(settings)) as client:
        yield client


def _import(client: TestClient, content: bytes, filename: str) -> dict:
    response = client.post(
        "/api/v1/imports/csv",
        files={"file": (filename, content, "text/csv")},
        data={"title": "CSV import check", "voting_method": "plurality", "iterations": "200", "seed": "42"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_csv_import_runs_end_to_end(any_db_client: TestClient) -> None:
    client = any_db_client
    imported = _import(client, PERSIAN_CSV, "regions.csv")
    assert imported["hypothetical"] is True
    assert imported["validation"]["valid"] is True
    spec = imported["specification"]
    assert {region["name"] for region in spec["regions"]} == {"منطقه شمال", "منطقه جنوب"}
    assert {candidate["id"] for candidate in spec["candidates"]} == {"alpha", "beta"}

    created = client.post("/api/v1/simulations", json={"specification": spec})
    assert created.status_code == 201, created.text
    simulation_id = created.json()["id"]
    executed = client.post(f"/api/v1/simulations/{simulation_id}/execute", json={"wait": True})
    assert executed.status_code == 200
    assert executed.json()["status"] == "completed"

    results = client.get(f"/api/v1/simulations/{simulation_id}/results").json()
    assert results["hypothetical"] is True
    scenario = results["scenarios"][0]
    assert scenario["eligible_voters"] == 2000
    assert scenario["iterations_completed"] == 200
    total_share = sum(candidate["mean_share"] for candidate in scenario["candidates"])
    assert total_share == pytest.approx(1.0, abs=1e-6)

    regional = client.get(f"/api/v1/simulations/{simulation_id}/export.csv?view=regional")
    assert regional.status_code == 200
    assert "منطقه شمال" in regional.content.decode("utf-8-sig")
    assert client.delete(f"/api/v1/simulations/{simulation_id}").status_code == 204


def test_bundled_example_csv_imports(any_db_client: TestClient) -> None:
    client = any_db_client
    example = client.get("/api/v1/examples/datasets/regions.csv")
    assert example.status_code == 200
    imported = _import(client, example.content, "example.csv")
    assert imported["validation"]["valid"] is True
    assert len(imported["specification"]["regions"]) >= 1


def test_malformed_csv_is_rejected_with_a_clear_message(any_db_client: TestClient) -> None:
    response = any_db_client.post(
        "/api/v1/imports/csv",
        files={"file": ("bad.csv", b"region_id,name\nx,X\n", "text/csv")},
        data={"title": "Bad", "voting_method": "plurality", "iterations": "10", "seed": "1"},
    )
    assert response.status_code == 400
    assert "missing required columns" in response.text
