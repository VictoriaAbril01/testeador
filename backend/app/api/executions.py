import hashlib
import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.errors import DomainError
from app.database.session import get_session
from app.models import Evidence, Finding, Project, RuleEvaluation, TestRun, TestStep
from app.schemas.api import ExecutionCreate, ExecutionHistoryRead, ExecutionRead, FindingRead, RuleEvaluationRead, StepRead, origin_of, target_origin
from app.api.projects import find_project
from app.services.queue import cancel_queued_job, enqueue_run, queue_enabled
from app.services.runs import transition_run
from app.services.retesting import assess_finding
from app.services.dashboard import execution_history
from tester.blackbox.policy import clean_url
from tester.reports.html import render_report


router = APIRouter(prefix="/executions", tags=["executions"])


def find_run(session: Session, run_id: UUID) -> TestRun:
    run = session.get(TestRun, run_id)
    if run is None:
        raise DomainError(404, "execution_not_found", "Execution not found")
    return run


def _request_key(project_id: UUID, kind: str, key: str | None, payload: dict) -> tuple[str | None, str | None]:
    if key is None:
        return None, None
    identity = hashlib.sha256(f"{project_id}:{kind}:{key}".encode()).hexdigest()
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return identity, fingerprint


def _create_run(session: Session, run: TestRun, identity: str | None, fingerprint: str | None) -> TestRun:
    if identity:
        existing = session.scalar(select(TestRun).where(TestRun.idempotency_key == identity))
        if existing:
            if existing.request_fingerprint != fingerprint:
                raise DomainError(409, "idempotency_conflict", "Idempotency key was used for different inputs")
            return existing
    run.idempotency_key = identity
    run.request_fingerprint = fingerprint
    run.dispatch_requested = queue_enabled()
    session.add(run)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(select(TestRun).where(TestRun.idempotency_key == identity)) if identity else None
        if existing is None:
            raise
        if existing.request_fingerprint != fingerprint:
            raise DomainError(409, "idempotency_conflict", "Idempotency key was used for different inputs") from None
        return existing
    session.refresh(run)
    if run.dispatch_requested:
        try:
            enqueue_run(str(run.id), run.execution_timeout_ms)
            current = session.get(TestRun, run.id, populate_existing=True, with_for_update=True)
            if current.status == "pending":
                transition_run(current, "queued")
            session.commit()
        except Exception:
            session.rollback()
            current = session.get(TestRun, run.id, populate_existing=True, with_for_update=True)
            if current.status in {"pending", "queued"}:
                transition_run(current, "failed")
                current.error_message = "Worker queue is unavailable"
            session.commit()
    return run


@router.post("", response_model=ExecutionRead, status_code=status.HTTP_201_CREATED)
def create_execution(payload: ExecutionCreate,
                     idempotency_key: str | None = Header(None, alias="Idempotency-Key", min_length=8, max_length=128),
                     session: Session = Depends(get_session)) -> TestRun:
    project = find_project(session, payload.project_id)
    if not project.is_active or project.modality != "blackbox":
        raise DomainError(409, "project_not_runnable", "Project is inactive or unsupported")
    allowed = {target_origin(target.scheme, target.hostname, target.port) for target in project.authorized_targets}
    try:
        base_origin = origin_of(project.base_url)
    except ValueError:
        raise DomainError(409, "invalid_project_url", "Project base URL is invalid") from None
    if base_origin not in allowed:
        raise DomainError(409, "scope_missing", "Base URL origin is not authorized")
    identity, fingerprint = _request_key(payload.project_id, "create", idempotency_key, payload.model_dump())
    return _create_run(session, TestRun(**payload.model_dump()), identity, fingerprint)


@router.get("", response_model=list[ExecutionRead])
def list_executions(project_id: UUID | None = None, limit: int = Query(50, ge=1, le=100),
                    offset: int = Query(0, ge=0), session: Session = Depends(get_session)) -> list[TestRun]:
    statement = select(TestRun)
    if project_id is not None:
        find_project(session, project_id)
        statement = statement.where(TestRun.project_id == project_id)
    return list(session.scalars(statement.order_by(TestRun.requested_at.desc(), TestRun.id).limit(limit).offset(offset)))


ExecutionStatusFilter = Literal["pending", "queued", "running", "cancelling", "completed", "failed", "cancelled"]


@router.get("/history", response_model=ExecutionHistoryRead)
def list_execution_history(project_id: UUID | None = None, status: ExecutionStatusFilter | None = None,
                           limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0, le=100000),
                           session: Session = Depends(get_session)) -> ExecutionHistoryRead:
    if project_id is not None:
        find_project(session, project_id)
    return execution_history(session, limit=limit, offset=offset, project_id=project_id, status=status)


@router.get("/{run_id}", response_model=ExecutionRead)
def get_execution(run_id: UUID, session: Session = Depends(get_session)) -> TestRun:
    return find_run(session, run_id)


@router.get("/{run_id}/findings", response_model=list[FindingRead])
def list_findings(
    run_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> list[Finding]:
    find_run(session, run_id)
    return list(session.scalars(
        select(Finding)
        .where(Finding.run_id == run_id)
        .order_by(Finding.created_at, Finding.id)
        .limit(limit)
        .offset(offset)
    ))


@router.post("/{run_id}/retest", response_model=ExecutionRead, status_code=201)
def retest_execution(run_id: UUID,
                     idempotency_key: str | None = Header(None, alias="Idempotency-Key", min_length=8, max_length=128),
                     session: Session = Depends(get_session)) -> TestRun:
    previous = find_run(session, run_id)
    if previous.status != "completed":
        raise DomainError(409, "retest_unavailable", "Only a completed execution can be retested")
    project = find_project(session, previous.project_id)
    if not project.is_active or project.modality != "blackbox":
        raise DomainError(409, "project_not_runnable", "Project is inactive or unsupported")
    recorded = list(dict.fromkeys(session.scalars(select(TestStep.target).where(
        TestStep.run_id == run_id, TestStep.action == "navigate",
        (TestStep.status.like("HTTP %") | (TestStep.status == "failed")),
        TestStep.target.is_not(None)).order_by(TestStep.step_number)).all()))
    if not recorded:
        raise DomainError(409, "scenario_missing", "No recorded navigation can be retested")
    # The runner opens the login page itself and always queues project.base_url.
    # Replaying either consumes the page budget and may omit an affected page.
    already_visited = {clean_url(project.base_url)}
    if project.credential:
        already_visited.add(clean_url(project.credential.login_url))
    urls = [url for url in recorded if clean_url(url) not in already_visited]
    run = TestRun(project_id=previous.project_id, retest_of_run_id=previous.id, scenario_urls=urls[:previous.max_pages],
                  max_pages=previous.max_pages, max_depth=previous.max_depth, max_requests=previous.max_requests,
                  max_concurrency=previous.max_concurrency, page_timeout_ms=previous.page_timeout_ms,
                  execution_timeout_ms=previous.execution_timeout_ms, slow_navigation_ms=previous.slow_navigation_ms)
    identity, fingerprint = _request_key(previous.project_id, "retest", idempotency_key,
                                         {"source": str(previous.id), "urls": urls[:previous.max_pages]})
    return _create_run(session, run, identity, fingerprint)


@router.post("/{run_id}/retry", response_model=ExecutionRead, status_code=201)
def retry_execution(run_id: UUID,
                    idempotency_key: str | None = Header(None, alias="Idempotency-Key", min_length=8, max_length=128),
                    session: Session = Depends(get_session)) -> TestRun:
    previous = find_run(session, run_id)
    if previous.status not in {"failed", "cancelled"}:
        raise DomainError(409, "retry_unavailable", "Only a failed or cancelled execution can be retried")
    project = find_project(session, previous.project_id)
    if not project.is_active or project.modality != "blackbox":
        raise DomainError(409, "project_not_runnable", "Project is inactive or unsupported")
    run = TestRun(project_id=previous.project_id, retry_of_run_id=previous.id,
                  scenario_urls=previous.scenario_urls,
                  max_pages=previous.max_pages, max_depth=previous.max_depth,
                  max_requests=previous.max_requests, max_concurrency=previous.max_concurrency,
                  page_timeout_ms=previous.page_timeout_ms, execution_timeout_ms=previous.execution_timeout_ms,
                  slow_navigation_ms=previous.slow_navigation_ms)
    identity, fingerprint = _request_key(previous.project_id, "retry", idempotency_key, {"source": str(previous.id)})
    return _create_run(session, run, identity, fingerprint)


@router.post("/{run_id}/cancel", response_model=ExecutionRead)
def cancel_execution(run_id: UUID, session: Session = Depends(get_session)) -> TestRun:
    run = session.get(TestRun, run_id, with_for_update=True)
    if run is None:
        raise DomainError(404, "execution_not_found", "Execution not found")
    if run.status in {"completed", "failed"}:
        raise DomainError(409, "execution_finished", "Execution has already finished")
    if run.status in {"pending", "queued"}:
        run.cancellation_requested = True
        transition_run(run, "cancelled")
        session.commit()
        try:
            cancel_queued_job(str(run.id))
        except Exception:
            # The DB state also invalidates a job that Redis already delivered.
            pass
    elif run.status == "running":
        run.cancellation_requested = True
        transition_run(run, "cancelling")
        session.commit()
    return run


@router.get("/{run_id}/cancellation")
def cancellation_status(run_id: UUID, session: Session = Depends(get_session)) -> dict:
    run = find_run(session, run_id)
    return {"run_id": str(run.id), "status": run.status,
            "requested": run.cancellation_requested, "completed": run.status == "cancelled",
            "finished_at": run.finished_at}


@router.get("/{run_id}/comparison")
def compare_retest(run_id: UUID, session: Session = Depends(get_session)) -> dict:
    run = find_run(session, run_id)
    if run.retest_of_run_id is None:
        raise DomainError(409, "not_a_retest", "Execution is not a retest")
    previous = find_run(session, run.retest_of_run_id)
    before = list(session.scalars(select(Finding).where(Finding.run_id == previous.id)))
    after = list(session.scalars(select(Finding).where(Finding.run_id == run.id)))
    old = {item.fingerprint: item for item in before}
    old_counts = dict(session.execute(select(Evidence.finding_id, func.count(Evidence.id)).where(Evidence.finding_id.in_([f.id for f in before])).group_by(Evidence.finding_id)).all()) if before else {}
    new_counts = dict(session.execute(select(Evidence.finding_id, func.count(Evidence.id)).where(Evidence.finding_id.in_([f.id for f in after])).group_by(Evidence.finding_id)).all()) if after else {}
    compared = []
    consumed: set[UUID] = set()
    for key, original in sorted(old.items()):
        assessment = assess_finding(session, original, run)
        current = assessment.current_finding
        if current is not None:
            consumed.add(current.id)
        compared.append({"fingerprint": key, "previous_finding_id": str(original.id),
                         "current_finding_id": str(current.id) if current else None,
                         "previous_result": original.observed_result,
                         "current_result": current.observed_result if current else
                         f"HTTP {assessment.observed_status}" if assessment.observed_status is not None else None,
                         "previous_evidence_count": old_counts.get(original.id, 0),
                         "current_evidence_count": new_counts.get(current.id, 0) if current else 0,
                         "assessment": assessment.status})
    if run.status == "completed":
        for current in after:
            if current.id not in consumed:
                compared.append({"fingerprint": current.fingerprint, "previous_finding_id": None,
                                 "current_finding_id": str(current.id), "previous_result": None,
                                 "current_result": current.observed_result, "previous_evidence_count": 0,
                                 "current_evidence_count": new_counts.get(current.id, 0), "assessment": "new"})
    return {
        "previous_run_id": str(previous.id), "current_run_id": str(run.id),
        "previous_finished_at": previous.finished_at, "current_finished_at": run.finished_at,
        "complete": run.status == "completed", "previous_status": previous.status, "current_status": run.status,
        "findings": compared,
    }


@router.get("/{run_id}/report", response_class=Response)
def download_report(run_id: UUID, session: Session = Depends(get_session)) -> Response:
    run = find_run(session, run_id)
    project = session.get(Project, run.project_id)
    findings = list(session.scalars(select(Finding).where(Finding.run_id == run_id).order_by(Finding.created_at, Finding.id)))
    evidence = list(session.scalars(select(Evidence).where(Evidence.finding_id.in_([f.id for f in findings])))) if findings else []
    grouped = {finding.id: [item for item in evidence if item.finding_id == finding.id] for finding in findings}
    html = render_report(run, project, findings, grouped)
    return Response(html, media_type="text/html; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="testlab-{run.id}.html"',
        "Cache-Control": "no-store", "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
        "X-Content-Type-Options": "nosniff",
    })


@router.get("/{run_id}/steps", response_model=list[StepRead])
def list_steps(
    run_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> list[TestStep]:
    find_run(session, run_id)
    return list(session.scalars(
        select(TestStep)
        .where(TestStep.run_id == run_id)
        .order_by(TestStep.step_number)
        .limit(limit)
        .offset(offset)
    ))


@router.get("/{run_id}/rule-evaluations", response_model=list[RuleEvaluationRead])
def list_rule_evaluations(run_id: UUID, limit: int = Query(100, ge=1, le=100),
                          offset: int = Query(0, ge=0), session: Session = Depends(get_session)) -> list[RuleEvaluation]:
    find_run(session, run_id)
    return list(session.scalars(select(RuleEvaluation).where(RuleEvaluation.run_id == run_id)
                                .order_by(RuleEvaluation.id).limit(limit).offset(offset)))
