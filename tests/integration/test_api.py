"""API tests against a migrated PostgreSQL database; writes are rolled back."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.database.config import get_database_url
from app.database.session import get_session
from app.main import app
from app.models import Credential, DiscoveredPage, Evidence, Finding, Project, RuleEvaluation, TestRun as RunModel, TestStep as StepModel
from app.api import executions as execution_api
from tester.evidence.storage import save
from app.services.evidence import purge_expired


@pytest.fixture
def client():
    engine = create_engine(get_database_url())
    connection = engine.connect()
    transaction = connection.begin()

    def session_override():
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    try:
        with TestClient(app) as test_client:
            yield test_client, connection
    finally:
        app.dependency_overrides.clear()
        transaction.rollback()
        connection.close()
        engine.dispose()


@pytest.fixture
def auth_header():
    token = get_settings().testlab_api_key.get_secret_value()
    return {"Authorization": f"Bearer {token}"}


def project_payload(**overrides):
    payload = {
        "name": "Example platform",
        "base_url": "https://example.test/app",
        "environment": "staging",
        "modality": "blackbox",
        "authorized_origins": ["https://example.test"],
    }
    payload.update(overrides)
    return payload


def create_project(client, auth_header):
    response = client.post("/api/v1/projects", json=project_payload(), headers=auth_header)
    assert response.status_code == 201, response.text
    return response.json()


def test_screenshot_status_is_authorized_and_visible_in_report(client, auth_header, monkeypatch, tmp_path):
    http, connection = client
    monkeypatch.setenv("TESTLAB_EVIDENCE_ROOT", str(tmp_path / "private"))
    project = create_project(http, auth_header)
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        run = RunModel(project_id=project["id"], max_pages=1, max_depth=0, max_requests=5,
                       max_concurrency=1, page_timeout_ms=5000, execution_timeout_ms=10000)
        session.add(run)
        session.flush()
        finding = Finding(run_id=run.id, fingerprint="d" * 64, error_type="navigation_failure",
                          severity="medium", description="Navigation failed", observed_result="No response")
        session.add(finding)
        session.flush()
        data = b'[{"status":"unavailable","reason":"navigation_failed","page_url":"https://example.test/app","captured_at":"2026-10-12T12:00:00+00:00"}]'
        relative, size, digest, expires = save(run.id, "screenshot_status", data)
        item = Evidence(finding_id=finding.id, kind="screenshot_status", relative_path=relative,
                        size_bytes=size, sha256=digest, expires_at=expires)
        session.add(item)
        session.commit()
        run_id, finding_id, evidence_id = str(run.id), str(finding.id), str(item.id)

    assert http.get(f"/api/v1/findings/{finding_id}/evidence").status_code == 401
    listing = http.get(f"/api/v1/findings/{finding_id}/evidence", headers=auth_header).json()
    assert listing[0]["capture_status"] == "unavailable"
    assert listing[0]["page_url"] == "https://example.test/app"
    assert "relative_path" not in listing[0]
    assert http.get(f"/api/v1/evidence/{evidence_id}").status_code == 401
    report = http.get(f"/api/v1/executions/{run_id}/report", headers=auth_header)
    assert report.status_code == 200
    assert "Captura: unavailable (navigation_failed)" in report.text


def test_health_openapi_and_authorization(client, auth_header):
    http, _ = client
    assert http.get("/health").json() == {"status": "ok"}
    assert http.get("/api/v1/projects").status_code == 401
    assert http.get("/api/v1/projects", headers={"Authorization": "Bearer invalid"}).status_code == 401
    assert http.get("/api/v1/projects", headers=auth_header).status_code == 200
    schema = http.get("/openapi.json").json()
    assert "/api/v1/projects" in schema["paths"]
    assert "/api/v1/executions/{run_id}/findings" in schema["paths"]
    assert schema["paths"]["/api/v1/projects"]["get"]["security"]


def test_project_registration_and_lookup(client, auth_header):
    http, connection = client
    project = create_project(http, auth_header)
    assert project["base_url"] == "https://example.test/app"
    assert project["authorized_origins"] == ["https://example.test:443"]
    assert project["environments"][0]["name"] == "staging"
    assert http.get(f"/api/v1/projects/{project['id']}", headers=auth_header).json()["id"] == project["id"]
    assert any(item["id"] == project["id"] for item in http.get("/api/v1/projects", headers=auth_header).json())
    assert http.get(f"/api/v1/projects/{uuid4()}", headers=auth_header).status_code == 404
    assert connection.execute(select(Project.id).where(Project.id == project["id"])).scalar_one() is not None


@pytest.mark.parametrize("base_url", ["ftp://example.test", "http://user:pass@example.test", "https://example.test/?token=secret", "http://"])
def test_invalid_project_urls_are_rejected_without_echo(client, auth_header, base_url):
    http, _ = client
    response = http.post("/api/v1/projects", json=project_payload(base_url=base_url), headers=auth_header)
    assert response.status_code == 422
    assert "secret" not in response.text
    assert "pass" not in response.text


def test_scope_must_be_explicit(client, auth_header):
    http, _ = client
    response = http.post(
        "/api/v1/projects",
        json=project_payload(authorized_origins=["https://another.test"]),
        headers=auth_header,
    )
    assert response.status_code == 422


def test_credentials_are_encrypted_and_never_returned(client, auth_header):
    http, connection = client
    project = create_project(http, auth_header)
    payload = {
        "login_url": "https://example.test/login",
        "username_selector": "#user",
        "password_selector": "#password",
        "submit_selector": "button[type=submit]",
        "success_selector": "#dashboard",
        "username": "qa-operator",
        "password": "sample-secret-password",
    }
    response = http.post(f"/api/v1/projects/{project['id']}/credentials", json=payload, headers=auth_header)
    assert response.status_code == 200, response.text
    assert "sample-secret-password" not in response.text
    assert "qa-operator" not in response.text
    with Session(bind=connection) as session:
        credential = session.scalar(select(Credential).where(Credential.project_id == project["id"]))
        assert credential is not None
        assert credential.password_ciphertext != payload["password"].encode()
        assert credential.username_ciphertext != payload["username"].encode()
        assert payload["password"].encode() not in credential.password_ciphertext
        cipher = Fernet(get_settings().testlab_fernet_key.get_secret_value().encode())
        assert cipher.decrypt(credential.password_ciphertext).decode() == payload["password"]

    outside = {**payload, "login_url": "https://other.test/login"}
    assert http.post(f"/api/v1/projects/{project['id']}/credentials", json=outside, headers=auth_header).status_code == 422


def test_execution_creation_and_result_reads(client, auth_header):
    http, connection = client
    project = create_project(http, auth_header)
    response = http.post("/api/v1/executions", json={"project_id": project["id"]}, headers=auth_header)
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["status"] == "pending"
    assert http.get(f"/api/v1/executions/{run['id']}", headers=auth_header).json()["id"] == run["id"]
    assert http.get(f"/api/v1/executions/{run['id']}").status_code == 401
    assert http.get(f"/api/v1/executions/{run['id']}/findings", headers=auth_header).json() == []
    assert http.get(f"/api/v1/executions/{run['id']}/steps", headers=auth_header).json() == []
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        session.add(
            Finding(
                run_id=run["id"],
                fingerprint="b" * 64,
                error_type="http",
                severity="medium",
                description="HTTP 500 observed",
                observed_result="500",
                reproduction_steps=["Open the test page"],
            )
        )
        session.add(StepModel(run_id=run["id"], step_number=1, action="navigate", status="success"))
        session.commit()
    findings = http.get(f"/api/v1/executions/{run['id']}/findings?limit=1", headers=auth_header).json()
    steps = http.get(f"/api/v1/executions/{run['id']}/steps?limit=1", headers=auth_header).json()
    assert findings[0]["observed_result"] == "500"
    assert steps[0]["step_number"] == 1
    assert http.get(f"/api/v1/executions/{uuid4()}", headers=auth_header).status_code == 404
    assert http.post("/api/v1/executions", json={"project_id": str(uuid4())}, headers=auth_header).status_code == 404
    assert http.post(
        "/api/v1/executions", json={"project_id": project["id"], "max_pages": 0}, headers=auth_header
    ).status_code == 422


def test_retest_does_not_replay_login_or_base_page_within_page_budget(client, auth_header):
    http, connection = client
    project = create_project(http, auth_header)
    credential = http.post(f"/api/v1/projects/{project['id']}/credentials", headers=auth_header, json={
        "login_url": "https://example.test/login", "username_selector": "#user",
        "password_selector": "#password", "submit_selector": "button[type=submit]",
        "success_url_pattern": "/app", "username": "fixture", "password": "fixture-only-secret",
    })
    assert credential.status_code == 200
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        original = RunModel(project_id=project["id"], status="completed", max_pages=4, max_depth=1,
                            max_requests=30, max_concurrency=1, page_timeout_ms=15000,
                            execution_timeout_ms=60000)
        session.add(original)
        session.flush()
        for order, url in enumerate(("https://example.test/login", "https://example.test/app",
                                     "https://example.test/healthy", "https://example.test/broken"), 1):
            session.add(StepModel(run_id=original.id, step_number=order, action="navigate",
                                  page_url=url, target=url, status="HTTP 200"))
        session.commit()
        original_id = original.id
    response = http.post(f"/api/v1/executions/{original_id}/retest", headers=auth_header)
    assert response.status_code == 201, response.text
    with Session(bind=connection) as session:
        retest = session.get(RunModel, response.json()["id"])
        assert retest.scenario_urls == ["https://example.test/healthy", "https://example.test/broken"]
        assert retest.max_pages == 4


def test_database_error_does_not_expose_internal_values(client, auth_header):
    http, _ = client

    def broken_session():
        raise SQLAlchemyError("PRIVATE_DATABASE_VALUE")

    app.dependency_overrides[get_session] = broken_session
    response = http.get("/api/v1/projects", headers=auth_header)
    assert response.status_code == 503
    assert "PRIVATE_DATABASE_VALUE" not in response.text


def test_execution_dispatch_and_queue_failure_are_visible(client, auth_header, monkeypatch):
    http, _ = client
    project = create_project(http, auth_header)
    sent = []
    monkeypatch.setattr(execution_api, "queue_enabled", lambda: True)
    monkeypatch.setattr(execution_api, "enqueue_run", lambda run_id, timeout: sent.append((run_id, timeout)))
    success = http.post("/api/v1/executions", json={"project_id": project["id"]}, headers=auth_header)
    assert success.status_code == 201
    assert success.json()["status"] == "queued"
    assert sent == [(success.json()["id"], 120000)]

    def unavailable(*_args):
        raise ConnectionError("PRIVATE_REDIS_VALUE")

    monkeypatch.setattr(execution_api, "enqueue_run", unavailable)
    failed = http.post("/api/v1/executions", json={"project_id": project["id"]}, headers=auth_header)
    assert failed.status_code == 201
    assert failed.json()["status"] == "failed"
    assert failed.json()["error_message"] == "Worker queue is unavailable"
    assert "PRIVATE_REDIS_VALUE" not in failed.text


def test_execution_idempotency_and_cancellation_states(client, auth_header, monkeypatch):
    http, connection = client
    project = create_project(http, auth_header)
    sent: list[str] = []
    removed: list[str] = []
    monkeypatch.setattr(execution_api, "queue_enabled", lambda: True)
    monkeypatch.setattr(execution_api, "enqueue_run", lambda run_id, _timeout: sent.append(run_id))
    monkeypatch.setattr(execution_api, "cancel_queued_job", lambda run_id: removed.append(run_id))
    header = {**auth_header, "Idempotency-Key": "creation-unique-key-123"}
    payload = {"project_id": project["id"]}
    first = http.post("/api/v1/executions", json=payload, headers=header)
    second = http.post("/api/v1/executions", json=payload, headers=header)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"] and len(sent) == 1
    assert first.json()["status"] == "queued"
    assert http.post("/api/v1/executions", json={**payload, "max_pages": 3}, headers=header).status_code == 409
    assert http.get(f"/api/v1/executions/{first.json()['id']}/cancellation", headers=auth_header).json()["requested"] is False
    cancelled = http.post(f"/api/v1/executions/{first.json()['id']}/cancel", headers=auth_header)
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert removed == [first.json()["id"]]
    again = http.post(f"/api/v1/executions/{first.json()['id']}/cancel", headers=auth_header)
    assert again.status_code == 200 and again.json()["status"] == "cancelled"
    assert http.get(f"/api/v1/executions/{first.json()['id']}/cancellation", headers=auth_header).json()["completed"] is True
    retry = http.post(f"/api/v1/executions/{first.json()['id']}/retry", headers={**auth_header, "Idempotency-Key": "retry-unique-key-123"})
    assert retry.status_code == 201 and retry.json()["retry_of_run_id"] == first.json()["id"]
    assert http.post(f"/api/v1/executions/{first.json()['id']}/retry", headers={**auth_header, "Idempotency-Key": "retry-unique-key-123"}).json()["id"] == retry.json()["id"]
    assert len(sent) == 2
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        session.get(RunModel, retry.json()["id"]).status = "completed"
        session.commit()
    assert http.post(f"/api/v1/executions/{retry.json()['id']}/cancel", headers=auth_header).status_code == 409


def test_active_cancellation_is_cooperative_and_repeatable(client, auth_header, monkeypatch):
    http, connection = client
    monkeypatch.setattr(execution_api, "queue_enabled", lambda: False)
    project = create_project(http, auth_header)
    run = http.post("/api/v1/executions", json={"project_id": project["id"]}, headers=auth_header).json()
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        session.get(RunModel, run["id"]).status = "running"
        session.commit()
    response = http.post(f"/api/v1/executions/{run['id']}/cancel", headers=auth_header)
    assert response.status_code == 200 and response.json()["status"] == "cancelling"
    assert response.json()["finished_at"] is None
    assert http.post(f"/api/v1/executions/{run['id']}/cancel", headers=auth_header).json()["status"] == "cancelling"
    status = http.get(f"/api/v1/executions/{run['id']}/cancellation", headers=auth_header).json()
    assert status["requested"] is True and status["completed"] is False


def test_phase5_evidence_validation_report_history_and_retest(client, auth_header, monkeypatch, tmp_path):
    http, connection = client
    monkeypatch.setenv("TESTLAB_EVIDENCE_ROOT", str(tmp_path / "private"))
    monkeypatch.setattr(execution_api, "queue_enabled", lambda: False)
    project = create_project(http, auth_header)
    run = http.post("/api/v1/executions", json={"project_id": project["id"]}, headers=auth_header).json()
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        stored = save(uuid4(), "http_metadata", b'[{"status":500}]')
        relative, size, digest, expires = stored
        session.get(RunModel, run["id"]).status = "completed"
        finding = Finding(run_id=run["id"], fingerprint="c" * 64, error_type="http_5xx",
                          severity="high", module_name="Users", url="https://example.test/users",
                          description="<script>alert(1)</script>", observed_result="HTTP 500",
                          reproduction_steps=["Abrir https://example.test/users."],
                          scenario={"page_url": "https://example.test/users", "target_url": "https://example.test/users",
                                    "rule_key": "http_5xx", "resource_type": "document", "requires_login": False})
        session.add(finding)
        session.flush()
        session.add(Evidence(finding_id=finding.id, kind="http_metadata", relative_path=relative,
                             size_bytes=size, sha256=digest, expires_at=expires))
        session.add(StepModel(run_id=run["id"], step_number=1, action="navigate",
                              page_url="https://example.test/users", target="https://example.test/users", status="HTTP 500"))
        session.commit()
        finding_id = str(finding.id)
        evidence_id = str(finding.evidence[0].id)

    assert http.get(f"/api/v1/evidence/{evidence_id}").status_code == 401
    assert http.get(f"/api/v1/evidence/{evidence_id}", headers=auth_header).content == b'[{"status":500}]'
    listing = http.get(f"/api/v1/findings/{finding_id}/evidence", headers=auth_header).json()
    assert len(listing) == 1 and "relative_path" not in listing[0]
    assert http.get(f"/api/v1/findings/{finding_id}", headers=auth_header).json()["project_id"] == project["id"]
    assert len(http.get("/api/v1/findings?module=Users&error_type=http_5xx", headers=auth_header).json()) == 1
    assert http.get("/api/v1/findings?module=Other", headers=auth_header).json() == []
    report = http.get(f"/api/v1/executions/{run['id']}/report", headers=auth_header)
    assert report.status_code == 200 and "attachment" in report.headers["content-disposition"]
    assert "&lt;script&gt;" in report.text and "<script>alert(1)</script>" not in report.text
    assert "HTTP 500" in report.text

    changed = http.post(f"/api/v1/findings/{finding_id}/validations", json={"status": "confirmed", "notes": "Replicado"}, headers=auth_header)
    assert changed.status_code == 201 and changed.json()["actor"] == "operator"
    assert http.post(f"/api/v1/findings/{finding_id}/validations", json={"status": "confirmed"}, headers=auth_header).status_code == 409
    assert http.post(f"/api/v1/findings/{finding_id}/validations", json={"status": "fixed"}, headers=auth_header).status_code == 422
    assert http.post(f"/api/v1/findings/{finding_id}/validations", json={"status": "fixed", "notes": "Cambio revisado"}, headers=auth_header).status_code == 201
    assert http.post(f"/api/v1/findings/{finding_id}/validations", json={"status": "retested", "notes": "Sin fallo"}, headers=auth_header).status_code == 409
    assert len(http.get(f"/api/v1/findings/{finding_id}/validations", headers=auth_header).json()) == 2

    retest = http.post(f"/api/v1/executions/{run['id']}/retest", headers=auth_header).json()
    assert retest["retest_of_run_id"] == run["id"] and retest["status"] == "pending"
    pending = http.get(f"/api/v1/executions/{retest['id']}/comparison", headers=auth_header).json()
    assert pending["findings"][0]["assessment"] == "unknown"
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        session.get(RunModel, retest["id"]).status = "completed"
        session.commit()
    compared = http.get(f"/api/v1/executions/{retest['id']}/comparison", headers=auth_header).json()
    assert compared["findings"][0]["assessment"] == "inconclusive"
    assert http.post(f"/api/v1/findings/{finding_id}/validations", json={"status": "retested", "notes": "Sin cobertura"}, headers=auth_header).status_code == 409
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        session.add(DiscoveredPage(run_id=retest["id"], url="https://example.test/users", depth=0))
        session.add(StepModel(run_id=retest["id"], step_number=1, action="navigate", page_url="https://example.test/users",
                              target="https://example.test/users", status="HTTP 200"))
        session.commit()
    assert http.get(f"/api/v1/executions/{retest['id']}/comparison", headers=auth_header).json()["findings"][0]["assessment"] == "inconclusive"
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        session.add(RuleEvaluation(run_id=retest["id"], rule_key="http_5xx", url="https://example.test/other",
                                   page_url="https://example.test/users", resource_type="document", matched=False, observed_status=200))
        session.commit()
    assert http.get(f"/api/v1/executions/{retest['id']}/comparison", headers=auth_header).json()["findings"][0]["assessment"] == "inconclusive"
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        session.add(RuleEvaluation(run_id=retest["id"], rule_key="http_5xx", url="https://example.test/users",
                                   page_url="https://example.test/users", resource_type="document", matched=False, observed_status=200))
        session.commit()
    compared = http.get(f"/api/v1/executions/{retest['id']}/comparison", headers=auth_header).json()
    assert compared["findings"][0]["assessment"] == "not_observed_pending_verification"
    coverage = http.get(f"/api/v1/executions/{retest['id']}/rule-evaluations", headers=auth_header).json()
    assert http.get(f"/api/v1/executions/{retest['id']}/rule-evaluations").status_code == 401
    assert any(item["rule_key"] == "http_5xx" and item["url"] == "https://example.test/users"
               and item["observed_status"] == 200 and not item["matched"] for item in coverage)
    assert http.get(f"/api/v1/executions/{retest['id']}/steps", headers=auth_header).json()[0]["page_url"] == "https://example.test/users"
    assert http.get(f"/api/v1/findings/{finding_id}", headers=auth_header).json()["validation_status"] == "fixed"
    assert http.post(f"/api/v1/findings/{finding_id}/validations", json={"status": "retested", "notes": "Verificado manualmente"}, headers=auth_header).status_code == 201
    assert http.get(f"/api/v1/findings/{finding_id}", headers=auth_header).json()["validation_status"] == "retested"
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        session.add(Finding(run_id=retest["id"], fingerprint="c" * 64, error_type="http_5xx",
                            severity="high", description="Same", observed_result="HTTP 500"))
        session.add(RuleEvaluation(run_id=retest["id"], rule_key="http_5xx", url="https://example.test/users",
                                   page_url="https://example.test/users", resource_type="document", matched=True, observed_status=500))
        session.commit()
    assert len(http.get(f"/api/v1/findings/{finding_id}/history", headers=auth_header).json()) == 2
    assert http.get(f"/api/v1/executions/{retest['id']}/comparison", headers=auth_header).json()["findings"][0]["assessment"] == "persisting"
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        session.get(RunModel, retest["id"]).status = "failed"
        session.commit()
    assert http.get(f"/api/v1/executions/{retest['id']}/comparison", headers=auth_header).json()["findings"][0]["assessment"] == "technical_failure"
    assert len(http.get(f"/api/v1/findings/{finding_id}/evidence", headers=auth_header).json()) == 1
    assert http.delete(f"/api/v1/evidence/{evidence_id}", headers=auth_header).status_code == 204
    assert http.get(f"/api/v1/evidence/{evidence_id}", headers=auth_header).status_code == 404


def test_retest_needs_login_action_and_legacy_findings_remain_inconclusive(client, auth_header, monkeypatch):
    http, connection = client
    monkeypatch.setattr(execution_api, "queue_enabled", lambda: False)
    project = create_project(http, auth_header)
    original = http.post("/api/v1/executions", json={"project_id": project["id"]}, headers=auth_header).json()
    page_url = "https://example.test/users"
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        session.get(RunModel, original["id"]).status = "completed"
        protected = Finding(run_id=original["id"], fingerprint="d" * 64, error_type="http_5xx",
                            severity="high", description="HTTP 500", observed_result="HTTP 500",
                            url=page_url, scenario={"page_url": page_url, "target_url": page_url,
                                                     "rule_key": "http_5xx", "resource_type": "document", "requires_login": True})
        legacy = Finding(run_id=original["id"], fingerprint="e" * 64, error_type="javascript_error",
                         severity="medium", description="JS", observed_result="JS", url=page_url)
        session.add_all([protected, legacy, StepModel(run_id=original["id"], step_number=1,
                        action="navigate", page_url=page_url, target=page_url, status="HTTP 500")])
        session.commit()
        protected_id = str(protected.id)
    retest = http.post(f"/api/v1/executions/{original['id']}/retest", headers=auth_header).json()
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        session.get(RunModel, retest["id"]).status = "completed"
        session.add(DiscoveredPage(run_id=retest["id"], url=page_url, depth=0))
        session.add(StepModel(run_id=retest["id"], step_number=1, action="navigate", page_url=page_url,
                              target=page_url, status="HTTP 200"))
        session.add(RuleEvaluation(run_id=retest["id"], rule_key="http_5xx", url=page_url,
                                   page_url=page_url, resource_type="document", matched=False, observed_status=200))
        session.commit()
    comparison = http.get(f"/api/v1/executions/{retest['id']}/comparison", headers=auth_header).json()
    assert [item["assessment"] for item in comparison["findings"]] == ["inconclusive", "inconclusive"]
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        session.add(StepModel(run_id=retest["id"], step_number=2, action="verify_login",
                              page_url="https://example.test/login", status="success"))
        session.commit()
    comparison = http.get(f"/api/v1/executions/{retest['id']}/comparison", headers=auth_header).json()
    assert comparison["findings"][0]["assessment"] == "not_observed_pending_verification"
    assert comparison["findings"][1]["assessment"] == "inconclusive"
    assert http.post(f"/api/v1/findings/{protected_id}/validations", json={"status": "confirmed"}, headers=auth_header).status_code == 201
    assert http.post(f"/api/v1/findings/{protected_id}/validations", json={"status": "fixed", "notes": "Revisión manual"}, headers=auth_header).status_code == 201
    assert http.post(f"/api/v1/findings/{protected_id}/validations", json={"status": "retested", "notes": "Evaluado de nuevo"}, headers=auth_header).status_code == 201


def test_evidence_retention_removes_expired_file_and_record(client, auth_header, monkeypatch, tmp_path):
    http, connection = client
    monkeypatch.setenv("TESTLAB_EVIDENCE_ROOT", str(tmp_path / "private"))
    project = create_project(http, auth_header)
    run = http.post("/api/v1/executions", json={"project_id": project["id"]}, headers=auth_header).json()
    stored = save(uuid4(), "console_log", b"[]")
    relative, size, digest, _ = stored
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        finding = Finding(run_id=run["id"], fingerprint="e" * 64, error_type="javascript_error",
                          severity="medium", description="Observed", observed_result="Exception")
        session.add(finding)
        session.flush()
        item = Evidence(finding_id=finding.id, kind="console_log", relative_path=relative,
                        size_bytes=size, sha256=digest, expires_at=datetime.now(timezone.utc) - timedelta(days=1))
        session.add(item)
        session.commit()
        evidence_id = str(item.id)
    assert http.get(f"/api/v1/evidence/{evidence_id}", headers=auth_header).status_code == 404
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        assert purge_expired(session) == 1
    assert not (tmp_path / "private" / relative).exists()
