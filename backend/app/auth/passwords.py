"""Password hashing. Plaintext passwords are never stored."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()
_DUMMY_HASH = _hasher.hash("not-a-real-password")
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 200


def validate_password(password: str) -> str | None:
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Passwords must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Passwords must be at most {MAX_PASSWORD_LENGTH} characters."
    return None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def consume_dummy_password(password: str) -> None:
    """Spend roughly the same time as a real check when the account does not exist."""

    verify_password(_DUMMY_HASH, password)
