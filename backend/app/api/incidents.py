"""Authorized evidence and manual validation for an operator-owned TestLab instance."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.database.session import get_session
from app.models import Evidence, Finding, FindingValidation, TestRun
from app.services.retesting import assess_finding
from app.schemas.api import EvidenceRead, FindingRead, ValidationCreate, ValidationRead
from tester.evidence.storage import artifact_path, delete, read_screenshot_status

router = APIRouter(tags=["incidents"])


def find_finding(session: Session, finding_id: UUID) -> Finding:
    finding = session.get(Finding, finding_id)
    if finding is None:
        raise DomainError(404, "finding_not_found", "Finding not found")
    return finding


@router.get("/findings", response_model=list[FindingRead])
def list_incidents(project_id: UUID | None = None, module: str | None = Query(None, max_length=200),
                   error_type: str | None = Query(None, max_length=50), validation_status: str | None = Query(None, max_length=30),
                   limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
                   session: Session = Depends(get_session)) -> list[Finding]:
    statement = select(Finding).join(TestRun, Finding.run_id == TestRun.id)
    if project_id is not None:
        statement = statement.where(TestRun.project_id == project_id)
    if module is not None:
        statement = statement.where(Finding.module_name == module)
    if error_type is not None:
        statement = statement.where(Finding.error_type == error_type)
    if validation_status is not None:
        statement = statement.where(Finding.validation_status == validation_status)
    return list(session.scalars(statement.order_by(Finding.created_at.desc(), Finding.id).limit(limit).offset(offset)))


@router.get("/findings/{finding_id}", response_model=FindingRead)
def get_finding(finding_id: UUID, session: Session = Depends(get_session)) -> Finding:
    return find_finding(session, finding_id)


@router.get("/findings/{finding_id}/evidence", response_model=list[EvidenceRead])
def list_evidence(finding_id: UUID, session: Session = Depends(get_session)) -> list[EvidenceRead]:
    find_finding(session, finding_id)
    items = list(session.scalars(select(Evidence).where(Evidence.finding_id == finding_id,
                                                      Evidence.expires_at > datetime.now(timezone.utc)).order_by(Evidence.created_at, Evidence.id)))
    return [evidence_response(item) for item in items]


def evidence_response(item: Evidence) -> EvidenceRead:
    result = EvidenceRead.model_validate(item)
    if item.kind != "screenshot_status":
        return result
    detail = read_screenshot_status(item.relative_path)
    if detail is None:
        return result
    try:
        return result.model_copy(update={
            "capture_status": detail["status"], "capture_reason": detail["reason"],
            "page_url": detail["page_url"], "captured_at": datetime.fromisoformat(detail["captured_at"]),
            "width": detail["width"], "height": detail["height"],
        })
    except (ValueError, TypeError):
        return result


@router.get("/findings/{finding_id}/validations", response_model=list[ValidationRead])
def list_validations(finding_id: UUID, session: Session = Depends(get_session)) -> list[FindingValidation]:
    find_finding(session, finding_id)
    return list(session.scalars(select(FindingValidation).where(FindingValidation.finding_id == finding_id)
                                .order_by(FindingValidation.validated_at, FindingValidation.id)))


@router.post("/findings/{finding_id}/validations", response_model=ValidationRead, status_code=201)
def validate_finding(finding_id: UUID, payload: ValidationCreate, session: Session = Depends(get_session)) -> FindingValidation:
    finding = find_finding(session, finding_id)
    allowed = {
        "detected": {"pending_confirmation", "confirmed", "not_reproducible", "false_positive"},
        "pending_confirmation": {"confirmed", "not_reproducible", "false_positive"},
        "confirmed": {"fixed", "not_reproducible", "false_positive"},
        "not_reproducible": {"pending_confirmation", "confirmed", "false_positive"},
        "false_positive": {"pending_confirmation", "confirmed"},
        "fixed": {"retested", "confirmed"},
        "retested": {"confirmed", "fixed"},
    }
    if payload.status not in allowed.get(finding.validation_status, set()):
        raise DomainError(409, "invalid_validation_transition", "Validation state transition is not allowed")
    if payload.status in {"fixed", "retested"} and not payload.notes:
        raise DomainError(422, "validation_notes_required", "Explain the manual verification in notes")
    if payload.status == "retested":
        completed_retests = list(session.scalars(select(TestRun).where(
            TestRun.retest_of_run_id == finding.run_id, TestRun.status == "completed")))
        verified = any(assess_finding(session, finding, retest).status == "not_observed_pending_verification"
                       for retest in completed_retests)
        if not verified:
            raise DomainError(409, "retest_evidence_missing", "A completed retest with executed scenario and reevaluated rule is required")
    record = FindingValidation(finding_id=finding.id, from_status=finding.validation_status,
                               to_status=payload.status, actor="operator", notes=payload.notes)
    finding.validation_status = payload.status
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


@router.get("/findings/{finding_id}/history", response_model=list[FindingRead])
def finding_history(finding_id: UUID, limit: int = Query(100, ge=1, le=100),
                    session: Session = Depends(get_session)) -> list[Finding]:
    finding = find_finding(session, finding_id)
    run = session.get(TestRun, finding.run_id)
    return list(session.scalars(select(Finding).join(TestRun, Finding.run_id == TestRun.id)
                                .where(TestRun.project_id == run.project_id, Finding.fingerprint == finding.fingerprint)
                                .order_by(Finding.created_at.desc(), Finding.id).limit(limit)))


@router.get("/evidence/{evidence_id}")
def download_evidence(evidence_id: UUID, session: Session = Depends(get_session)) -> FileResponse:
    item = session.get(Evidence, evidence_id)
    if item is None or item.expires_at <= datetime.now(timezone.utc):
        raise DomainError(404, "evidence_not_found", "Evidence not found")
    path = artifact_path(item.relative_path)
    if not path.is_file():
        raise DomainError(404, "evidence_not_found", "Evidence not found")
    media_type = "image/png" if item.kind == "screenshot" else "application/json"
    return FileResponse(path, media_type=media_type, filename=f"testlab-{item.id}{path.suffix}",
                        headers={"Cache-Control": "no-store", "Content-Security-Policy": "default-src 'none'", "X-Content-Type-Options": "nosniff"})


@router.delete("/evidence/{evidence_id}", status_code=204)
def remove_evidence(evidence_id: UUID, session: Session = Depends(get_session)) -> None:
    item = session.get(Evidence, evidence_id)
    if item is None:
        raise DomainError(404, "evidence_not_found", "Evidence not found")
    delete(item.relative_path)
    session.delete(item)
    session.commit()
