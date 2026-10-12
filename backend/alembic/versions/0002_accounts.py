"""Accounts, sessions, and resource owners."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_accounts"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disabled", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    _add_owner("projects")
    _add_owner("simulations")
    _add_owner("datasets")


def _add_owner(table: str) -> None:
    with op.batch_alter_table(table) as batch:
        batch.add_column(sa.Column("owner_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(f"fk_{table}_owner_id", "users", ["owner_id"], ["id"], ondelete="CASCADE")
        batch.create_index(f"ix_{table}_owner_id", ["owner_id"])


def downgrade() -> None:
    for table in ("datasets", "simulations", "projects"):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_owner_id")
            batch.drop_constraint(f"fk_{table}_owner_id", type_="foreignkey")
            batch.drop_column("owner_id")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
