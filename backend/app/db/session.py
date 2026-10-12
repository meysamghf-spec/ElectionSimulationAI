"""Engine and session factory."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import Settings


def sqlite_file(url: str) -> Path | None:
    if not url.startswith("sqlite:///"):
        return None
    raw = url.removeprefix("sqlite:///")
    if raw in {":memory:", ""}:
        return None
    return Path(raw)


def prepare_database_url(url: str) -> str:
    path = sqlite_file(url)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
    return url


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=NullPool,
        )

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection: object, connection_record: object) -> None:
            del connection_record
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        return engine
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
    finally:
        session.close()


def build_session_factory(settings: Settings) -> tuple[Engine, sessionmaker[Session]]:
    url = prepare_database_url(settings.database_url)
    engine = make_engine(url)
    return engine, make_session_factory(engine)
