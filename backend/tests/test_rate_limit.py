"""Client identity for rate limits. Forwarded headers count only from a trusted peer."""

from pathlib import Path

from app.config import Settings
from app.main import create_app
from app.security import rate_limit_identity
from fastapi.testclient import TestClient

PASSWORD = "correct-horse-battery"
TRUSTED = "172.28.10.10/32"


def test_identity_ignores_forwarded_headers_from_untrusted_peers() -> None:
    assert rate_limit_identity("203.0.113.9", "198.51.100.7", "") == "203.0.113.9"
    assert rate_limit_identity("203.0.113.9", "198.51.100.7", TRUSTED) == "203.0.113.9"
    assert rate_limit_identity("testclient", "198.51.100.7", TRUSTED) == "testclient"
    assert rate_limit_identity(None, "198.51.100.7", TRUSTED) == "unknown"


def test_identity_uses_one_forwarded_address_from_the_trusted_proxy() -> None:
    assert rate_limit_identity("172.28.10.10", "203.0.113.5", TRUSTED) == "203.0.113.5"
    assert rate_limit_identity("172.28.10.10", "2001:db8::5", TRUSTED) == "2001:db8::5"
    assert rate_limit_identity("172.28.10.10", "[2001:db8::5]", TRUSTED) == "2001:db8::5"
    assert rate_limit_identity("172.28.10.10", "203.0.113.5, 198.51.100.2", TRUSTED) == "172.28.10.10"
    assert rate_limit_identity("172.28.10.10", "not-an-ip", TRUSTED) == "172.28.10.10"
    assert rate_limit_identity("172.28.10.10", "", TRUSTED) == "172.28.10.10"


def _accounts(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path}/limits.db",
        environment="test",
        auth_mode="accounts",
        allow_registration=False,
        auth_rate_limit_per_minute=1,
        trusted_proxy_cidrs=TRUSTED,
    )


def _login(client: TestClient, forwarded: str | None = None) -> int:
    headers = {"X-Forwarded-For": forwarded} if forwarded is not None else None
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": PASSWORD},
        headers=headers,
    )
    return response.status_code


def test_untrusted_peer_shares_one_auth_bucket(tmp_path: Path) -> None:
    application = create_app(_accounts(tmp_path))
    with TestClient(application) as client:
        assert _login(client, "203.0.113.5") == 401
        assert _login(client, "203.0.113.6") == 429


def test_trusted_proxy_gets_a_separate_auth_bucket_per_client(tmp_path: Path) -> None:
    application = create_app(_accounts(tmp_path))
    with TestClient(application, client=("172.28.10.10", 50000)) as client:
        assert _login(client, "203.0.113.5") == 401
        assert _login(client, "203.0.113.6") == 401
        assert _login(client, "203.0.113.5") == 429
        assert _login(client, "203.0.113.5, 198.51.100.2") == 401
        assert _login(client, "203.0.113.5, 198.51.100.8") == 429
