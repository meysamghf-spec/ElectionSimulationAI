"""Accounts, ownership, sessions, and production configuration."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from app.auth.bootstrap import ensure_initial_admin
from app.auth.passwords import verify_password
from app.config import Settings, validate_production
from app.db.migrate import mark_interrupted, upgrade_database
from app.db.models import Simulation, User
from app.db.session import build_session_factory
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import func, select

PASSWORD = "correct-horse-battery"
OTHER_PASSWORD = "another-strong-passphrase"


def _accounts(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": f"sqlite:///{tmp_path}/accounts.db",
        "environment": "test",
        "auth_mode": "accounts",
        "allow_registration": True,
        "api_token": None,
        "auth_rate_limit_per_minute": 1000,
        "rate_limit_per_minute": 1000,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _spec(title: str = "Owned") -> dict[str, object]:
    return {
        "title": title,
        "candidates": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}],
        "regions": [
            {
                "id": "r",
                "name": "Region",
                "eligible_voters": 10,
                "turnout_probability": 1,
                "preferences": {"a": 1, "b": 0},
                "blank_rate": 0,
                "invalid_rate": 0,
            }
        ],
        "voting_method": "plurality",
        "iterations": 2,
        "seed": 3,
    }


def _csrf(client: TestClient) -> dict[str, str]:
    token = client.cookies.get("esim_csrf")
    assert token
    return {"X-CSRF-Token": token}


def _register(client: TestClient, email: str, password: str = PASSWORD) -> None:
    response = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["authenticated"] is True
    assert body["email"] == email
    assert "password" not in body
    assert password not in response.text
    assert "esim_session" not in response.text
    assert client.cookies.get("esim_session")


def test_cross_user_resources_are_hidden(tmp_path: Path) -> None:
    application = create_app(_accounts(tmp_path))
    with TestClient(application) as client:
        _register(client, "ada@example.com")
        created = client.post(
            "/api/v1/simulations",
            json={"specification": _spec("Ada"), "project_name": "Ada project"},
            headers=_csrf(client),
        )
        assert created.status_code == 201, created.text
        simulation_id = created.json()["id"]
        client.post(f"/api/v1/simulations/{simulation_id}/execute", json={"wait": True}, headers=_csrf(client))
        ada_session = client.cookies.get("esim_session")
        ada_csrf = client.cookies.get("esim_csrf")
        assert ada_session and ada_csrf

        client.cookies.clear()
        _register(client, "grace@example.com", OTHER_PASSWORD)
        hidden = client.get(f"/api/v1/simulations/{simulation_id}")
        assert hidden.status_code == 404
        listing = client.get("/api/v1/simulations")
        assert listing.status_code == 200
        assert listing.json()["total"] == 0
        assert client.get("/api/v1/projects").json()["items"] == []
        for method, path, payload in (
            ("PATCH", f"/api/v1/simulations/{simulation_id}", {"specification": _spec("Stolen")}),
            ("DELETE", f"/api/v1/simulations/{simulation_id}", None),
            ("POST", f"/api/v1/simulations/{simulation_id}/execute", {"wait": True}),
            ("POST", f"/api/v1/simulations/{simulation_id}/cancel", {}),
            ("POST", f"/api/v1/simulations/{simulation_id}/duplicate", {}),
            (
                "POST",
                f"/api/v1/simulations/{simulation_id}/compare",
                {"left_scenario_id": "baseline", "right_scenario_id": "baseline"},
            ),
            ("POST", f"/api/v1/simulations/{simulation_id}/sensitivity", {}),
        ):
            response = client.request(method, path, json=payload, headers=_csrf(client))
            assert response.status_code == 404, (method, path, response.text)
        for path in (
            f"/api/v1/simulations/{simulation_id}/results",
            f"/api/v1/simulations/{simulation_id}/status",
            f"/api/v1/simulations/{simulation_id}/export.csv",
            f"/api/v1/simulations/{simulation_id}/export.json",
            f"/api/v1/simulations/{simulation_id}/export.pdf",
        ):
            response = client.get(path)
            assert response.status_code == 404, path

        db = application.state.session_factory()
        try:
            record = db.get(Simulation, simulation_id)
            assert record is not None
            assert record.status == "completed"
            assert record.owner_id is not None
        finally:
            db.close()

        client.cookies.clear()
        client.cookies.set("esim_session", ada_session)
        client.cookies.set("esim_csrf", ada_csrf)
        own = client.get(f"/api/v1/simulations/{simulation_id}")
        assert own.status_code == 200
        assert own.json()["results"]["scenarios"][0]["candidates"][0]["mean_votes"] == 10


def test_invalid_session_and_csrf(tmp_path: Path) -> None:
    application = create_app(_accounts(tmp_path))
    with TestClient(application) as client:
        assert client.get("/api/v1/simulations").status_code == 401
        client.cookies.set("esim_session", "not-a-valid-session")
        assert client.get("/api/v1/simulations").status_code == 401
        client.cookies.clear()
        _register(client, "ada@example.com")
        missing = client.post("/api/v1/simulations", json={"specification": _spec()})
        assert missing.status_code == 403
        assert missing.json()["error"]["code"] == "csrf"
        wrong = client.post(
            "/api/v1/simulations",
            json={"specification": _spec()},
            headers={"X-CSRF-Token": "not-the-token"},
        )
        assert wrong.status_code == 403
        me = client.get("/api/v1/auth/me")
        assert me.json()["authenticated"] is True
        assert me.json()["csrf_token"]
        logout = client.post("/api/v1/auth/logout", headers=_csrf(client))
        assert logout.status_code == 200
        assert client.get("/api/v1/simulations").status_code == 401


def test_login_does_not_store_or_echo_the_password(tmp_path: Path) -> None:
    application = create_app(_accounts(tmp_path))
    with TestClient(application) as client:
        _register(client, "ada@example.com")
        client.cookies.clear()
        mixed = client.post("/api/v1/auth/login", json={"email": "Ada@Example.com", "password": PASSWORD})
        assert mixed.status_code == 200
        client.cookies.clear()
        wrong = client.post(
            "/api/v1/auth/login",
            json={"email": "ada@example.com", "password": "wrong-password-1"},
        )
        missing = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "wrong-password-1"},
        )
        assert wrong.status_code == 401
        assert missing.status_code == 401
        assert wrong.json()["error"]["message"] == missing.json()["error"]["message"]
        ok = client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": PASSWORD})
        assert ok.status_code == 200
        assert PASSWORD not in ok.text
        db = application.state.session_factory()
        try:
            user = db.scalar(select(User).where(User.email == "ada@example.com"))
            assert user is not None
            assert user.password_hash != PASSWORD
            assert PASSWORD not in user.password_hash
            assert user.password_hash.startswith("$argon2")
            assert verify_password(user.password_hash, PASSWORD)
        finally:
            db.close()


def test_registration_validation_and_closure(tmp_path: Path) -> None:
    closed = create_app(_accounts(tmp_path, allow_registration=False))
    with TestClient(closed) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "ada@example.com", "password": PASSWORD},
        )
        assert response.status_code == 403
        short = client.post("/api/v1/auth/login", json={"email": "not-an-email", "password": "short"})
        assert short.status_code == 401

    opened = create_app(_accounts(tmp_path / "open", allow_registration=True))
    with TestClient(opened) as client:
        short = client.post(
            "/api/v1/auth/register",
            json={"email": "ada@example.com", "password": "short-pass"},
        )
        assert short.status_code == 400
        assert short.json()["error"]["details"][0]["field"] == "password"
        _register(client, "ada@example.com")
        client.cookies.clear()
        duplicate = client.post(
            "/api/v1/auth/register",
            json={"email": "ada@example.com", "password": OTHER_PASSWORD},
        )
        assert duplicate.status_code == 409


def test_auth_rate_limit(tmp_path: Path) -> None:
    application = create_app(_accounts(tmp_path, auth_rate_limit_per_minute=2))
    with TestClient(application) as client:
        for _ in range(2):
            assert client.post(
                "/api/v1/auth/login",
                json={"email": "ada@example.com", "password": PASSWORD},
            ).status_code == 401
        limited = client.post(
            "/api/v1/auth/login",
            json={"email": "ada@example.com", "password": PASSWORD},
        )
        assert limited.status_code == 429
        assert limited.json()["error"]["code"] == "rate_limited"


def test_shared_token_is_not_an_account_backdoor(tmp_path: Path) -> None:
    token = "this-token-must-not-open-accounts"
    application = create_app(_accounts(tmp_path, api_token=token))
    with TestClient(application) as client:
        denied = client.get("/api/v1/simulations", headers={"Authorization": f"Bearer {token}"})
        assert denied.status_code == 401
        _register(client, "ada@example.com")
        created = client.post(
            "/api/v1/simulations",
            json={"specification": _spec()},
            headers=_csrf(client),
        )
        assert created.status_code == 201


def test_development_and_accounts_do_not_share_rows(tmp_path: Path) -> None:
    database = tmp_path / "shared.db"
    dev = Settings(database_url=f"sqlite:///{database}", environment="test", auth_mode="development")
    with TestClient(create_app(dev)) as client:
        created = client.post("/api/v1/simulations", json={"specification": _spec("Local")})
        assert created.status_code == 201
        local_id = created.json()["id"]
    accounts = Settings(
        database_url=f"sqlite:///{database}",
        environment="test",
        auth_mode="accounts",
        allow_registration=True,
        auth_rate_limit_per_minute=100,
    )
    with TestClient(create_app(accounts)) as client:
        _register(client, "ada@example.com")
        assert client.get(f"/api/v1/simulations/{local_id}").status_code == 404
        owned = client.post("/api/v1/simulations", json={"specification": _spec("Ada")}, headers=_csrf(client))
        owned_id = owned.json()["id"]
    with TestClient(create_app(dev)) as client:
        assert client.get(f"/api/v1/simulations/{owned_id}").status_code == 404
        assert client.get(f"/api/v1/simulations/{local_id}").status_code == 200


def test_restart_marks_queued_work_failed(tmp_path: Path) -> None:
    application = create_app(_accounts(tmp_path))
    with TestClient(application) as client:
        _register(client, "ada@example.com")
        created = client.post("/api/v1/simulations", json={"specification": _spec()}, headers=_csrf(client))
        simulation_id = created.json()["id"]
        db = application.state.session_factory()
        try:
            record = db.get(Simulation, simulation_id)
            assert record is not None
            record.status = "running"
            db.commit()
            assert mark_interrupted(db) == 1
        finally:
            db.close()
        status = client.get(f"/api/v1/simulations/{simulation_id}/status")
        assert status.status_code == 200
        assert status.json()["status"] == "failed"
        assert "Interrupted by process restart" in status.json()["error_message"]


def test_meta_does_not_reveal_secrets(tmp_path: Path) -> None:
    token = "local-test-token"
    model_key = "sk-live-should-not-leak"
    application = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path}/meta.db",
            environment="test",
            auth_mode="development",
            api_token=token,
            llm_api_key=model_key,
            initial_admin_password="another-admin-secret",
        )
    )
    with TestClient(application) as client:
        hidden = client.get("/api/v1/meta")
        assert hidden.status_code == 401
        meta = client.get("/api/v1/meta", headers={"Authorization": f"Bearer {token}"})
        assert meta.status_code == 200
        text = meta.text
        assert token not in text
        assert model_key not in text
        assert "another-admin-secret" not in text
        assert meta.json()["auth_mode"] == "development"


def test_private_mode_requires_the_deployment_token(tmp_path: Path) -> None:
    application = create_app(
        Settings(
            database_url=f"sqlite:///{tmp_path}/private.db",
            environment="test",
            auth_mode="private",
            api_token="a" * 32,
        )
    )
    with TestClient(application) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/simulations").status_code == 401
        ok = client.get("/api/v1/simulations", headers={"Authorization": "Bearer " + ("a" * 32)})
        assert ok.status_code == 200
        headers = {"Authorization": "Bearer " + ("a" * 32)}
        denied_login = client.post(
            "/api/v1/auth/login",
            json={"email": "ada@example.com", "password": PASSWORD},
            headers=headers,
        )
        assert denied_login.status_code == 404


def test_production_rejects_insecure_defaults() -> None:
    long_password = "a-sufficiently-long-password"
    postgres = f"postgresql+psycopg://election:{long_password}@db:5432/election"
    with pytest.raises(RuntimeError, match="AUTH_MODE"):
        validate_production(
            Settings(environment="production", auth_mode="development", database_url=postgres, cors_origins="https://example.com")
        )
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        validate_production(
            Settings(
                environment="production",
                auth_mode="accounts",
                database_url="sqlite:///./data/elections.db",
                cors_origins="https://example.com",
            )
        )
    with pytest.raises(RuntimeError, match="password"):
        validate_production(
            Settings(
                environment="production",
                auth_mode="accounts",
                database_url="postgresql+psycopg://election:change-me-local-only@db:5432/election",
                cors_origins="https://example.com",
            )
        )
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        validate_production(
            Settings(environment="production", auth_mode="accounts", database_url=postgres, cors_origins="*")
        )
    with pytest.raises(RuntimeError, match="API_TOKEN"):
        validate_production(
            Settings(
                environment="production",
                auth_mode="private",
                database_url=postgres,
                cors_origins="https://example.com",
                api_token="short-token",
            )
        )
    validate_production(
        Settings(
            environment="production",
            auth_mode="accounts",
            database_url=postgres,
            cors_origins="https://example.com",
            trusted_proxy_cidrs="172.28.10.10/32",
        )
    )
    validate_production(
        Settings(
            environment="production",
            auth_mode="private",
            database_url=postgres,
            cors_origins="https://example.com",
            api_token="p" * 32,
            trusted_proxy_cidrs="172.28.10.10/32",
        )
    )
    validate_production(Settings(environment="development", auth_mode="development"))
    assert Settings(environment="production").cookie_secure is True
    assert Settings(environment="development").cookie_secure is False


def test_production_rejects_open_registration_and_world_proxies() -> None:
    long_password = "a-sufficiently-long-password"
    postgres = f"postgresql+psycopg://election:{long_password}@db:5432/election"

    def settings(**overrides: object) -> Settings:
        values: dict[str, object] = {
            "environment": "production",
            "auth_mode": "accounts",
            "database_url": postgres,
            "cors_origins": "https://example.com",
            "trusted_proxy_cidrs": "172.28.10.10/32",
        }
        values.update(overrides)
        return Settings(**values)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="ALLOW_REGISTRATION"):
        validate_production(settings(allow_registration=True))
    with pytest.raises(RuntimeError, match="TRUSTED_PROXY_CIDRS"):
        validate_production(settings(trusted_proxy_cidrs=""))
    with pytest.raises(RuntimeError, match="0.0.0.0/0"):
        validate_production(settings(trusted_proxy_cidrs="0.0.0.0/0"))
    with pytest.raises(RuntimeError, match="::/0"):
        validate_production(settings(trusted_proxy_cidrs="::/0"))
    with pytest.raises(RuntimeError, match="TRUSTED_PROXY_CIDRS"):
        validate_production(settings(trusted_proxy_cidrs="not-a-network"))


def test_initial_admin_is_hashed_and_required(tmp_path: Path) -> None:
    settings = Settings(
        environment="production",
        auth_mode="accounts",
        database_url=f"sqlite:///{tmp_path}/admin.db",
        allow_registration=False,
        initial_admin_email="Admin@Example.com",
        initial_admin_password=PASSWORD,
    )
    upgrade_database(settings)
    _engine, factory = build_session_factory(settings)
    db = factory()
    try:
        ensure_initial_admin(db, settings)
        user = db.scalar(select(User))
        assert user is not None
        assert user.email == "admin@example.com"
        assert verify_password(user.password_hash, PASSWORD)
        assert user.password_hash != PASSWORD
        ensure_initial_admin(db, settings)
        assert int(db.scalar(select(func.count()).select_from(User)) or 0) == 1
    finally:
        db.close()
        _engine.dispose()

    empty = Settings(
        environment="production",
        auth_mode="accounts",
        database_url=f"sqlite:///{tmp_path}/empty.db",
        allow_registration=False,
    )
    upgrade_database(empty)
    engine, factory = build_session_factory(empty)
    db = factory()
    try:
        with pytest.raises(RuntimeError, match="INITIAL_ADMIN_EMAIL"):
            ensure_initial_admin(db, empty)
    finally:
        db.close()
        engine.dispose()


def test_cli_creates_a_user_from_the_environment(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{tmp_path}/cli.db"
    env["CREATE_USER_EMAIL"] = "person@example.com"
    env["CREATE_USER_PASSWORD"] = PASSWORD
    env.pop("INITIAL_ADMIN_PASSWORD", None)
    backend = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "-m", "app.auth.cli"],
        cwd=backend,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert PASSWORD not in completed.stdout
    settings = Settings(database_url=env["DATABASE_URL"], environment="test")
    engine, factory = build_session_factory(settings)
    db = factory()
    try:
        user = db.scalar(select(User).where(User.email == "person@example.com"))
        assert user is not None
        assert verify_password(user.password_hash, PASSWORD)
    finally:
        db.close()
        engine.dispose()
