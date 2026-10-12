"""Opaque server-side sessions. The browser receives an HttpOnly cookie."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.config import Settings
from app.db.models import AuthSession, User
from app.services.clock import utcnow

SESSION_COOKIE = "esim_session"
CSRF_COOKIE = "esim_csrf"
CSRF_HEADER = "x-csrf-token"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def create_session(db: Session, user: User, settings: Settings) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    now = utcnow()
    db.add(
        AuthSession(
            id=str(uuid.uuid4()),
            user_id=user.id,
            token_hash=_hash_token(token),
            csrf_token=csrf,
            created_at=now,
            expires_at=now + timedelta(hours=settings.session_hours),
            revoked=False,
        )
    )
    db.commit()
    return token, csrf


def revoke_session(db: Session, token: str) -> None:
    row = db.scalar(select(AuthSession).where(AuthSession.token_hash == _hash_token(token)))
    if row is None:
        return
    row.revoked = True
    db.commit()


def apply_session_cookies(response: Response, token: str, csrf: str, settings: Settings) -> None:
    max_age = settings.session_hours * 3600
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=CSRF_COOKIE,
        value=csrf,
        max_age=max_age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=settings.cookie_secure, httponly=True, samesite="lax")
    response.delete_cookie(CSRF_COOKIE, path="/", secure=settings.cookie_secure, httponly=False, samesite="lax")


def authenticated_user(db: Session, token: str) -> tuple[User, AuthSession] | None:
    if not token:
        return None
    row = db.scalar(select(AuthSession).where(AuthSession.token_hash == _hash_token(token)))
    if row is None or row.revoked or _as_utc(row.expires_at) <= utcnow():
        return None
    user = db.get(User, row.user_id)
    if user is None or user.disabled:
        return None
    return user, row
