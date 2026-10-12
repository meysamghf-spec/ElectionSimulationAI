"""Run Alembic migrations against the configured database URL."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import Simulation
from app.db.session import build_session_factory


def backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def alembic_config(settings: Settings) -> Config:
    root = backend_root()
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def upgrade_database(settings: Settings) -> None:
    from app.db.session import prepare_database_url

    settings.database_url = prepare_database_url(settings.database_url)
    command.upgrade(alembic_config(settings), "head")


def downgrade_database(settings: Settings, revision: str = "base") -> None:
    command.downgrade(alembic_config(settings), revision)


def mark_interrupted(session: Session) -> int:
    """A process restart cannot resume an in-process job."""

    rows = (
        session.query(Simulation)
        .filter(Simulation.status.in_(("queued", "running")))
        .all()
    )
    for row in rows:
        row.status = "failed"
        row.error_message = "Interrupted by process restart. Submit the simulation again to recompute it."
        row.progress = 0
    if rows:
        session.commit()
    return len(rows)


def database_ready(settings: Settings) -> bool:
    engine, factory = build_session_factory(settings)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        inspector = inspect(engine)
        return inspector.has_table("simulations")
    finally:
        engine.dispose()
        del factory
