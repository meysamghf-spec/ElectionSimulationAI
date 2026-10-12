"""Check a production environment without printing secret values."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping

from app.auth.passwords import validate_password
from app.config import Settings, database_password, validate_production

_SECRET_NAMES = (
    "DATABASE_URL",
    "POSTGRES_PASSWORD",
    "API_TOKEN",
    "INITIAL_ADMIN_PASSWORD",
    "LLM_API_KEY",
    "CREATE_USER_PASSWORD",
)
_PUBLIC_NAMES = {"NEXT_PUBLIC_API_TOKEN", "NEXT_PUBLIC_API_INTERNAL_URL"}


def _enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _redact(text: str, env: Mapping[str, str]) -> str:
    redacted = text
    secrets = [env.get(name) or "" for name in _SECRET_NAMES]
    secrets.append(database_password(env.get("DATABASE_URL", "")))
    for secret in secrets:
        if len(secret) >= 8:
            redacted = redacted.replace(secret, "[redacted]")
    return redacted


def production_problems(env: Mapping[str, str]) -> list[str]:
    """Return configuration problems. Messages name variables, not secret values."""

    problems: list[str] = []
    required = (
        "ENVIRONMENT",
        "AUTH_MODE",
        "DATABASE_URL",
        "CORS_ORIGINS",
        "POSTGRES_PASSWORD",
        "SITE_ADDRESS",
        "ACME_EMAIL",
        "TRUSTED_PROXY_CIDRS",
        "API_INTERNAL_URL",
    )
    for name in required:
        if not (env.get(name) or "").strip():
            problems.append(f"{name} is required.")

    if (env.get("ENVIRONMENT") or "").strip() != "production":
        problems.append("ENVIRONMENT must be production.")

    if _enabled(env.get("ALLOW_REGISTRATION")):
        problems.append("ALLOW_REGISTRATION must be false.")

    for name in sorted(_PUBLIC_NAMES):
        if (env.get(name) or "").strip():
            problems.append(f"{name} must be unset. The browser must not receive internal credentials.")

    site = (env.get("SITE_ADDRESS") or "").strip()
    if site and ("://" in site or "/" in site or " " in site or "@" in site):
        problems.append("SITE_ADDRESS must be a bare hostname, not a URL.")

    cors = (env.get("CORS_ORIGINS") or "").strip()
    if site and "://" not in site and "/" not in site and cors != f"https://{site}":
        problems.append("CORS_ORIGINS must be exactly https://SITE_ADDRESS.")

    email = (env.get("ACME_EMAIL") or "").strip()
    if email and ("@" not in email or email.startswith("@") or email.endswith("@") or " " in email):
        problems.append("ACME_EMAIL must look like an email address.")

    internal = (env.get("API_INTERNAL_URL") or "").strip().rstrip("/")
    if internal and internal != "http://api:8000":
        problems.append("API_INTERNAL_URL must be the Docker network address http://api:8000.")

    mode = (env.get("AUTH_MODE") or "").strip().lower()
    admin_email = (env.get("INITIAL_ADMIN_EMAIL") or "").strip()
    admin_password = env.get("INITIAL_ADMIN_PASSWORD") or ""
    if mode == "accounts":
        if bool(admin_email) != bool(admin_password):
            problems.append("INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD must be set together.")
        elif not admin_email and not _enabled(env.get("EXISTING_USERS")):
            problems.append(
                "INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD are required for the first boot. "
                "After the account exists, set EXISTING_USERS=true and remove the password."
            )
        elif admin_password:
            password_problem = validate_password(admin_password)
            if password_problem:
                problems.append(f"INITIAL_ADMIN_PASSWORD is not acceptable. {password_problem}")

    url_password = database_password(env.get("DATABASE_URL", ""))
    postgres_password = env.get("POSTGRES_PASSWORD") or ""
    if url_password and postgres_password and url_password != postgres_password:
        problems.append("POSTGRES_PASSWORD must be the same password encoded in DATABASE_URL.")
    if postgres_password and any(character in postgres_password for character in "@:/?#"):
        problems.append(
            "POSTGRES_PASSWORD contains characters that change a URL. Use a password without @ : / ? #."
        )

    try:
        validate_production(
            Settings(
                environment="production",
                auth_mode=env.get("AUTH_MODE") or "development",
                database_url=env.get("DATABASE_URL") or "sqlite:///./data/elections.db",
                cors_origins=env.get("CORS_ORIGINS") or "",
                api_token=env.get("API_TOKEN") or None,
                allow_registration=_enabled(env.get("ALLOW_REGISTRATION")),
                trusted_proxy_cidrs=env.get("TRUSTED_PROXY_CIDRS") or "",
                initial_admin_email=admin_email or None,
                initial_admin_password=admin_password or None,
            )
        )
    except RuntimeError as exc:
        problems.append(_redact(str(exc), env))

    return [_redact(problem, env) for problem in problems]


def main() -> int:
    problems = production_problems(os.environ)
    if problems:
        print("Production configuration is not acceptable:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        return 1
    print("Production configuration checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
