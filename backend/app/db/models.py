"""Durable records. The specification JSON is the reproducible source of truth."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Simulation(Base):
    __tablename__ = "simulations"
    __table_args__ = (
        CheckConstraint(
            "status in ('draft','queued','running','completed','failed','cancelled')",
            name="ck_simulations_status",
        ),
        Index("ix_simulations_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    spec_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    seed: Mapped[int] = mapped_column(BigInteger, nullable=False)
    iterations: Mapped[int] = mapped_column(Integer, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(32), nullable=False)
    voting_method: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    results_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    hypothetical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CandidateRecord(Base):
    __tablename__ = "candidates"
    __table_args__ = (UniqueConstraint("simulation_id", "candidate_key", name="uq_candidate_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_id: Mapped[str] = mapped_column(
        ForeignKey("simulations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class RegionRecord(Base):
    __tablename__ = "regions"
    __table_args__ = (
        UniqueConstraint("simulation_id", "region_key", name="uq_region_key"),
        CheckConstraint("eligible_voters >= 0", name="ck_regions_eligible"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_id: Mapped[str] = mapped_column(
        ForeignKey("simulations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    region_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    eligible_voters: Mapped[int] = mapped_column(Integer, nullable=False)
    turnout_probability: Mapped[float] = mapped_column(Float, nullable=False)


class ComparisonRecord(Base):
    __tablename__ = "comparisons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    simulation_id: Mapped[str] = mapped_column(
        ForeignKey("simulations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    left_scenario_id: Mapped[str] = mapped_column(String(64), nullable=False)
    right_scenario_id: Mapped[str] = mapped_column(String(64), nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DatasetRecord(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_name: Mapped[str] = mapped_column(String(64), nullable=False)
    summary_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_id: Mapped[str | None] = mapped_column(
        ForeignKey("simulations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
