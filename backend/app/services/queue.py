"""Optional RQ dispatch. API tests and local development keep queuing disabled by default."""

import os

from redis import Redis
from rq import Queue
from rq.job import Job
from rq.exceptions import NoSuchJobError


QUEUE_NAME = "testlab"


def connection() -> Redis:
    return Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))


def queue_enabled() -> bool:
    return os.getenv("TESTLAB_QUEUE_ENABLED", "false").lower() == "true"


def enqueue_run(run_id: str, timeout_ms: int) -> None:
    redis = connection()
    with redis.lock(f"testlab:dispatch:{run_id}", timeout=30, blocking_timeout=5):
        try:
            Job.fetch(run_id, connection=redis)
            return
        except NoSuchJobError:
            pass
        Queue(QUEUE_NAME, connection=redis).enqueue(
            "workers.jobs.execute_run", run_id, job_id=run_id,
            job_timeout=max(60, timeout_ms // 1000 + 60),
            result_ttl=86400, failure_ttl=86400,
        )


def cancel_queued_job(run_id: str) -> None:
    redis = connection()
    try:
        job = Job.fetch(run_id, connection=redis)
    except NoSuchJobError:
        return
    status = job.get_status()
    if getattr(status, "value", status) in {"queued", "deferred"}:
        Queue(QUEUE_NAME, connection=redis).remove(job)
        job.cancel()
