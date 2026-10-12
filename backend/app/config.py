"""Environment-backed settings. Secrets are read from the environment only."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
    )

    database_url: str = "sqlite:///./data/elections.db"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    api_token: str | None = None
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
