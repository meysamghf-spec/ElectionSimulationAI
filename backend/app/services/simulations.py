"""Persistence for projects and simulations."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import (
    AuditEvent,
    CandidateRecord,
    ComparisonRecord,
    DatasetRecord,
    Project,
    RegionRecord,
    Simulation,
)
from app.engine.compare import compare_scenarios
from app.engine.validate import ensure_valid
from app.engine.version import ALGORITHM_VERSION
from app.errors import ConflictError, NotFoundError
from app.schemas.results import ComparisonResult, SimulationOutput
from app.schemas.spec import ElectionSpecification, ValidationReport
from app.services.clock import utcnow


def create_simulation(
    session: Session,
    spec: ElectionSpecification,
    settings: Settings,
    *,
    project_name: str | None = None,
) -> Simulation:
    report = ensure_valid(spec, settings)
    project_id = _project_id(session, project_name)
    now = utcnow()
    record = Simulation(
        id=str(uuid.uuid4()),
        project_id=project_id,
        title=spec.title,
        description=spec.description,
        spec_json=spec.model_dump_json(),
        status="draft",
        seed=spec.seed,
        iterations=spec.iterations,
        algorithm_version=ALGORITHM_VERSION,
        voting_method=spec.voting_method,
        created_at=now,
        updated_at=now,
        progress=0,
        validation_json=report.model_dump_json(),
        hypothetical=True,
    )
    session.add(record)
    session.flush()
    _replace_children(session, record.id, spec)
    _audit(session, record.id, "created", f"method={spec.voting_method} iterations={spec.iterations}")
    session.commit()
    session.refresh(record)
    return record


def update_simulation(
    session: Session,
    simulation_id: str,
    spec: ElectionSpecification,
    settings: Settings,
    *,
    project_name: str | None = None,
) -> Simulation:
    record = get_simulation(session, simulation_id)
    if record.status in {"queued", "running"}:
        raise ConflictError("A queued or running simulation cannot be edited.")
    report = ensure_valid(spec, settings)
    record.project_id = _project_id(session, project_name) if project_name is not None else record.project_id
    record.title = spec.title
    record.description = spec.description
    record.spec_json = spec.model_dump_json()
    record.seed = spec.seed
    record.iterations = spec.iterations
    record.voting_method = spec.voting_method
    record.status = "draft"
    record.results_json = None
    record.error_message = None
    record.progress = 0
    record.started_at = None
    record.finished_at = None
    record.validation_json = report.model_dump_json()
    record.updated_at = utcnow()
    record.hypothetical = True
    _replace_children(session, record.id, spec)
    _audit(session, record.id, "updated", "Configuration replaced. Previous results were cleared.")
    session.commit()
    session.refresh(record)
    return record


def delete_simulation(session: Session, simulation_id: str) -> None:
    record = get_simulation(session, simulation_id)
    if record.status in {"queued", "running"}:
        raise ConflictError("Cancel the simulation before deleting it.")
    session.delete(record)
    session.commit()


def duplicate_simulation(session: Session, simulation_id: str) -> Simulation:
    source = get_simulation(session, simulation_id)
    spec = ElectionSpecification.model_validate_json(source.spec_json)
    now = utcnow()
    record = Simulation(
        id=str(uuid.uuid4()),
        project_id=source.project_id,
        title=spec.title,
        description=spec.description,
        spec_json=source.spec_json,
        status="draft",
        seed=spec.seed,
        iterations=spec.iterations,
        algorithm_version=ALGORITHM_VERSION,
        voting_method=spec.voting_method,
        created_at=now,
        updated_at=now,
        progress=0,
        validation_json=source.validation_json,
        hypothetical=True,
    )
    session.add(record)
    session.flush()
    _replace_children(session, record.id, spec)
    _audit(session, record.id, "duplicated", f"Copied from {source.id}.")
    session.commit()
    session.refresh(record)
    return record


def get_simulation(session: Session, simulation_id: str) -> Simulation:
    record = session.get(Simulation, simulation_id)
    if record is None:
        raise NotFoundError("Simulation not found.")
    return record


def list_simulations(
    session: Session,
    *,
    limit: int,
    offset: int,
    project_id: str | None,
) -> tuple[list[Simulation], int]:
    query = select(Simulation)
    count_query = select(func.count()).select_from(Simulation)
    if project_id:
        query = query.where(Simulation.project_id == project_id)
        count_query = count_query.where(Simulation.project_id == project_id)
    total = int(session.scalar(count_query) or 0)
    rows = (
        session.scalars(query.order_by(Simulation.created_at.desc()).limit(limit).offset(offset)).all()
    )
    return list(rows), total


def queue_simulation(session: Session, simulation_id: str, settings: Settings) -> Simulation:
    record = get_simulation(session, simulation_id)
    if record.status in {"queued", "running"}:
        raise ConflictError("This simulation is already queued or running.")
    spec = ElectionSpecification.model_validate_json(record.spec_json)
    report = ensure_valid(spec, settings)
    record.validation_json = report.model_dump_json()
    record.status = "queued"
    record.progress = 0
    record.error_message = None
    record.results_json = None
    record.started_at = None
    record.finished_at = None
    record.updated_at = utcnow()
    _audit(session, record.id, "execute_queued", f"iterations={record.iterations}")
    session.commit()
    session.refresh(record)
    return record


def cancel_if_queued(session: Session, simulation_id: str) -> Simulation:
    record = get_simulation(session, simulation_id)
    if record.status == "queued":
        record.status = "cancelled"
        record.error_message = "Cancelled before execution started."
        record.finished_at = utcnow()
        record.updated_at = utcnow()
        _audit(session, record.id, "execute_cancelled", "Cancelled while queued.")
        session.commit()
        session.refresh(record)
    elif record.status != "running":
        raise ConflictError("Only a queued or running simulation can be cancelled.")
    return record


def stored_results(record: Simulation) -> SimulationOutput:
    if record.status != "completed" or not record.results_json:
        raise ConflictError("Results are available only after a completed run.")
    return SimulationOutput.model_validate_json(record.results_json)


def stored_spec(record: Simulation) -> ElectionSpecification:
    return ElectionSpecification.model_validate_json(record.spec_json)


def compare_stored(session: Session, simulation_id: str, left_id: str, right_id: str) -> ComparisonResult:
    record = get_simulation(session, simulation_id)
    output = stored_results(record)
    lookup = {scenario.scenario_id: scenario for scenario in output.scenarios}
    if left_id not in lookup or right_id not in lookup:
        raise NotFoundError("One or both scenario ids are not in this simulation.")
    comparison = compare_scenarios(lookup[left_id], lookup[right_id])
    session.add(
        ComparisonRecord(
            id=str(uuid.uuid4()),
            simulation_id=simulation_id,
            left_scenario_id=left_id,
            right_scenario_id=right_id,
            result_json=comparison.model_dump_json(),
            created_at=utcnow(),
        )
    )
    _audit(session, simulation_id, "compared", f"{left_id} -> {right_id}")
    session.commit()
    return comparison


def recent_audit(session: Session, simulation_id: str, limit: int = 30) -> list[AuditEvent]:
    return list(
        session.scalars(
            select(AuditEvent)
            .where(AuditEvent.simulation_id == simulation_id)
            .order_by(AuditEvent.id.desc())
            .limit(limit)
        ).all()
    )


def list_projects(session: Session) -> list[Project]:
    return list(session.scalars(select(Project).order_by(Project.created_at.desc())).all())


def validation_report(record: Simulation) -> ValidationReport | None:
    if not record.validation_json:
        return None
    return ValidationReport.model_validate_json(record.validation_json)


def record_dataset(
    session: Session,
    *,
    filename: str,
    content_type: str,
    sha256: str,
    byte_size: int,
    row_count: int,
    schema_name: str,
    summary_json: str,
) -> DatasetRecord:
    record = DatasetRecord(
        id=str(uuid.uuid4()),
        filename=filename,
        content_type=content_type,
        sha256=sha256,
        byte_size=byte_size,
        row_count=row_count,
        schema_name=schema_name,
        summary_json=summary_json,
        created_at=utcnow(),
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def _project_id(session: Session, name: str | None) -> str | None:
    if name is None or not name.strip():
        return None
    cleaned = name.strip()[:200]
    existing = session.scalar(select(Project).where(Project.name == cleaned))
    if existing is not None:
        return existing.id
    project = Project(id=str(uuid.uuid4()), name=cleaned, description="", created_at=utcnow())
    session.add(project)
    session.flush()
    return project.id


def _replace_children(session: Session, simulation_id: str, spec: ElectionSpecification) -> None:
    session.query(CandidateRecord).filter(CandidateRecord.simulation_id == simulation_id).delete()
    session.query(RegionRecord).filter(RegionRecord.simulation_id == simulation_id).delete()
    for position, candidate in enumerate(spec.candidates):
        session.add(
            CandidateRecord(
                simulation_id=simulation_id,
                candidate_key=candidate.id,
                name=candidate.name,
                position=position,
            )
        )
    for region in spec.regions:
        session.add(
            RegionRecord(
                simulation_id=simulation_id,
                region_key=region.id,
                name=region.name,
                eligible_voters=region.eligible_voters,
                turnout_probability=region.turnout_probability,
            )
        )


def _audit(session: Session, simulation_id: str | None, action: str, detail: str) -> None:
    session.add(
        AuditEvent(
            simulation_id=simulation_id,
            action=action,
            detail=detail[:2000],
            created_at=utcnow(),
        )
    )
