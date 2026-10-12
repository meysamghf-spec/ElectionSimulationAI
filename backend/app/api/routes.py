"""Versioned HTTP API."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import Settings
from app.content.docs import read_document
from app.content.examples import EXAMPLE_PROMPTS, IMPORT_SCHEMAS, REGION_CSV
from app.db.models import Simulation
from app.engine.sensitivity import run_sensitivity
from app.engine.simulate import expectation_preview, spec_hash
from app.engine.validate import validate_spec
from app.engine.version import ALGORITHM_VERSION, DISCLAIMER
from app.errors import AppError, ConflictError, LimitError, PayloadTooLarge, SpecError
from app.interpreter.service import interpret
from app.io.csv_export import comparison_csv, results_csv
from app.io.csv_import import import_regions_csv
from app.io.pdf_export import render_pdf
from app.io.safety import safe_filename
from app.schemas.spec import ElectionSpecification
from app.security import error_body
from app.services.executor import SimulationExecutor
from app.services.simulations import (
    cancel_if_queued,
    compare_stored,
    create_simulation,
    delete_simulation,
    duplicate_simulation,
    get_simulation,
    list_projects,
    list_simulations,
    queue_simulation,
    recent_audit,
    record_dataset,
    stored_results,
    stored_spec,
    update_simulation,
    validation_report,
)

router = APIRouter(prefix="/api/v1")
WAIT_LIMIT = 5000


class PromptBody(BaseModel):
    prompt: str = Field(min_length=1)


class SimulationBody(BaseModel):
    specification: ElectionSpecification
    project_name: str | None = None


class ExecuteBody(BaseModel):
    wait: bool = False


class CompareBody(BaseModel):
    left_scenario_id: str
    right_scenario_id: str


class JsonImportBody(BaseModel):
    specification: ElectionSpecification
    filename: str = "specification.json"


def get_session(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_executor(request: Request) -> SimulationExecutor:
    return request.app.state.executor


def _limit(request: Request, bucket: str) -> None:
    limiter = request.app.state.rate_limiter
    host = request.client.host if request.client else "unknown"
    if not limiter.allow(f"{bucket}:{host}"):
        raise AppError(
            "Rate limit exceeded. Wait a minute and try again.",
            status_code=429,
            code="rate_limited",
        )


def _summary(record: Simulation) -> dict[str, object]:
    return {
        "id": record.id,
        "project_id": record.project_id,
        "title": record.title,
        "status": record.status,
        "seed": record.seed,
        "iterations": record.iterations,
        "algorithm_version": record.algorithm_version,
        "voting_method": record.voting_method,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
        "started_at": record.started_at.isoformat() if record.started_at else None,
        "finished_at": record.finished_at.isoformat() if record.finished_at else None,
        "progress": record.progress,
        "error_message": record.error_message,
        "hypothetical": True,
    }


def _detail(session: Session, record: Simulation) -> dict[str, object]:
    spec = stored_spec(record)
    results = None
    if record.status == "completed" and record.results_json:
        results = json.loads(record.results_json)
    validation = validation_report(record)
    return {
        **_summary(record),
        "description": record.description,
        "specification": spec.model_dump(mode="json"),
        "validation": validation.model_dump(mode="json") if validation else None,
        "results": results,
        "audit_events": [
            {
                "id": event.id,
                "action": event.action,
                "detail": event.detail,
                "created_at": event.created_at.isoformat(),
            }
            for event in recent_audit(session, record.id)
        ],
    }


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(request: Request) -> JSONResponse:
    from sqlalchemy import text

    try:
        engine = request.app.state.engine
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            error_body("not_ready", "Database is not ready."),
            status_code=503,
        )
    return JSONResponse({"status": "ok", "database": "ok"})


@router.get("/meta")
def meta(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    return {
        "algorithm_version": ALGORITHM_VERSION,
        "environment": settings.environment,
        "persistence": settings.persistence_label,
        "llm_configured": settings.llm_configured,
        "interpreter_default": "llm" if settings.llm_configured else "deterministic",
        "api_token_required": bool(settings.api_token),
        "max_iterations": settings.max_iterations,
        "max_candidates": settings.max_candidates,
        "max_regions": settings.max_regions,
        "max_upload_bytes": settings.max_upload_bytes,
        "sensitivity_iteration_cap": settings.sensitivity_iteration_cap,
        "authentication": (
            "Optional shared bearer token. There are no user accounts. "
            "When API_TOKEN is unset, anyone who can reach the API can read stored simulations."
        ),
        "disclaimer": DISCLAIMER,
        "worker": "in-process thread pool; not a distributed queue",
    }


@router.get("/content/{name}")
def content(name: str) -> dict[str, str]:
    return {"name": name, "markdown": read_document(name)}


@router.get("/examples")
def examples() -> dict[str, object]:
    return {"prompts": EXAMPLE_PROMPTS}


@router.get("/examples/datasets/regions.csv")
def example_regions_csv() -> Response:
    return Response(
        content=REGION_CSV,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=regions-example.csv"},
    )


@router.get("/imports/schemas")
def import_schemas() -> dict[str, object]:
    return IMPORT_SCHEMAS


@router.post("/interpret")
def interpret_prompt(
    body: PromptBody,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    _limit(request, "interpret")
    result = interpret(body.prompt, settings)
    return result.model_dump(mode="json")


@router.post("/simulations/validate")
def validate(body: SimulationBody, settings: Settings = Depends(get_settings)) -> dict[str, object]:
    report = validate_spec(body.specification, settings)
    return report.model_dump(mode="json")


@router.post("/simulations/preview")
def preview(body: SimulationBody, settings: Settings = Depends(get_settings)) -> dict[str, object]:
    report = validate_spec(body.specification, settings)
    expectations = None
    if report.valid:
        expectations = expectation_preview(body.specification)
    return {
        "hypothetical": True,
        "disclaimer": DISCLAIMER,
        "validation": report.model_dump(mode="json"),
        "spec_hash": spec_hash(body.specification),
        "expectations": expectations,
        "note": (
            "Preview reports analytical expectations when they exist. "
            "It does not run the Monte Carlo simulation and it does not create official results."
        ),
    }


@router.post("/simulations", status_code=201)
def create(
    body: SimulationBody,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    record = create_simulation(session, body.specification, settings, project_name=body.project_name)
    return _detail(session, record)


@router.get("/simulations")
def simulations(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    project_id: str | None = None,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    rows, total = list_simulations(session, limit=limit, offset=offset, project_id=project_id)
    return {"items": [_summary(row) for row in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/projects")
def projects(session: Session = Depends(get_session)) -> dict[str, object]:
    return {
        "items": [
            {"id": project.id, "name": project.name, "created_at": project.created_at.isoformat()}
            for project in list_projects(session)
        ]
    }


@router.get("/simulations/{simulation_id}")
def simulation_detail(simulation_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
    return _detail(session, get_simulation(session, simulation_id))


@router.patch("/simulations/{simulation_id}")
def simulation_update(
    simulation_id: str,
    body: SimulationBody,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    record = update_simulation(
        session,
        simulation_id,
        body.specification,
        settings,
        project_name=body.project_name,
    )
    return _detail(session, record)


@router.delete("/simulations/{simulation_id}", status_code=204)
def simulation_delete(simulation_id: str, session: Session = Depends(get_session)) -> Response:
    delete_simulation(session, simulation_id)
    return Response(status_code=204)


@router.post("/simulations/{simulation_id}/duplicate", status_code=201)
def simulation_duplicate(simulation_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
    return _detail(session, duplicate_simulation(session, simulation_id))


@router.post("/simulations/{simulation_id}/execute", status_code=202)
def simulation_execute(
    simulation_id: str,
    body: ExecuteBody,
    request: Request,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    executor: SimulationExecutor = Depends(get_executor),
) -> JSONResponse:
    _limit(request, "execute")
    current = get_simulation(session, simulation_id)
    if body.wait and current.iterations > WAIT_LIMIT:
        raise LimitError(
            f"wait=true is limited to {WAIT_LIMIT} iterations. Start the run without waiting and poll status."
        )
    record = queue_simulation(session, simulation_id, settings)
    if body.wait:
        executor.run(record.id)
        session.refresh(record)
        return JSONResponse(_summary(record), status_code=200)
    executor.submit(record.id)
    return JSONResponse(_summary(record), status_code=202)


@router.post("/simulations/{simulation_id}/cancel")
def simulation_cancel(
    simulation_id: str,
    session: Session = Depends(get_session),
    executor: SimulationExecutor = Depends(get_executor),
) -> dict[str, object]:
    executor.request_cancel(simulation_id)
    record = cancel_if_queued(session, simulation_id)
    message = (
        "Cancellation requested. The worker stops between iterations."
        if record.status == "running"
        else "The simulation was cancelled."
    )
    return {"message": message, "simulation": _summary(record)}


@router.get("/simulations/{simulation_id}/status")
def simulation_status(simulation_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
    return _summary(get_simulation(session, simulation_id))


@router.get("/simulations/{simulation_id}/results")
def simulation_results(simulation_id: str, session: Session = Depends(get_session)) -> dict[str, object]:
    record = get_simulation(session, simulation_id)
    return stored_results(record).model_dump(mode="json")


@router.post("/simulations/{simulation_id}/compare")
def simulation_compare(
    simulation_id: str,
    body: CompareBody,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    comparison = compare_stored(session, simulation_id, body.left_scenario_id, body.right_scenario_id)
    return comparison.model_dump(mode="json")


@router.post("/simulations/{simulation_id}/sensitivity")
def simulation_sensitivity(
    simulation_id: str,
    request: Request,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    _limit(request, "sensitivity")
    record = get_simulation(session, simulation_id)
    if record.status in {"queued", "running"}:
        raise ConflictError("Wait until the current run finishes before starting a sensitivity sweep.")
    report = run_sensitivity(stored_spec(record), settings)
    return report.model_dump(mode="json")


@router.get("/simulations/{simulation_id}/export.csv")
def export_csv(
    simulation_id: str,
    view: Literal["candidates", "regional"] = "candidates",
    session: Session = Depends(get_session),
) -> Response:
    record = get_simulation(session, simulation_id)
    content = results_csv(stored_results(record), view=view)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=simulation-{record.id}-{view}.csv"},
    )


@router.get("/simulations/{simulation_id}/export.json")
def export_json(simulation_id: str, session: Session = Depends(get_session)) -> Response:
    record = get_simulation(session, simulation_id)
    payload = {
        "hypothetical": True,
        "disclaimer": DISCLAIMER,
        "specification": stored_spec(record).model_dump(mode="json"),
        "results": stored_results(record).model_dump(mode="json"),
    }
    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=simulation-{record.id}.json"},
    )


@router.get("/simulations/{simulation_id}/export.pdf")
def export_pdf(simulation_id: str, session: Session = Depends(get_session)) -> Response:
    record = get_simulation(session, simulation_id)
    content = render_pdf(
        stored_spec(record),
        stored_results(record),
        created_at=record.created_at.isoformat(),
        finished_at=record.finished_at.isoformat() if record.finished_at else None,
    )
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=simulation-{record.id}.pdf"},
    )


@router.get("/simulations/{simulation_id}/compare.csv")
def export_comparison_csv(
    simulation_id: str,
    left: str,
    right: str,
    session: Session = Depends(get_session),
) -> Response:
    comparison = compare_stored(session, simulation_id, left, right)
    return Response(
        content=comparison_csv(comparison),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=comparison.csv"},
    )


@router.post("/imports/csv")
async def import_csv(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    voting_method: str = Form(...),
    iterations: int = Form(...),
    seed: int = Form(...),
    seats: int | None = Form(default=None),
    description: str = Form(default=""),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    _limit(request, "import")
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise PayloadTooLarge(f"Uploads are limited to {settings.max_upload_bytes} bytes.")
    filename = safe_filename(file.filename)
    specification, warnings = import_regions_csv(
        content,
        filename=filename,
        title=title,
        voting_method=voting_method,
        iterations=iterations,
        seed=seed,
        seats=seats,
        description=description,
    )
    report = validate_spec(specification, settings)
    if not report.valid:
        raise SpecError(
            "The imported specification is invalid.",
            details=[{"field": issue.field, "message": issue.message} for issue in report.errors],
        )
    dataset = record_dataset(
        session,
        filename=filename,
        content_type=file.content_type or "text/csv",
        sha256=hashlib.sha256(content).hexdigest(),
        byte_size=len(content),
        row_count=len(specification.regions),
        schema_name="regions_csv",
        summary_json=json.dumps({"warnings": warnings, "candidate_ids": [c.id for c in specification.candidates]}),
    )
    return {
        "dataset_id": dataset.id,
        "warnings": warnings,
        "validation": report.model_dump(mode="json"),
        "specification": specification.model_dump(mode="json"),
        "hypothetical": True,
    }


@router.post("/imports/json")
def import_json(
    body: JsonImportBody,
    request: Request,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    _limit(request, "import")
    report = validate_spec(body.specification, settings)
    if not report.valid:
        raise SpecError(
            "The imported specification is invalid.",
            details=[{"field": issue.field, "message": issue.message} for issue in report.errors],
        )
    raw = body.specification.model_dump_json().encode()
    dataset = record_dataset(
        session,
        filename=safe_filename(body.filename),
        content_type="application/json",
        sha256=hashlib.sha256(raw).hexdigest(),
        byte_size=len(raw),
        row_count=len(body.specification.regions),
        schema_name="specification_json",
        summary_json=json.dumps({"title": body.specification.title}),
    )
    return {
        "dataset_id": dataset.id,
        "warnings": [],
        "validation": report.model_dump(mode="json"),
        "specification": body.specification.model_dump(mode="json"),
        "hypothetical": True,
    }
