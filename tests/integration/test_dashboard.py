"""Dashboard reads real PostgreSQL rows through the authenticated API."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import Finding, TestRun as RunModel
from tests.integration.test_api import auth_header, client, create_project, project_payload


def _run(connection, project_id, status="pending", *, retry_of=None):
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        run = RunModel(project_id=project_id, status=status, retry_of_run_id=retry_of,
                      max_pages=1, max_depth=0, max_requests=5, max_concurrency=1,
                      page_timeout_ms=5000, execution_timeout_ms=10000)
        if status in {"running", "completed", "failed", "cancelled"}:
            run.started_at = datetime.now(timezone.utc)
        if status in {"completed", "failed", "cancelled"}:
            run.finished_at = datetime.now(timezone.utc)
        session.add(run)
        session.commit()
        return run.id


def test_empty_dashboard_and_authorization(client, auth_header):
    http, _ = client
    assert http.get("/api/v1/dashboard").status_code == 401
    assert http.get("/api/v1/executions/history").status_code == 401
    snapshot = http.get("/api/v1/dashboard", headers=auth_header).json()
    assert snapshot == {"total_projects": 0, "total_executions": 0, "executions_by_status": {},
                        "total_findings": 0, "findings_pending_confirmation": 0,
                        "recent_executions": [], "recent_projects": []}
    assert http.get("/api/v1/executions/history", headers=auth_header).json()["total"] == 0


def test_dashboard_history_statuses_counts_filters_and_retry(client, auth_header):
    http, connection = client
    first = create_project(http, auth_header)
    second_response = http.post("/api/v1/projects", json=project_payload(name="Second platform"), headers=auth_header)
    assert second_response.status_code == 201
    second = second_response.json()
    queued = _run(connection, first["id"], "queued")
    running = _run(connection, first["id"], "running")
    completed = _run(connection, second["id"], "completed")
    cancelled = _run(connection, first["id"], "cancelled")
    failed = _run(connection, second["id"], "failed")
    retry = _run(connection, second["id"], "queued", retry_of=failed)
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        session.add_all([
            Finding(run_id=completed, fingerprint="a" * 64, error_type="http", severity="high",
                    description="Observed 500", observed_result="HTTP 500"),
            Finding(run_id=failed, fingerprint="b" * 64, error_type="javascript", severity="medium",
                    validation_status="confirmed", description="JS error", observed_result="Error"),
        ])
        session.commit()

    snapshot = http.get("/api/v1/dashboard", headers=auth_header).json()
    assert snapshot["total_projects"] == 2
    assert snapshot["total_executions"] == 6
    assert snapshot["executions_by_status"] == {"queued": 2, "running": 1, "completed": 1, "failed": 1, "cancelled": 1}
    assert snapshot["total_findings"] == 2
    assert snapshot["findings_pending_confirmation"] == 1
    assert len(snapshot["recent_executions"]) == 5
    assert {p["id"] for p in snapshot["recent_projects"]} == {first["id"], second["id"]}
    for project in snapshot["recent_projects"]:
        assert project["latest_execution"]["project_id"] == project["id"]
    assert "relative_path" not in str(snapshot)
    assert "password" not in str(snapshot)

    all_runs = http.get("/api/v1/executions/history?limit=2&offset=0", headers=auth_header).json()
    assert all_runs["total"] == 6 and len(all_runs["items"]) == 2
    later = http.get("/api/v1/executions/history?limit=2&offset=2", headers=auth_header).json()
    assert later["total"] == 6 and len(later["items"]) == 2
    assert {item["id"] for item in all_runs["items"]}.isdisjoint({item["id"] for item in later["items"]})
    by_project = http.get(f"/api/v1/executions/history?project_id={first['id']}", headers=auth_header).json()
    assert by_project["total"] == 3
    assert {item["id"] for item in by_project["items"]} == {str(queued), str(running), str(cancelled)}
    assert all(item["project_id"] == first["id"] for item in by_project["items"])
    assert all(item["project_name"] == first["name"] for item in by_project["items"])
    by_status = http.get("/api/v1/executions/history?status=failed", headers=auth_header).json()
    assert by_status["total"] == 1 and by_status["items"][0]["id"] == str(failed)
    retry_item = next(item for item in http.get(f"/api/v1/executions/history?project_id={second['id']}", headers=auth_header).json()["items"] if item["id"] == str(retry))
    assert retry_item["retry_of_run_id"] == str(failed)
    assert retry_item["finding_count"] == 0
    assert next(item for item in http.get(f"/api/v1/executions/history?project_id={second['id']}", headers=auth_header).json()["items"] if item["id"] == str(completed))["finding_count"] == 1


def test_history_filter_validation_and_existing_operator_scope(client, auth_header):
    http, _ = client
    for query in ("status=bogus", "limit=101", "offset=-1", "project_id=bad"):
        assert http.get(f"/api/v1/executions/history?{query}", headers=auth_header).status_code == 422
    assert http.get(f"/api/v1/executions/history?project_id={uuid4()}", headers=auth_header).status_code == 404


def test_dashboard_reads_run_transitions_after_each_request(client, auth_header):
    http, connection = client
    project = create_project(http, auth_header)
    run_id = _run(connection, project["id"], "queued")
    for status in ("queued", "running", "completed"):
        if status != "queued":
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                run = session.get(RunModel, run_id)
                run.status = status
                run.started_at = run.started_at or datetime.now(timezone.utc)
                if status == "completed":
                    run.finished_at = datetime.now(timezone.utc)
                session.commit()
        snapshot = http.get("/api/v1/dashboard", headers=auth_header).json()
        assert snapshot["executions_by_status"] == {status: 1}
        assert snapshot["recent_executions"][0]["status"] == status
        assert http.get("/api/v1/executions/history", headers=auth_header).json()["items"][0]["status"] == status
