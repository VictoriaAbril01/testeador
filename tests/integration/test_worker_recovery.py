"""Recovery never re-enqueues; it reconciles stale database states conservatively."""

from datetime import datetime, timedelta, timezone

from rq.exceptions import NoSuchJobError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database.config import get_database_url
from app.models import Project, TestRun as RunModel
from app.services import recovery
from workers import jobs as worker_jobs


def test_recovery_handles_lost_queued_and_interrupted_jobs(monkeypatch):
    engine = create_engine(get_database_url())
    connection = engine.connect()
    transaction = connection.begin()
    now = datetime.now(timezone.utc)
    old = now - timedelta(minutes=5)
    try:
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            project = Project(name="Recovery fixture", base_url="https://example.test/", environment="staging", modality="blackbox")
            session.add(project)
            session.flush()

            def add(status: str, dispatch: bool, heartbeat=None) -> RunModel:
                item = RunModel(project_id=project.id, status=status, dispatch_requested=dispatch,
                               max_pages=1, max_depth=0, max_requests=10, max_concurrency=1,
                               page_timeout_ms=1000, execution_timeout_ms=10000,
                               requested_at=old, started_at=old if status in {"running", "cancelling"} else None,
                               heartbeat_at=heartbeat)
                session.add(item)
                session.flush()
                return item

            manual = add("pending", False)
            missing = add("pending", True)
            queued = add("queued", True)
            interrupted = add("running", True, old)
            active = add("running", True, now)
            deliverable = add("pending", True)
            session.commit()

            class FakeJob:
                def __init__(self, status, heartbeat):
                    self.status = status
                    self.last_heartbeat = heartbeat

                def get_status(self):
                    return self.status

            jobs = {str(queued.id): FakeJob("queued", None),
                    str(interrupted.id): FakeJob("started", old),
                    str(active.id): FakeJob("started", now),
                    str(deliverable.id): FakeJob("queued", None)}
            monkeypatch.setattr(recovery, "Queue", lambda *_args, **_kwargs: type("QueueView", (), {
                "get_job_ids": lambda self: [str(queued.id), str(deliverable.id)]})())

            def fetch(job_id, connection):
                if job_id not in jobs:
                    raise NoSuchJobError(job_id)
                return jobs[job_id]

            monkeypatch.setattr(recovery.Job, "fetch", staticmethod(fetch))
            changed = recovery.reconcile_once(session, object(), now)
            assert set(changed) == {str(missing.id), str(interrupted.id), str(deliverable.id)}
            assert session.get(RunModel, manual.id).status == "pending"
            assert session.get(RunModel, queued.id).status == "queued"
            assert session.get(RunModel, missing.id).status == "failed"
            assert session.get(RunModel, interrupted.id).status == "failed"
            assert session.get(RunModel, active.id).status == "running"
            assert session.get(RunModel, deliverable.id).status == "queued"
            assert recovery.reconcile_once(session, object(), now) == []
    finally:
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_worker_heartbeat_observes_cancellation_request(monkeypatch):
    engine = create_engine(get_database_url())
    connection = engine.connect()
    transaction = connection.begin()
    try:
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            project = Project(name="Heartbeat fixture", base_url="https://example.test/",
                              environment="staging", modality="blackbox")
            session.add(project)
            session.flush()
            run = RunModel(project_id=project.id, status="running", max_pages=1, max_depth=0,
                           max_requests=10, max_concurrency=1, page_timeout_ms=1000, execution_timeout_ms=10000)
            session.add(run)
            session.commit()
            run_id = run.id
        monkeypatch.setattr(worker_jobs, "Session", lambda _engine: Session(bind=connection, join_transaction_mode="create_savepoint"))
        monkeypatch.setattr(worker_jobs, "get_engine", lambda: engine)
        assert worker_jobs._heartbeat_and_check(run_id) is False
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            stored = session.get(RunModel, run_id)
            assert stored.heartbeat_at is not None
            stored.cancellation_requested = True
            stored.status = "cancelling"
            session.commit()
        assert worker_jobs._heartbeat_and_check(run_id) is True
    finally:
        transaction.rollback()
        connection.close()
        engine.dispose()
