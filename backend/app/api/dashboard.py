"""Authenticated summary of persisted projects, runs and findings."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_session
from app.schemas.api import DashboardRead
from app.services.dashboard import dashboard_snapshot

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardRead)
def get_dashboard(session: Session = Depends(get_session)) -> DashboardRead:
    return dashboard_snapshot(session)
