from datetime import datetime, timezone

from app.core.errors import DomainError
from app.models import TestRun


ALLOWED_TRANSITIONS = {
    "pending": {"queued", "running", "failed", "cancelled"},
    "queued": {"running", "failed", "cancelled"},
    "running": {"cancelling", "completed", "failed"},
    "cancelling": {"cancelled", "failed"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


def transition_run(run: TestRun, next_status: str) -> None:
    if next_status not in ALLOWED_TRANSITIONS.get(run.status, set()):
        raise DomainError(409, "invalid_transition", "Execution state transition is not allowed")
    now = datetime.now(timezone.utc)
    run.status = next_status
    if next_status == "running":
        run.started_at = now
    if next_status in {"completed", "failed", "cancelled"}:
        run.finished_at = now
