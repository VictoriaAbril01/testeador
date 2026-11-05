"""Bounded, database-backed dashboard and execution history queries."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Finding, Project, TestRun
from app.schemas.api import DashboardProjectRead, DashboardRead, ExecutionHistoryRead, ExecutionSummaryRead


def _finding_counts():
    return (select(Finding.run_id.label("run_id"), func.count(Finding.id).label("finding_count"))
            .group_by(Finding.run_id).subquery())


def _summary_rows(session: Session, *, limit: int, offset: int = 0,
                  project_id: UUID | None = None, status: str | None = None) -> list[ExecutionSummaryRead]:
    counts = _finding_counts()
    statement = (select(TestRun, Project.name, Project.modality, func.coalesce(counts.c.finding_count, 0))
                 .join(Project, TestRun.project_id == Project.id)
                 .outerjoin(counts, counts.c.run_id == TestRun.id))
    if project_id is not None:
        statement = statement.where(TestRun.project_id == project_id)
    if status is not None:
        statement = statement.where(TestRun.status == status)
    rows = session.execute(statement.order_by(TestRun.requested_at.desc(), TestRun.id.desc())
                           .limit(limit).offset(offset)).all()
    return [ExecutionSummaryRead(
        id=run.id, project_id=run.project_id, project_name=name, modality=modality,
        status=run.status, requested_at=run.requested_at, started_at=run.started_at,
        finished_at=run.finished_at, finding_count=count,
        retest_of_run_id=run.retest_of_run_id, retry_of_run_id=run.retry_of_run_id,
    ) for run, name, modality, count in rows]


def execution_history(session: Session, *, limit: int, offset: int,
                      project_id: UUID | None, status: str | None) -> ExecutionHistoryRead:
    count_query = select(func.count(TestRun.id))
    if project_id is not None:
        count_query = count_query.where(TestRun.project_id == project_id)
    if status is not None:
        count_query = count_query.where(TestRun.status == status)
    total = session.scalar(count_query) or 0
    return ExecutionHistoryRead(total=total, limit=limit, offset=offset,
                                items=_summary_rows(session, limit=limit, offset=offset,
                                                    project_id=project_id, status=status))


def dashboard_snapshot(session: Session) -> DashboardRead:
    projects_count = session.scalar(select(func.count(Project.id))) or 0
    by_status = {status: count for status, count in session.execute(
        select(TestRun.status, func.count(TestRun.id)).group_by(TestRun.status))}
    findings_count = session.scalar(select(func.count(Finding.id))) or 0
    pending_count = session.scalar(select(func.count(Finding.id)).where(
        Finding.validation_status.in_(("detected", "pending_confirmation")))) or 0
    recent = _summary_rows(session, limit=5)
    projects = list(session.scalars(select(Project).order_by(Project.created_at.desc(), Project.id.desc()).limit(5)))
    recent_projects = [DashboardProjectRead(
        id=project.id, name=project.name, modality=project.modality,
        latest_execution=next(iter(_summary_rows(session, limit=1, project_id=project.id)), None),
    ) for project in projects]
    return DashboardRead(total_projects=projects_count, total_executions=sum(by_status.values()),
                         executions_by_status=by_status, total_findings=findings_count,
                         findings_pending_confirmation=pending_count,
                         recent_executions=recent, recent_projects=recent_projects)
