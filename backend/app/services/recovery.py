"""Conservative Redis/PostgreSQL reconciliation; never rerun a browser job."""

from datetime import datetime, timedelta, timezone

from redis import Redis
from rq import Queue
from rq.exceptions import NoSuchJobError
from rq.job import Job
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TestRun
from app.services.runs import transition_run


GRACE = timedelta(seconds=45)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def reconcile_once(session: Session, redis: Redis, now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    queued_ids = set(Queue("testlab", connection=redis).get_job_ids())
    changed: list[str] = []
    runs = list(session.scalars(select(TestRun).where(TestRun.status.in_(
        ["pending", "queued", "running", "cancelling"])).with_for_update(skip_locked=True)))
    for run in runs:
        try:
            job = Job.fetch(str(run.id), connection=redis)
            status = job.get_status()
            job_status = getattr(status, "value", status)
            job_heartbeat = _aware(job.last_heartbeat)
        except NoSuchJobError:
            job_status = "missing"
            job_heartbeat = None
        age = now - _aware(run.started_at or run.requested_at)
        if run.status == "pending" and not run.dispatch_requested:
            continue
        if run.status == "pending" and str(run.id) in queued_ids:
            transition_run(run, "queued")
        elif run.status in {"pending", "queued"} and age >= GRACE and (
            job_status in {"missing", "failed", "canceled", "cancelled", "finished", "stopped"}
            or (job_status == "queued" and str(run.id) not in queued_ids)
            or (job_status == "started" and (job_heartbeat is None or now - job_heartbeat >= GRACE))
        ):
            transition_run(run, "failed")
            run.error_message = "Queued worker job was lost or stopped before execution"
        elif run.status in {"running", "cancelling"} and age >= GRACE:
            db_fresh = _aware(run.heartbeat_at) is not None and now - _aware(run.heartbeat_at) < GRACE
            rq_fresh = job_heartbeat is not None and now - job_heartbeat < GRACE
            if not db_fresh and not rq_fresh and job_status in {"missing", "failed", "canceled", "cancelled", "finished", "stopped", "started", "queued"}:
                transition_run(run, "failed")
                run.error_message = "Worker interrupted before the execution could finish"
        if session.is_modified(run):
            changed.append(str(run.id))
    session.commit()
    return changed
