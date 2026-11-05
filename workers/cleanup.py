"""Run with `python -m workers.cleanup` from a scheduler for idle retention cleanup."""

from sqlalchemy.orm import Session

from app.database.session import get_engine
from app.services.evidence import purge_expired


if __name__ == "__main__":
    with Session(get_engine()) as session:
        purge_expired(session)
