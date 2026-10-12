"""Production environment checks name variables and keep secret values out of the text."""

from app.deploy_check import production_problems

PASSWORD = "unique-db-secret-value-99"
TOKEN = "browser-must-not-see-this-token"
ADMIN = "correct-horse-battery"


def _valid(**overrides: str) -> dict[str, str]:
    env = {
        "ENVIRONMENT": "production",
        "AUTH_MODE": "accounts",
        "DATABASE_URL": f"postgresql+psycopg://election:{PASSWORD}@db:5432/election",
        "CORS_ORIGINS": "https://example.com",
        "POSTGRES_PASSWORD": PASSWORD,
        "SITE_ADDRESS": "example.com",
        "ACME_EMAIL": "certs@example.com",
        "TRUSTED_PROXY_CIDRS": "172.28.10.10/32",
        "API_INTERNAL_URL": "http://api:8000",
        "ALLOW_REGISTRATION": "false",
        "INITIAL_ADMIN_EMAIL": "operator@example.com",
        "INITIAL_ADMIN_PASSWORD": ADMIN,
    }
    env.update(overrides)
    return env


def test_valid_production_env_is_accepted() -> None:
    assert production_problems(_valid()) == []


def test_checker_names_missing_variables_and_hides_secrets() -> None:
    env = _valid(
        SITE_ADDRESS="",
        CORS_ORIGINS="https://other.example",
        ALLOW_REGISTRATION="true",
        NEXT_PUBLIC_API_TOKEN=TOKEN,
        API_INTERNAL_URL="http://127.0.0.1:8000",
        TRUSTED_PROXY_CIDRS="0.0.0.0/0",
    )
    text = "\n".join(production_problems(env))
    assert "SITE_ADDRESS is required." in text
    assert "ALLOW_REGISTRATION must be false." in text
    assert "NEXT_PUBLIC_API_TOKEN must be unset." in text
    assert "API_INTERNAL_URL must be the Docker network address" in text
    assert "0.0.0.0/0" in text
    assert PASSWORD not in text
    assert TOKEN not in text
    assert ADMIN not in text
    assert "postgresql+psycopg" not in text


def test_existing_users_flag_replaces_the_initial_password() -> None:
    env = _valid(INITIAL_ADMIN_EMAIL="", INITIAL_ADMIN_PASSWORD="")
    assert any("INITIAL_ADMIN_EMAIL" in problem for problem in production_problems(env))
    assert production_problems(_valid(INITIAL_ADMIN_EMAIL="", INITIAL_ADMIN_PASSWORD="", EXISTING_USERS="true")) == []
