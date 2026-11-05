import pytest

from app.core.errors import DomainError
from app.models import TestRun as RunModel
from app.services.runs import transition_run


def test_valid_state_transitions_set_timestamps():
    run = RunModel(status="pending")
    transition_run(run, "running")
    assert run.started_at is not None
    transition_run(run, "completed")
    assert run.finished_at is not None


def test_invalid_state_transition_is_rejected():
    run = RunModel(status="completed")
    with pytest.raises(DomainError) as error:
        transition_run(run, "running")
    assert error.value.status_code == 409


def test_queue_and_cooperative_cancellation_transitions():
    run = RunModel(status="pending")
    transition_run(run, "queued")
    assert run.started_at is None and run.finished_at is None
    transition_run(run, "running")
    transition_run(run, "cancelling")
    assert run.finished_at is None
    with pytest.raises(DomainError):
        transition_run(run, "completed")
    transition_run(run, "cancelled")
    assert run.finished_at is not None
