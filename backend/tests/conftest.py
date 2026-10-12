"""Shared API fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from app.config import Settings
from app.main import create_app
from app.schemas.spec import ElectionSpecification
from fastapi.testclient import TestClient


@pytest.fixture
def settings(tmp_path: pytest.TempPathFactory) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path}/test.db",
        environment="test",
        api_token=None,
        rate_limit_per_minute=10_000,
        max_iterations=5_000,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    application = create_app(settings)
    with TestClient(application) as test_client:
        yield test_client


def specification(**overrides: object) -> ElectionSpecification:
    payload: dict[str, object] = {
        "title": "Test election",
        "candidates": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}],
        "regions": [
            {
                "id": "r",
                "name": "Region",
                "eligible_voters": 100,
                "turnout_probability": 1,
                "preferences": {"a": 1.0, "b": 0.0},
                "blank_rate": 0,
                "invalid_rate": 0,
            }
        ],
        "voting_method": "plurality",
        "iterations": 4,
        "seed": 1,
    }
    payload.update(overrides)
    return ElectionSpecification.model_validate(payload)
