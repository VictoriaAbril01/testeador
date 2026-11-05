"""Evidence retention maintenance; also available as a worker CLI task."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Evidence
from tester.evidence.storage import delete


def purge_expired(session: Session) -> int:
    items = list(session.scalars(select(Evidence).where(Evidence.expires_at <= datetime.now(timezone.utc))))
    for item in items:
        delete(item.relative_path)
        session.delete(item)
    session.commit()
    return len(items)
