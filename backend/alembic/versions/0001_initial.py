"""Initial schema."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "simulations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("spec_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column("iterations", sa.Integer(), nullable=False),
        sa.Column("algorithm_version", sa.String(length=32), nullable=False),
        sa.Column("voting_method", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("results_json", sa.Text(), nullable=True),
        sa.Column("validation_json", sa.Text(), nullable=True),
        sa.Column("hypothetical", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "status in ('draft','queued','running','completed','failed','cancelled')",
            name="ck_simulations_status",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_simulations_status", "simulations", ["status"])
    op.create_index("ix_simulations_project_id", "simulations", ["project_id"])
    op.create_index("ix_simulations_created_at", "simulations", ["created_at"])
    op.create_table(
        "candidates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("simulation_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("simulation_id", "candidate_key", name="uq_candidate_key"),
    )
    op.create_index("ix_candidates_simulation_id", "candidates", ["simulation_id"])
    op.create_table(
        "regions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("simulation_id", sa.String(length=36), nullable=False),
        sa.Column("region_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("eligible_voters", sa.Integer(), nullable=False),
        sa.Column("turnout_probability", sa.Float(), nullable=False),
        sa.CheckConstraint("eligible_voters >= 0", name="ck_regions_eligible"),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("simulation_id", "region_key", name="uq_region_key"),
    )
    op.create_index("ix_regions_simulation_id", "regions", ["simulation_id"])
    op.create_table(
        "comparisons",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("simulation_id", sa.String(length=36), nullable=False),
        sa.Column("left_scenario_id", sa.String(length=64), nullable=False),
        sa.Column("right_scenario_id", sa.String(length=64), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_comparisons_simulation_id", "comparisons", ["simulation_id"])
    op.create_table(
        "datasets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("filename", sa.String(length=200), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("schema_name", sa.String(length=64), nullable=False),
        sa.Column("summary_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("simulation_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_audit_events_simulation_id", "audit_events", ["simulation_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_simulation_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("datasets")
    op.drop_index("ix_comparisons_simulation_id", table_name="comparisons")
    op.drop_table("comparisons")
    op.drop_index("ix_regions_simulation_id", table_name="regions")
    op.drop_table("regions")
    op.drop_index("ix_candidates_simulation_id", table_name="candidates")
    op.drop_table("candidates")
    op.drop_index("ix_simulations_created_at", table_name="simulations")
    op.drop_index("ix_simulations_project_id", table_name="simulations")
    op.drop_index("ix_simulations_status", table_name="simulations")
    op.drop_table("simulations")
    op.drop_table("projects")
