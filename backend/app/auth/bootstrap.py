"""Create the first account from the environment when none exist."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password, validate_password
from app.config import Settings
from app.db.models import User
from app.services.clock import utcnow

logger = logging.getLogger("electionsim.auth")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def email_error(email: str) -> str | None:
    if len(email) < 3 or len(email) > 254 or "@" not in email or email.startswith("@") or email.endswith("@"):
        return "Enter a valid email address."
    local, _, domain = email.partition("@")
    if not local or "." not in domain or " " in email:
        return "Enter a valid email address."
    return None


def create_user(db: Session, email: str, password: str) -> User:
    user = User(
        id=str(uuid.uuid4()),
        email=email,
        password_hash=hash_password(password),
        created_at=utcnow(),
        disabled=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def ensure_initial_admin(db: Session, settings: Settings) -> None:
    """Create one operator account, or refuse a production boot that has no way to sign in."""

    if settings.normalized_auth_mode != "accounts":
        return
    existing = int(db.scalar(select(func.count()).select_from(User)) or 0)
    email = normalize_email(settings.initial_admin_email or "")
    password = settings.initial_admin_password or ""
    if existing == 0 and email and password:
        problem = email_error(email) or validate_password(password)
        if problem:
            raise RuntimeError(f"Initial administrator was not created: {problem}")
        create_user(db, email, password)
        logger.info("Created the initial account for %s. Remove INITIAL_ADMIN_PASSWORD from the environment.", email)
        return
    if settings.environment == "production" and existing == 0 and not settings.allow_registration:
        raise RuntimeError(
            "No accounts exist. Set INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD for the first user, "
            "or set ALLOW_REGISTRATION=true."
        )
