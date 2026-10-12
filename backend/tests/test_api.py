"""API workflow, imports, exports, and security boundaries."""

from __future__ import annotations

import json
import os

import pytest
from app.config import Settings
from app.content.examples import REGION_CSV
from app.main import create_app
from fastapi.testclient import TestClient


def test_health_ready_and_examples(client: TestClient) -> None:
    assert client.get("/api/v1/health").json()["status"] == "ok"
    assert client.get("/api/v1/ready").json()["database"] == "ok"
    examples = client.get("/api/v1/examples").json()["prompts"]
    assert any(item["id"] == "four-candidate-regional" for item in examples)
    assert "Binomial" in client.get("/api/v1/content/methodology").json()["markdown"]
    csv_body = client.get("/api/v1/examples/datasets/regions.csv").text
    assert "pref_alice" in csv_body


def test_full_simulation_roundtrip(client: TestClient) -> None:
    interpreted = client.post(
        "/api/v1/interpret",
        json={
            "prompt": (
                "Plurality election. Candidates Alpha and Beta. 100 eligible voters. "
                "Turnout of 100%. Alpha 100%, Beta 0%. 8 iterations. Seed 3."
            )
        },
    )
    assert interpreted.status_code == 200
    assert interpreted.json()["interpreter_mode"] == "deterministic"
    spec = interpreted.json()["specification"]
    created = client.post("/api/v1/simulations", json={"specification": spec, "project_name": "Lab"})
    assert created.status_code == 201
    simulation_id = created.json()["id"]
    assert created.json()["status"] == "draft"
    assert created.json()["hypothetical"] is True
    executed = client.post(f"/api/v1/simulations/{simulation_id}/execute", json={"wait": True})
    assert executed.status_code == 200
    assert executed.json()["status"] == "completed"
    results = client.get(f"/api/v1/simulations/{simulation_id}/results").json()
    alpha = next(item for item in results["scenarios"][0]["candidates"] if item["name"] == "Alpha")
    assert alpha["mean_votes"] == 100
    assert alpha["sole_win_frequency"] == 1
    assert results["hypothetical"] is True
    exported = client.get(f"/api/v1/simulations/{simulation_id}/export.csv")
    assert exported.status_code == 200
    assert b"Alpha" in exported.content
    pdf = client.get(f"/api/v1/simulations/{simulation_id}/export.pdf")
    assert pdf.content.startswith(b"%PDF")
    assert b"Hypothetical" in pdf.content
    listed = client.get("/api/v1/simulations").json()
    assert listed["total"] == 1
    duplicate = client.post(f"/api/v1/simulations/{simulation_id}/duplicate")
    assert duplicate.status_code == 201
    assert duplicate.json()["status"] == "draft"
    assert client.delete(f"/api/v1/simulations/{duplicate.json()['id']}").status_code == 204


def test_validation_error_shape(client: TestClient) -> None:
    response = client.post(
        "/api/v1/simulations",
        json={
            "specification": {
                "title": "Bad",
                "candidates": [{"id": "a", "name": "A"}, {"id": "a", "name": "B"}],
                "regions": [{
                    "id": "r",
                    "name": "R",
                    "eligible_voters": 10,
                    "turnout_probability": 1,
                    "preferences": {"a": 1},
                }],
                "voting_method": "plurality",
                "iterations": 1,
                "seed": 1,
            }
        },
    )
    assert response.status_code == 400
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert body["details"]


def test_missing_simulation_and_results_before_run(client: TestClient) -> None:
    assert client.get("/api/v1/simulations/missing").status_code == 404
    created = client.post(
        "/api/v1/simulations",
        json={
            "specification": {
                "title": "Draft",
                "candidates": [{"id": "a", "name": "A"}],
                "regions": [{
                    "id": "r", "name": "R", "eligible_voters": 5,
                    "turnout_probability": 1, "preferences": {"a": 1},
                }],
                "voting_method": "plurality",
                "iterations": 1,
                "seed": 1,
            }
        },
    )
    simulation_id = created.json()["id"]
    results = client.get(f"/api/v1/simulations/{simulation_id}/results")
    assert results.status_code == 409
    status = client.get(f"/api/v1/simulations/{simulation_id}/status").json()
    assert status["status"] == "draft"


def test_csv_import_and_rejection(client: TestClient) -> None:
    good = client.post(
        "/api/v1/imports/csv",
        files={"file": ("regions.csv", REGION_CSV, "text/csv")},
        data={"title": "Imported", "voting_method": "plurality", "iterations": "20", "seed": "4"},
    )
    assert good.status_code == 200
    spec = good.json()["specification"]
    assert spec["empirical_data"] is True
    assert len(spec["regions"]) == 3
    bad = client.post(
        "/api/v1/imports/csv",
        files={"file": ("bad.csv", "region_id,name\n../etc,passwd\n", "text/csv")},
        data={"title": "Bad", "voting_method": "plurality", "iterations": "2", "seed": "1"},
    )
    assert bad.status_code == 400
    empty = client.post(
        "/api/v1/imports/csv",
        files={"file": ("empty.csv", "", "text/csv")},
        data={"title": "Empty", "voting_method": "plurality", "iterations": "2", "seed": "1"},
    )
    assert empty.status_code == 400


def test_formula_injection_is_prefixed(client: TestClient) -> None:
    created = client.post(
        "/api/v1/simulations",
        json={
            "specification": {
                "title": "Formula",
                "candidates": [{"id": "a", "name": "=2+2"}, {"id": "b", "name": "Safe"}],
                "regions": [{
                    "id": "r", "name": "R", "eligible_voters": 4,
                    "turnout_probability": 1, "preferences": {"a": 1, "b": 0},
                }],
                "voting_method": "plurality",
                "iterations": 1,
                "seed": 1,
            }
        },
    )
    simulation_id = created.json()["id"]
    client.post(f"/api/v1/simulations/{simulation_id}/execute", json={"wait": True})
    csv_text = client.get(f"/api/v1/simulations/{simulation_id}/export.csv").text
    assert "'=2+2" in csv_text


def test_api_token_required(tmp_path: pytest.TempPathFactory) -> None:
    application = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path}/secure.db",
            api_token="local-test-token",
            environment="test",
        )
    )
    with TestClient(application) as secured:
        assert secured.get("/api/v1/health").status_code == 200
        assert secured.get("/api/v1/simulations").status_code == 401
        ok = secured.get("/api/v1/simulations", headers={"Authorization": "Bearer local-test-token"})
        assert ok.status_code == 200


def test_oversized_body_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/interpret",
        content=b'{"prompt":"' + b"a" * 3_000_000 + b'"}',
        headers={"Content-Type": "application/json", "Content-Length": "3000020"},
    )
    assert response.status_code == 413


def test_json_export_contains_configuration_and_results(client: TestClient) -> None:
    created = client.post(
        "/api/v1/simulations",
        json={
            "specification": {
                "title": "JSON",
                "candidates": [{"id": "a", "name": "A"}],
                "regions": [{
                    "id": "r", "name": "R", "eligible_voters": 3,
                    "turnout_probability": 1, "preferences": {"a": 1},
                }],
                "voting_method": "plurality",
                "iterations": 2,
                "seed": 9,
            }
        },
    )
    simulation_id = created.json()["id"]
    client.post(f"/api/v1/simulations/{simulation_id}/execute", json={"wait": True})
    payload = json.loads(client.get(f"/api/v1/simulations/{simulation_id}/export.json").content)
    assert payload["hypothetical"] is True
    assert payload["specification"]["seed"] == 9
    assert payload["results"]["scenarios"][0]["candidates"][0]["mean_votes"] == 3


@pytest.mark.postgres
def test_postgres_migration_roundtrip() -> None:
    url = os.getenv("DATABASE_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip("PostgreSQL DATABASE_URL is not set")
    settings = Settings(database_url=url, environment="test")
    application = create_app(settings)
    with TestClient(application) as postgres_client:
        response = postgres_client.post(
            "/api/v1/simulations",
            json={
                "specification": {
                    "title": "Postgres",
                    "candidates": [{"id": "a", "name": "A"}],
                    "regions": [{
                        "id": "r", "name": "R", "eligible_voters": 2,
                        "turnout_probability": 1, "preferences": {"a": 1},
                    }],
                    "voting_method": "plurality",
                    "iterations": 1,
                    "seed": 1,
                }
            },
        )
        assert response.status_code == 201
        simulation_id = response.json()["id"]
        rerun = postgres_client.get(f"/api/v1/simulations/{simulation_id}")
        assert rerun.status_code == 200
        assert rerun.json()["title"] == "Postgres"
        postgres_client.delete(f"/api/v1/simulations/{simulation_id}")
