"""In-process simulation jobs.

This is not a distributed worker. A restart marks queued and running jobs as
failed. Cancellation is cooperative and is checked between iterations.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db.models import AuditEvent, Simulation
from app.engine.simulate import run_simulation
from app.engine.version import ALGORITHM_VERSION
from app.errors import Cancelled
from app.schemas.spec import ElectionSpecification
from app.services.clock import utcnow


class SimulationExecutor:
    def __init__(self, session_factory: sessionmaker[Session], settings: Settings) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="electionsim")
        self._cancel: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def submit(self, simulation_id: str) -> None:
        event = threading.Event()
        with self._lock:
            self._cancel[simulation_id] = event
        self._pool.submit(self.run, simulation_id, event)

    def request_cancel(self, simulation_id: str) -> bool:
        """Signal a job this process already accepted. Unknown ids are ignored."""

        with self._lock:
            event = self._cancel.get(simulation_id)
            if event is None:
                return False
            event.set()
            return True

    def run(self, simulation_id: str, event: threading.Event | None = None) -> None:
        if event is None:
            with self._lock:
                event = self._cancel.get(simulation_id) or threading.Event()
                self._cancel[simulation_id] = event
        session = self._session_factory()
        try:
            self._run_locked(session, simulation_id, event)
        finally:
            session.close()
            with self._lock:
                self._cancel.pop(simulation_id, None)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    def _run_locked(self, session: Session, simulation_id: str, event: threading.Event) -> None:
        claimed = (
            session.query(Simulation)
            .filter(Simulation.id == simulation_id, Simulation.status == "queued")
            .update({"status": "running", "started_at": utcnow(), "progress": 0})
        )
        session.commit()
        if claimed == 0:
            return
        record = session.get(Simulation, simulation_id)
        if record is None:
            return
        spec = ElectionSpecification.model_validate_json(record.spec_json)

        def progress(fraction: float) -> None:
            record.progress = max(0.0, min(1.0, fraction))
            session.commit()

        try:
            output = run_simulation(
                spec,
                self._settings,
                cancel_event=event,
                progress=progress,
            )
        except Cancelled:
            record.status = "cancelled"
            record.error_message = "Cancelled by user."
            record.finished_at = utcnow()
            session.add(
                AuditEvent(
                    simulation_id=simulation_id,
                    action="execute_cancelled",
                    detail="Cooperative cancellation.",
                    created_at=utcnow(),
                )
            )
            session.commit()
            return
        except Exception as exc:
            record.status = "failed"
            record.error_message = str(exc)[:2000]
            record.finished_at = utcnow()
            session.add(
                AuditEvent(
                    simulation_id=simulation_id,
                    action="execute_failed",
                    detail=record.error_message,
                    created_at=utcnow(),
                )
            )
            session.commit()
            return
        session.refresh(record)
        if event.is_set() or record.status == "cancelled":
            record.status = "cancelled"
            record.error_message = "Cancelled by user."
            record.finished_at = utcnow()
            session.commit()
            return
        record.results_json = output.model_dump_json()
        record.status = "completed"
        record.progress = 1
        record.finished_at = utcnow()
        record.algorithm_version = output.algorithm_version or ALGORITHM_VERSION
        record.error_message = None
        session.add(
            AuditEvent(
                simulation_id=simulation_id,
                action="execute_finished",
                detail=f"iterations={record.iterations} scenarios={len(output.scenarios)}",
                created_at=utcnow(),
            )
        )
        session.commit()
