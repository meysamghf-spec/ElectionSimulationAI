"""Environment-backed settings. Secrets are read from the environment only."""

from functools import lru_cache
from urllib.parse import unquote, urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict

WEAK_SECRETS = {
    "change-me",
    "change-me-local-only",
    "password",
    "postgres",
    "election",
    "secret",
    "changeme",
    "api-token",
    "token",
    "admin",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
    )

    database_url: str = "sqlite:///./data/elections.db"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    api_token: str | None = None
    auth_mode: str = "development"
    allow_registration: bool = False
    initial_admin_email: str | None = None
    initial_admin_password: str | None = None
    session_hours: int = 12
    auth_rate_limit_per_minute: int = 10
    max_iterations: int = 50_000
    max_candidates: int = 25
    max_regions: int = 80
    max_scenarios: int = 12
    max_upload_bytes: int = 2_000_000
    max_prompt_chars: int = 20_000
    sensitivity_iteration_cap: int = 400
    rate_limit_per_minute: int = 60
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 30.0
    environment: str = "development"
    log_level: str = "INFO"

    @property
    def normalized_auth_mode(self) -> str:
        return self.auth_mode.strip().lower()

    @property
    def cookie_secure(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def persistence_label(self) -> str:
        if self.database_url.startswith("sqlite"):
            return "sqlite"
        if self.database_url.startswith("postgresql"):
            return "postgresql"
        return "other"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def database_password(url: str) -> str:
    return unquote(urlsplit(url).password or "")


def validate_production(settings: Settings) -> None:
    """Refuse to boot a production process that is still using development defaults."""

    if settings.environment != "production":
        return
    problems: list[str] = []
    mode = settings.normalized_auth_mode
    if mode not in {"accounts", "private"}:
        problems.append(
            "AUTH_MODE must be accounts or private. development serves an unauthenticated shared workspace."
        )
    if not settings.database_url.startswith("postgresql"):
        problems.append("DATABASE_URL must be a PostgreSQL URL. SQLite is only for local development.")
    password = database_password(settings.database_url)
    if len(password) < 16 or password.lower() in WEAK_SECRETS:
        problems.append(
            "The database password must be at least 16 characters and must not be a known placeholder."
        )
    origins = settings.cors_origin_list
    if not origins or any(origin == "*" or not origin.startswith("https://") for origin in origins):
        problems.append("CORS_ORIGINS must list https origins. Wildcard origins are not accepted.")
    if mode == "private":
        token = settings.api_token or ""
        if len(token) < 32 or token.lower() in WEAK_SECRETS:
            problems.append(
                "Private mode requires API_TOKEN of at least 32 characters that is not a known placeholder."
            )
    if problems:
        raise RuntimeError("Refusing to start in production:\n- " + "\n- ".join(problems))
