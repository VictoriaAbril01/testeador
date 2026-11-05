"""RQ job that runs an authorized browser test and persists its observations."""

import asyncio
import json
import os
from datetime import datetime, timezone
from uuid import UUID

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.settings import get_settings
from app.database.session import get_engine
from app.models import DiscoveredPage, Evidence, Finding, Project, RuleEvaluation, TestRun, TestStep
from app.services.runs import transition_run
from app.services.evidence import purge_expired
from tester.analyzers.rules import classify
from tester.blackbox.policy import ScopePolicy
from tester.blackbox.policy import clean_url
from tester.runner import BlackBoxRunner
from tester.scenarios.types import Limits, LoginConfig, RunReport
from tester.evidence.storage import MAX_FILE_BYTES, MAX_RUN_BYTES, remove_run_artifacts, save
from tester.reproduction.rules import fingerprint, reproduction_steps


_SAFE_REASONS = {
    "execution_timeout": "Execution time limit reached",
    "request_limit": "Request limit reached",
    "authentication_failed": "Configured authentication did not succeed",
    "login_navigation_failed": "Login page could not be opened",
}


def _input_for_run(session: Session, run: TestRun) -> BlackBoxRunner:
    project = session.scalar(
        select(Project)
        .where(Project.id == run.project_id)
        .options(selectinload(Project.authorized_targets), selectinload(Project.credential))
    )
    if project is None or not project.is_active or project.modality != "blackbox":
        raise ValueError("Project is unavailable for Black Box execution")
    origins = tuple(f"{item.scheme}://{item.hostname}:{item.port}" for item in project.authorized_targets)
    private_worker = os.getenv("TESTLAB_PRIVATE_WORKER", "false").lower() == "true"
    cidrs = tuple(item.strip() for item in os.getenv("TESTLAB_PRIVATE_CIDRS", "").split(",") if item.strip())
    policy = ScopePolicy(origins, private_worker=private_worker, private_cidrs=cidrs)
    login = None
    if project.credential:
        credential = project.credential
        cipher = Fernet(get_settings().testlab_fernet_key.get_secret_value().encode("ascii"))
        login = LoginConfig(
            url=credential.login_url,
            username_selector=credential.username_selector,
            password_selector=credential.password_selector,
            submit_selector=credential.submit_selector,
            success_selector=credential.success_selector,
            success_url_pattern=credential.success_url_pattern,
            username=cipher.decrypt(credential.username_ciphertext).decode("utf-8"),
            password=cipher.decrypt(credential.password_ciphertext).decode("utf-8"),
        )
    return BlackBoxRunner(
        base_url=project.base_url,
        policy=policy,
        limits=Limits(
            max_pages=run.max_pages, max_depth=run.max_depth,
            max_requests=run.max_requests, max_concurrency=run.max_concurrency,
            page_timeout_ms=run.page_timeout_ms,
            execution_timeout_ms=run.execution_timeout_ms,
        ),
        login=login,
        chromium_executable=os.getenv("TESTLAB_CHROMIUM_EXECUTABLE") or None,
        scenario_urls=tuple(run.scenario_urls or ()),
        cancellation_check=lambda: _heartbeat_and_check(run.id),
    )


def _heartbeat_and_check(run_id: UUID) -> bool:
    with Session(get_engine()) as session:
        run = session.get(TestRun, run_id, with_for_update=True)
        if run is None or run.status not in {"running", "cancelling"}:
            return True
        run.heartbeat_at = datetime.now(timezone.utc)
        requested = run.cancellation_requested
        session.commit()
        return requested


def _persist(session: Session, run: TestRun, report: RunReport) -> None:
    page_by_url = {}
    for page in report.pages:
        if page.url in page_by_url:
            continue
        page_by_url[page.url] = page
        session.add(DiscoveredPage(
            run_id=run.id, url=page.url[:2048], title=page.title,
            module_name=page.module or "No identificado", depth=page.depth,
            navigation_ms=page.navigation_ms,
        ))
    for step in report.steps:
        session.add(TestStep(
            run_id=run.id, step_number=step.order, action=step.action[:50],
            module_name=step.module, page_name=(step.page or "")[:500] or None,
            page_url=step.page_url,
            target=(step.element or "")[:2048] or None,
            status=step.result[:30], observed_at=step.timestamp,
        ))
    for evaluation in report.rule_evaluations:
        session.add(RuleEvaluation(
            run_id=run.id, rule_key=evaluation.rule_key, url=evaluation.url,
            page_url=evaluation.page_url, resource_type=evaluation.resource_type,
            matched=evaluation.matched, observed_status=evaluation.observed_status,
        ))
    fingerprints = set()
    remaining = MAX_RUN_BYTES
    for observation in report.observations:
        category = classify(observation)
        if category is None:
            continue
        page = page_by_url.get(observation.url) or page_by_url.get(observation.page)
        identity = fingerprint(category.error_type, observation, page.module if page else None)
        if identity in fingerprints:
            continue
        fingerprints.add(identity)
        target_url = clean_url(observation.url) if observation.url else None
        page_url = clean_url(observation.page) if observation.page else target_url
        evaluated = any(item.rule_key == category.error_type and item.url == target_url
                        and item.page_url == page_url and item.resource_type == observation.resource_type
                        and item.matched for item in report.rule_evaluations)
        navigated = any(step.action == "navigate" and step.page_url == page_url
                        and (step.result.startswith("HTTP") or step.result == "failed") for step in report.steps)
        scenario = None
        if evaluated and navigated and page_url and target_url:
            scenario = {"page_url": page_url, "target_url": target_url,
                        "rule_key": category.error_type, "resource_type": observation.resource_type,
                        "requires_login": any(step.action == "verify_login" and step.result == "success"
                                              for step in report.steps)}
        finding = Finding(
            run_id=run.id, fingerprint=identity,
            error_type=category.error_type, severity=category.severity,
            validation_status=category.certainty,
            module_name=page.module if page else None,
            page_name=page.title if page else (observation.page[:500] if observation.page else None),
            url=observation.url[:2048] if observation.url else None, description=category.description,
            expected_result=observation.detail.split(";", 1)[0] if observation.kind == "unexpected_response" else None,
            observed_result=observation.detail,
            reproduction_steps=reproduction_steps(observation, report.steps),
            scenario=scenario,
        )
        session.add(finding)
        session.flush()
        affected = observation.url if observation.url in report.screenshot_diagnostics else observation.page or observation.url
        artifacts: list[tuple[str, bytes]] = []
        diagnostic = dict(report.screenshot_diagnostics.get(affected) or {})
        shot = report.screenshots.get(affected)
        if shot is not None:
            stored_shot = None
            # Reserve room for the status record even when the PNG nearly fills
            # the per-run budget.
            if len(shot) <= min(max(remaining - 512, 0), MAX_FILE_BYTES):
                try:
                    stored_shot = save(run.id, "screenshot", shot)
                except OSError:
                    pass
            if stored_shot is not None:
                relative, size, digest, expires = stored_shot
                remaining -= size
                session.add(Evidence(finding_id=finding.id, kind="screenshot", relative_path=relative,
                                     size_bytes=size, sha256=digest, expires_at=expires))
            else:
                diagnostic.update(status="unavailable", reason="storage_limit_or_failure")
        if diagnostic:
            artifacts.append(("screenshot_status", _json_bytes([{
                "page_url": affected, **diagnostic,
            }])))
        artifacts.extend([
            ("console_log", _json_bytes([event for event in report.console_events if event.get("page") == affected])),
            ("http_metadata", _json_bytes([event for event in report.http_events if event.get("page") == affected or event.get("url") == observation.url])),
            ("navigation_trace", _json_bytes([{"url": page.url, "depth": page.depth, "navigation_ms": page.navigation_ms} for page in report.pages])),
            ("step_history", _json_bytes([{"order": step.order, "action": step.action, "page": step.page,
                                             "element": step.element, "result": step.result, "timestamp": step.timestamp.isoformat()}
                                            for step in report.steps])),
        ])
        for kind, content in artifacts:
            if len(content) > remaining:
                continue
            stored = save(run.id, kind, content)
            if stored is None:
                continue
            relative, size, digest, expires = stored
            remaining -= size
            session.add(Evidence(finding_id=finding.id, kind=kind, relative_path=relative,
                                 size_bytes=size, sha256=digest, expires_at=expires))


def _json_bytes(data: list[dict]) -> bytes:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def execute_run(run_id: str) -> None:
    """Claim a pending run once; failure messages never include browser or secret data."""
    identity = UUID(run_id)
    with Session(get_engine()) as session:
        purge_expired(session)
        run = session.get(TestRun, identity, with_for_update=True)
        if run is None or run.status not in {"pending", "queued"} or run.cancellation_requested:
            return
        transition_run(run, "running")
        run.heartbeat_at = datetime.now(timezone.utc)
        session.commit()
        try:
            browser_run = _input_for_run(session, run)
            report = asyncio.run(browser_run.run())
            _persist(session, run, report)
            session.flush()
            session.refresh(run, with_for_update=True)
            if report.cancelled or run.cancellation_requested:
                if run.status == "running":
                    transition_run(run, "cancelling")
                transition_run(run, "cancelled")
                run.error_message = None
            else:
                transition_run(run, "completed" if report.completed else "failed")
                run.error_message = _SAFE_REASONS.get(report.stop_reason, "Browser run stopped") if report.stop_reason else None
            session.commit()
        except Exception:
            session.rollback()
            try:
                remove_run_artifacts(identity)
            except (OSError, ValueError):
                pass
            run = session.get(TestRun, identity)
            if run is not None and run.status in {"running", "cancelling"}:
                transition_run(run, "failed")
                run.error_message = "Browser run failed; check worker health and scope configuration"
                session.commit()
