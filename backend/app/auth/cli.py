"""Create or reset an account without putting the password on the command line.

Usage, from the backend directory:

    CREATE_USER_EMAIL=person@example.com CREATE_USER_PASSWORD='a long passphrase' \\
        python -m app.auth.cli
"""

from __future__ import annotations

import os
import sys

from sqlalchemy import select

from app.auth.bootstrap import create_user, email_error, normalize_email
from app.auth.passwords import hash_password, validate_password
from app.config import get_settings
from app.db.migrate import upgrade_database
from app.db.models import User
from app.db.session import build_session_factory


def main() -> None:
    email = normalize_email(os.environ.get("CREATE_USER_EMAIL", ""))
    password = os.environ.get("CREATE_USER_PASSWORD", "")
    email_problem = email_error(email)
    password_problem = validate_password(password)
    if email_problem or password_problem:
        print(email_problem or password_problem, file=sys.stderr)
        raise SystemExit(1)
    settings = get_settings()
    upgrade_database(settings)
    _engine, factory = build_session_factory(settings)
    db = factory()
    try:
        existing = db.scalar(select(User).where(User.email == email))
        if existing is None:
            create_user(db, email, password)
            print(f"Created account {email}.")
            return
        existing.password_hash = hash_password(password)
        existing.disabled = False
        db.commit()
        print(f"Updated the password for {email}.")
    finally:
        db.close()
        _engine.dispose()


if __name__ == "__main__":
    main()
