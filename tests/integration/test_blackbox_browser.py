"""Real Chromium checks against a local, controlled FastAPI application."""

import asyncio
import os
import socket
import threading
import time
from contextlib import contextmanager
from urllib.parse import parse_qs

import pytest
import uvicorn
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from redis import Redis
from rq import Queue, SimpleWorker
from uuid import uuid4
from io import BytesIO
from PIL import Image

from app.database.config import get_database_url
from tester.evidence.storage import read_screenshot_status
from app.models import AuthorizedTarget, DiscoveredPage, Evidence, Finding, Project, RuleEvaluation, TestRun as RunModel, TestStep as StepModel
from tester.blackbox.policy import ScopeError, ScopePolicy
from tester.runner import BlackBoxRunner
from tester.scenarios.types import Limits, LoginConfig
from workers import jobs


CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe"


@contextmanager
def sample_server():
    app = FastAPI()
    changed = {"count": 0, "websocket": 0, "worker": 0, "slow": 0}

    @app.get("/", response_class=HTMLResponse)
    def home():
        return '<h1>Home</h1><nav><a href="/healthy">Healthy</a><a href="/broken">Broken</a><a href="/server-error">Server error</a><a href="/js-error">JS error</a><a href="/outside">Outside</a><a href="/redirect-delete">Redirect delete</a><a href="/ws-page">WebSocket</a><a href="/worker-page">Worker</a><a href="/delete">Delete</a><a href="/healthy?token=secret">Query</a></nav>'

    @app.get("/healthy", response_class=HTMLResponse)
    def healthy():
        return '<main data-module="Catalog"><h1>Healthy page</h1><form><label for="q">Search</label><input id="q" name="q"></form><button data-testid="save">Save</button></main>'

    @app.get("/visual", response_class=HTMLResponse)
    def visual():
        return '''<html><body style="margin:0;background:#f5f8ff"><main style="padding:35px;background:#204a85;color:white">
          <h1>VISUAL LANDMARK</h1><section style="height:180px;background:#e45b31"></section>
          <p data-sensitive>PRIVATE-TOKEN-DO-NOT-SHOW</p><input type="password" value="secret-password"></main></body></html>'''

    @app.get("/redirect-visual")
    def redirect_visual():
        return RedirectResponse("/visual", status_code=302)

    @app.get("/spa", response_class=HTMLResponse)
    def spa():
        return '<div id="loading">Loading</div><script>setTimeout(() => { document.querySelector("#loading").remove(); document.body.innerHTML = "<main><h1>SPA READY</h1><section style=\\"height:180px;background:#c34096\\"></section></main>" }, 180)</script>'

    @app.get("/uniform", response_class=HTMLResponse)
    def uniform():
        return '<html><body style="margin:0;background:white"></body></html>'

    @app.get("/broken")
    def broken():
        return HTMLResponse("<h1>Missing page</h1>", status_code=404)

    @app.get("/server-error")
    def server_error():
        return HTMLResponse("<title>Server error</title><h1>Server error</h1>", status_code=500)

    @app.get("/js-error", response_class=HTMLResponse)
    def js_error():
        return '<h1>JavaScript page</h1><script>throw new Error("intentional failure")</script>'

    @app.get("/slow", response_class=HTMLResponse)
    async def slow():
        changed["slow"] += 1
        await asyncio.sleep(2)
        return '<h1>Slow page</h1>'

    @app.get("/ws-page", response_class=HTMLResponse)
    def websocket_page(request: Request):
        return f'<h1>WebSocket page</h1><script>new WebSocket("ws://127.0.0.1:{request.url.port}/ws")</script>'

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        changed["websocket"] += 1
        await websocket.accept()
        await websocket.close()

    @app.get("/worker-page", response_class=HTMLResponse)
    def worker_page():
        return '<h1>Worker page</h1><script>new Worker("/worker-script.js")</script>'

    @app.get("/worker-script.js")
    def worker_script():
        changed["worker"] += 1
        return HTMLResponse('fetch("http://127.0.0.1:9/secret")', media_type="text/javascript")

    @app.get("/outside")
    def outside():
        return RedirectResponse("http://127.0.0.1:9/secret", status_code=302)

    @app.get("/delete")
    def delete():
        changed["count"] += 1
        return {"deleted": True}

    @app.get("/redirect-delete")
    def redirect_delete():
        return RedirectResponse("/delete", status_code=302)

    @app.get("/login", response_class=HTMLResponse)
    def login():
        return '<h1>Login</h1><form action="/do-login" method="post"><input id="user" name="username"><input id="pass" name="password" type="password"><button id="submit" type="submit">Enter</button></form>'

    @app.post("/do-login")
    async def do_login(request: Request):
        values = parse_qs((await request.body()).decode("utf-8"))
        username = values.get("username", [""])[0]
        password = values.get("password", [""])[0]
        if username != "operator" or password != "test-password":
            return HTMLResponse("denied", status_code=401)
        response = RedirectResponse("/private", status_code=303)
        response.set_cookie("session", "local-session", httponly=True)
        return response

    @app.get("/private", response_class=HTMLResponse)
    def private(request: Request):
        if request.cookies.get("session") != "local-session":
            return RedirectResponse("/login")
        return '<main data-module="Private"><h1 id="signed-in">Signed in</h1><a href="/healthy">Healthy</a></main>'

    @app.get("/favicon.ico")
    def favicon():
        return HTMLResponse("", status_code=204)

    with socket.socket() as port_socket:
        port_socket.bind(("127.0.0.1", 0))
        port = port_socket.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("Sample server did not start")
    try:
        yield f"http://127.0.0.1:{port}", changed
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def policy_for(base: str) -> ScopePolicy:
    return ScopePolicy((base,), private_worker=True, private_cidrs=("127.0.0.1/32",))


def run(base: str, *, login: LoginConfig | None = None, limits: Limits | None = None):
    return asyncio.run(BlackBoxRunner(
        base_url=f"{base}/private" if login else f"{base}/",
        policy=policy_for(base), limits=limits or Limits(max_pages=8, max_depth=2, max_requests=30),
        login=login, chromium_executable=CHROME,
    ).run())


def test_chromium_discovers_and_classifies_without_false_positive():
    with sample_server() as (base, changed):
        report = run(base)
    urls = {page.url for page in report.pages}
    kinds = {item.kind for item in report.observations}
    assert report.completed
    assert f"{base}/healthy" in urls
    assert f"{base}/server-error" in urls
    assert f"{base}/js-error" in urls
    assert "javascript_error" in kinds
    assert any(item.status_code == 500 and item.url == f"{base}/server-error" for item in report.observations)
    assert any(item.status_code == 404 and item.technical_failure for item in report.observations)
    assert any(item.kind == "scope_blocked" for item in report.observations)
    assert any(item.kind == "scope_blocked" and item.url == f"{base}/delete" for item in report.observations)
    assert not any(item.url == f"{base}/healthy" for item in report.observations)
    assert not any(page.url == f"{base}/delete" for page in report.pages)
    assert changed["count"] == 0
    assert changed["websocket"] == 0
    assert changed["worker"] == 0
    assert any(step.action == "block_request" and step.result == "blocked" for step in report.steps)
    assert all("?token=" not in page.url for page in report.pages)
    assert [step.order for step in report.steps] == list(range(1, len(report.steps) + 1))
    healthy = next(page for page in report.pages if page.url == f"{base}/healthy")
    assert healthy.module == "Catalog" and "Healthy page" in healthy.headings
    assert any(element.selector == "[data-testid=\"save\"]" for element in healthy.elements)
    assert report.screenshots[f"{base}/healthy"].startswith(b"\x89PNG")
    assert report.screenshot_diagnostics[f"{base}/healthy"]["status"] == "valid"
    assert report.screenshot_diagnostics[f"{base}/server-error"]["status"] == "valid"
    assert report.screenshot_diagnostics[f"{base}/js-error"]["status"] == "valid"
    assert report.screenshot_diagnostics[f"{base}/broken"]["status"] == "valid"
    assert report.screenshot_diagnostics[f"{base}/outside"]["status"] == "unavailable"
    assert all("headers" not in event and "body" not in event for event in report.http_events)


def test_screenshots_follow_rendered_page_redirect_and_spa(tmp_path):
    with sample_server() as (base, _):
        def visit(path: str):
            return asyncio.run(BlackBoxRunner(
                base_url=f"{base}{path}", policy=policy_for(base),
                limits=Limits(max_pages=1, max_depth=0, max_requests=20), chromium_executable=CHROME,
            ).run())

        visual = visit("/visual")
        redirected = visit("/redirect-visual")
        spa = visit("/spa")
        uniform = visit("/uniform")

    visual_png = visual.screenshots[f"{base}/visual"]
    path = tmp_path / "visual-evidence.png"
    path.write_bytes(visual_png)
    with Image.open(BytesIO(visual_png)) as image:
        image.load()
        assert image.width >= 800 and image.height >= 600
        assert image.convert("RGB").getpixel((100, 150)) == (228, 91, 49)
    assert visual.screenshot_diagnostics[f"{base}/visual"]["status"] == "valid"
    assert b"PRIVATE-TOKEN-DO-NOT-SHOW" not in visual_png
    assert redirected.screenshot_diagnostics[f"{base}/visual"]["status"] == "valid"
    assert f"{base}/redirect-visual" not in redirected.screenshots
    assert spa.screenshot_diagnostics[f"{base}/spa"]["status"] == "valid"
    assert "SPA READY" in spa.pages[0].headings
    assert uniform.screenshot_diagnostics[f"{base}/uniform"]["status"] == "suspicious"
    assert f"{base}/uniform" in uniform.screenshots
    print(f"VISUAL_EVIDENCE={path}")


def test_login_isolated_and_secrets_absent_from_records():
    with sample_server() as (base, _):
        login = LoginConfig(f"{base}/login", "#user, [data-test='selector-secret']", "#pass", "#submit", "#signed-in", None, "operator", "test-password")
        report = run(base, login=login)
    assert report.completed
    assert any(step.action == "verify_login" and step.result == "success" for step in report.steps)
    assert any(page.url == f"{base}/private" for page in report.pages)
    assert "test-password" not in repr(report)
    assert "operator" not in repr(report)
    assert "selector-secret" not in repr(report)


def test_private_destination_needs_worker_and_explicit_cidr():
    policy = ScopePolicy(("http://127.0.0.1:8080",))
    with pytest.raises(ScopeError):
        policy.prepare()
    with pytest.raises(ScopeError):
        ScopePolicy(("http://127.0.0.1:8080",), private_cidrs=("127.0.0.1/32",))
    with pytest.raises(ScopeError):
        ScopePolicy(("http://127.0.0.1:8080",), private_worker=True, private_cidrs=("0.0.0.0/0",))


def test_page_and_request_limits_are_enforced():
    with sample_server() as (base, _):
        pages = run(base, limits=Limits(max_pages=2, max_depth=3, max_requests=30))
        requests = run(base, limits=Limits(max_pages=8, max_depth=3, max_requests=1))
    assert len(pages.pages) <= 2
    assert requests.requests <= 1
    assert requests.stop_reason == "request_limit"


def test_timeout_and_configured_response_rule():
    with sample_server() as (base, _):
        report = asyncio.run(BlackBoxRunner(
            base_url=f"{base}/healthy", policy=policy_for(base),
            limits=Limits(max_pages=1, max_requests=10), chromium_executable=CHROME,
            expected_statuses={f"{base}/healthy": frozenset({204})},
        ).run())
        timeout_report = asyncio.run(BlackBoxRunner(
            base_url=f"{base}/slow", policy=policy_for(base),
            limits=Limits(max_pages=1, max_requests=10, page_timeout_ms=1000, execution_timeout_ms=5000),
            chromium_executable=CHROME,
        ).run())
    assert report.completed and any(item.kind == "unexpected_response" for item in report.observations)
    assert not timeout_report.completed
    assert any(item.kind in {"navigation_failure", "timeout"} for item in timeout_report.observations)


def test_cooperative_cancellation_interrupts_navigation_and_browser_can_restart():
    with sample_server() as (base, _):
        started = time.monotonic()
        cancelled = asyncio.run(BlackBoxRunner(
            base_url=f"{base}/slow", policy=policy_for(base),
            limits=Limits(max_pages=1, max_requests=10, page_timeout_ms=10000, execution_timeout_ms=20000),
            chromium_executable=CHROME, cancellation_check=lambda: time.monotonic() - started > 0.5,
        ).run())
        healthy = run(base, limits=Limits(max_pages=1, max_requests=10))
    assert cancelled.cancelled and not cancelled.completed and cancelled.stop_reason == "cancelled"
    assert healthy.completed and not healthy.cancelled


def test_worker_persists_steps_pages_and_findings_in_transaction(monkeypatch, tmp_path):
    with sample_server() as (base, _):
        port = int(base.rsplit(":", 1)[1])
        engine = create_engine(get_database_url())
        connection = engine.connect()
        transaction = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                project = Project(name="Black Box fixture", base_url=f"{base}/", environment="staging", modality="blackbox")
                session.add(project)
                session.flush()
                session.add(AuthorizedTarget(project_id=project.id, scheme="http", hostname="127.0.0.1", port=port))
                execution = RunModel(project_id=project.id, max_pages=8, max_depth=2, max_requests=30, max_concurrency=1, page_timeout_ms=10000, execution_timeout_ms=60000)
                session.add(execution)
                session.commit()
                run_id = str(execution.id)

            monkeypatch.setattr(jobs, "Session", lambda _engine: Session(bind=connection, join_transaction_mode="create_savepoint"))
            monkeypatch.setattr(jobs, "get_engine", lambda: engine)
            monkeypatch.setenv("TESTLAB_PRIVATE_WORKER", "true")
            monkeypatch.setenv("TESTLAB_PRIVATE_CIDRS", "127.0.0.1/32")
            monkeypatch.setenv("TESTLAB_CHROMIUM_EXECUTABLE", CHROME)
            monkeypatch.setenv("TESTLAB_EVIDENCE_ROOT", str(tmp_path / "private"))
            jobs.execute_run(run_id)
            with Session(bind=connection) as session:
                persisted = session.get(RunModel, run_id)
                assert persisted is not None and persisted.status == "completed"
                assert session.scalars(select(DiscoveredPage).where(DiscoveredPage.run_id == run_id)).first() is not None
                assert session.scalars(select(StepModel).where(StepModel.run_id == run_id)).first() is not None
                findings = list(session.scalars(select(Finding).where(Finding.run_id == run_id)))
                types = {finding.error_type for finding in findings}
                assert {"javascript_error", "http_5xx", "broken_link"} <= types
                assert all(finding.scenario for finding in findings if finding.error_type in {"javascript_error", "http_5xx", "broken_link"})
                evaluations = list(session.scalars(select(RuleEvaluation).where(RuleEvaluation.run_id == run_id)))
                assert {"javascript_error", "http_5xx", "broken_link"} <= {item.rule_key for item in evaluations if item.matched}
                assert any(item.rule_key == "http_5xx" and item.url == f"{base}/healthy" and not item.matched for item in evaluations)
                assert any(finding.error_type == "http_5xx" and finding.page_name == "Server error" for finding in findings)
                assert all(finding.reproduction_steps for finding in findings)
                evidence = list(session.scalars(select(Evidence).join(Finding).where(Finding.run_id == run_id)))
                assert {item.kind for item in evidence} >= {"screenshot", "screenshot_status", "console_log", "http_metadata", "navigation_trace", "step_history"}
                assert all((tmp_path / "private" / item.relative_path).is_file() for item in evidence)
                for finding in findings:
                    statuses = [item for item in evidence if item.finding_id == finding.id and item.kind == "screenshot_status"]
                    assert statuses
                    assert all(read_screenshot_status(item.relative_path)["page_url"] for item in statuses)
        finally:
            transaction.rollback()
            connection.close()
            engine.dispose()


def test_real_rq_worker_processes_local_fixture_without_duplicate_browser_run(monkeypatch, tmp_path):
    url = os.getenv("TESTLAB_TEST_REDIS_URL")
    if not url:
        pytest.skip("Set TESTLAB_TEST_REDIS_URL for an isolated Redis")
    with sample_server() as (base, _):
        port = int(base.rsplit(":", 1)[1])
        engine = create_engine(get_database_url())
        connection = engine.connect()
        transaction = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                project = Project(name="RQ fixture", base_url=f"{base}/", environment="staging", modality="blackbox")
                session.add(project)
                session.flush()
                session.add(AuthorizedTarget(project_id=project.id, scheme="http", hostname="127.0.0.1", port=port))
                execution = RunModel(project_id=project.id, status="queued", dispatch_requested=True,
                                     max_pages=8, max_depth=2, max_requests=30, max_concurrency=1,
                                     page_timeout_ms=10000, execution_timeout_ms=60000)
                session.add(execution)
                session.commit()
                run_id = str(execution.id)
            monkeypatch.setattr(jobs, "Session", lambda _engine: Session(bind=connection, join_transaction_mode="create_savepoint"))
            monkeypatch.setattr(jobs, "get_engine", lambda: engine)
            monkeypatch.setattr(jobs, "_heartbeat_and_check", lambda _id: False)
            monkeypatch.setenv("TESTLAB_PRIVATE_WORKER", "true")
            monkeypatch.setenv("TESTLAB_PRIVATE_CIDRS", "127.0.0.1/32")
            monkeypatch.setenv("TESTLAB_CHROMIUM_EXECUTABLE", CHROME)
            monkeypatch.setenv("TESTLAB_EVIDENCE_ROOT", str(tmp_path / "private"))
            redis = Redis.from_url(url)
            queue = Queue(f"testlab-integration-{uuid4().hex}", connection=redis)
            queue.enqueue("workers.jobs.execute_run", run_id, job_id=run_id, job_timeout=120)
            SimpleWorker([queue], connection=redis).work(burst=True)
            with Session(bind=connection) as session:
                stored = session.get(RunModel, run_id)
                assert stored.status == "completed"
                findings = list(session.scalars(select(Finding).where(Finding.run_id == run_id)))
                count = len(findings)
                assert {item.error_type for item in findings} >= {
                    "javascript_error", "http_5xx", "broken_link"}
            jobs.execute_run(run_id)
            with Session(bind=connection) as session:
                assert session.get(RunModel, run_id).status == "completed"
                assert len(list(session.scalars(select(Finding).where(Finding.run_id == run_id)))) == count
        finally:
            transaction.rollback()
            connection.close()
            engine.dispose()


def test_worker_cancellation_keeps_observed_findings_and_evidence(monkeypatch, tmp_path):
    with sample_server() as (base, changed):
        port = int(base.rsplit(":", 1)[1])
        engine = create_engine(get_database_url())
        connection = engine.connect()
        transaction = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                project = Project(name="Cancellation fixture", base_url=f"{base}/server-error",
                                  environment="staging", modality="blackbox")
                session.add(project)
                session.flush()
                session.add(AuthorizedTarget(project_id=project.id, scheme="http", hostname="127.0.0.1", port=port))
                execution = RunModel(project_id=project.id, status="queued", dispatch_requested=True,
                                     scenario_urls=[f"{base}/slow"], max_pages=2, max_depth=0, max_requests=20,
                                     max_concurrency=1, page_timeout_ms=10000, execution_timeout_ms=20000)
                session.add(execution)
                session.commit()
                run_id = str(execution.id)
            monkeypatch.setattr(jobs, "Session", lambda _engine: Session(bind=connection, join_transaction_mode="create_savepoint"))
            monkeypatch.setattr(jobs, "get_engine", lambda: engine)
            monkeypatch.setattr(jobs, "_heartbeat_and_check", lambda _id: changed["slow"] > 0)
            monkeypatch.setenv("TESTLAB_PRIVATE_WORKER", "true")
            monkeypatch.setenv("TESTLAB_PRIVATE_CIDRS", "127.0.0.1/32")
            monkeypatch.setenv("TESTLAB_CHROMIUM_EXECUTABLE", CHROME)
            monkeypatch.setenv("TESTLAB_EVIDENCE_ROOT", str(tmp_path / "private"))
            jobs.execute_run(run_id)
            with Session(bind=connection) as session:
                stored = session.get(RunModel, run_id)
                assert stored.status == "cancelled" and stored.finished_at is not None
                findings = list(session.scalars(select(Finding).where(Finding.run_id == run_id)))
                assert any(item.error_type == "http_5xx" for item in findings)
                partial = list(session.scalars(select(Evidence).join(Finding).where(Finding.run_id == run_id)))
                assert partial
                assert any(item.kind == "screenshot_status" for item in partial)
        finally:
            transaction.rollback()
            connection.close()
            engine.dispose()
