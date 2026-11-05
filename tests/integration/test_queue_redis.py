"""Opt-in Redis integration; run with TESTLAB_TEST_REDIS_URL against an isolated Redis."""

import os
from uuid import uuid4

import pytest
from redis import Redis
from rq import Queue
from rq.job import Job

from app.services.queue import cancel_queued_job, enqueue_run


def test_real_redis_dispatch_is_idempotent_and_cancel_removes_job(monkeypatch):
    url = os.getenv("TESTLAB_TEST_REDIS_URL")
    if not url:
        pytest.skip("Set TESTLAB_TEST_REDIS_URL for an isolated Redis")
    monkeypatch.setenv("REDIS_URL", url)
    redis = Redis.from_url(url)
    redis.ping()
    run_id = str(uuid4())
    queue = Queue("testlab", connection=redis)
    try:
        enqueue_run(run_id, 5000)
        enqueue_run(run_id, 5000)
        assert queue.get_job_ids().count(run_id) == 1
        job = Job.fetch(run_id, connection=redis)
        assert job.get_status().value == "queued" and job.timeout >= 60
        cancel_queued_job(run_id)
        assert run_id not in queue.get_job_ids()
        assert Job.fetch(run_id, connection=redis).get_status().value in {"canceled", "cancelled"}
    finally:
        redis.delete(f"testlab:dispatch:{run_id}")
        redis.delete(f"rq:job:{run_id}")
