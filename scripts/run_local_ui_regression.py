"""Run the authorized local UI→API→RQ→Chromium regression on isolated services.

Requires migrated PostgreSQL at 127.0.0.1:15432, Redis at 127.0.0.1:16379,
an installed frontend build, and local Chrome. Never contacts external targets.
"""

import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
FRONTEND = "http://127.0.0.1:5175"
API = "http://127.0.0.1:18000"
FIXTURE = "http://127.0.0.1:18991"


def wait_http(url: str, seconds: int = 30) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise RuntimeError("Local service did not become ready")


def free_port(port: int) -> None:
    with socket.socket() as probe:
        probe.settimeout(0.5)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"Local test port {port} is already occupied")


def main() -> None:
    if not PYTHON.is_file() or not CHROME.is_file() or not (ROOT / "frontend" / "dist" / "index.html").is_file():
        raise RuntimeError("Install Python/Chrome dependencies and build frontend first")
    for port in (18000, 18991, 5175):
        free_port(port)
    with tempfile.TemporaryDirectory(prefix="testlab-ui-regression-") as private:
        operator_key = secrets.token_urlsafe(40)
        environment = dict(os.environ,
            PYTHONPATH=f"{ROOT / 'backend'};{ROOT}", POSTGRES_HOST="127.0.0.1",
            POSTGRES_PORT="15432", POSTGRES_DB="testlab", POSTGRES_USER="testlab",
            POSTGRES_PASSWORD="isolated-increment5-only", REDIS_URL="redis://127.0.0.1:16379/0",
            TESTLAB_API_KEY=operator_key, TESTLAB_FERNET_KEY=Fernet.generate_key().decode(),
            TESTLAB_QUEUE_ENABLED="true", TESTLAB_EVIDENCE_ROOT=str(Path(private) / "evidence"),
            TESTLAB_PRIVATE_WORKER="true", TESTLAB_PRIVATE_CIDRS="127.0.0.1/32",
            TESTLAB_CHROMIUM_EXECUTABLE=str(CHROME),
            TESTLAB_VITE_PROXY_TARGET=API,
        )
        processes: list[subprocess.Popen] = []
        handles = []

        def start(name: str, command: list[str], cwd: Path = ROOT) -> None:
            handle = open(Path(private) / f"{name}.log", "wb")
            handles.append(handle)
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            processes.append(subprocess.Popen(command, cwd=cwd, env=environment,
                                              stdout=handle, stderr=subprocess.STDOUT,
                                              creationflags=flags))

        try:
            start("fixture", [str(PYTHON), "-m", "uvicorn", "scripts.local_fixture_app:app",
                              "--host", "127.0.0.1", "--port", "18991", "--no-access-log"])
            start("api", [str(PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                          "--port", "18000", "--no-access-log"])
            worker_code = ("from redis import Redis; from rq import SimpleWorker; "
                           "SimpleWorker(['testlab'], connection=Redis.from_url('redis://127.0.0.1:16379/0')).work()")
            start("worker", [str(PYTHON), "-u", "-c", worker_code])
            node = shutil.which("node")
            if not node:
                raise RuntimeError("Node.js is required for the local preview")
            start("vite", [node, str(ROOT / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"),
                           "preview", "--host", "127.0.0.1", "--port", "5175"], ROOT / "frontend")
            wait_http(f"{FIXTURE}/health")
            wait_http(f"{API}/health")
            wait_http(FRONTEND)

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, executable_path=str(CHROME))
                page = browser.new_page(accept_downloads=True)
                errors: list[str] = []
                page.on("pageerror", lambda error: errors.append(type(error).__name__))
                page.goto(FRONTEND)
                page.get_by_label("Clave de operador").fill(operator_key)
                page.get_by_role("button", name="Entrar a TestLab").click()
                page.get_by_role("heading", name="Tu espacio de pruebas").wait_for()
                headers = {"Authorization": f"Bearer {operator_key}"}
                baseline = httpx.get(f"{API}/api/v1/dashboard", headers=headers, timeout=15).json()["total_executions"]
                page.get_by_role("link", name="Proyectos", exact=True).click()
                page.get_by_role("link", name="Nuevo proyecto").click()
                page.get_by_label("Nombre").fill("Fixture local increment 5")
                page.get_by_label("URL base").fill(f"{FIXTURE}/admin")
                page.get_by_role("button", name="Usar origen de URL").click()
                page.get_by_role("button", name="Registrar proyecto").click()
                page.get_by_role("heading", name="Fixture local increment 5").wait_for()
                project_id = page.url.rstrip("/").split("/")[-1]
                page.get_by_role("link", name="Configurar acceso").click()
                page.get_by_label("URL de acceso").fill(f"{FIXTURE}/auth/login")
                page.get_by_label("Selector de usuario").fill("#login_email")
                page.get_by_label("Selector de contraseña").fill("#login_password")
                page.get_by_label("Selector del botón").fill('button[type="submit"]')
                page.get_by_label("Patrón de URL de éxito").fill("/admin")
                page.locator('input[autocomplete="off"]').fill("fixture@example.test")
                page.locator('input[autocomplete="new-password"]').fill("fixture-only-password")
                page.get_by_role("button", name="Guardar acceso").click()
                page.get_by_text("Configuración guardada.", exact=False).wait_for()
                page.get_by_role("link", name="Proyecto", exact=True).click()
                page.get_by_role("link", name="Crear ejecución").click()
                for label, value in (
                    ("Máximo de páginas", "6"), ("Profundidad máxima", "1"),
                    ("Máximo de solicitudes", "30"), ("Concurrencia máxima", "1"),
                    ("Tiempo por página (ms)", "15000"), ("Tiempo total (ms)", "60000"),
                ):
                    page.get_by_label(label).fill(value)
                page.get_by_role("button", name="Crear ejecución").click()
                page.wait_for_url(re.compile(r"/executions/[0-9a-f-]{36}$"))
                run_id = page.url.rstrip("/").split("/")[-1]
                with httpx.Client(timeout=15) as client:
                    deadline = time.monotonic() + 100
                    while time.monotonic() < deadline:
                        response = client.get(f"{API}/api/v1/executions/{run_id}", headers=headers)
                        response.raise_for_status()
                        run = response.json()
                        if run["status"] in {"completed", "failed", "cancelled"}:
                            break
                        time.sleep(1)
                    assert run["status"] == "completed", "Local worker did not complete"
                    page.get_by_role("button", name="Actualizar").click()
                    findings = client.get(f"{API}/api/v1/executions/{run_id}/findings", headers=headers).json()
                    kinds = {item["error_type"] for item in findings}
                    assert {"javascript_error", "http_5xx", "broken_link"} <= kinds, kinds
                    assert not any(item.get("url") == f"{FIXTURE}/healthy" for item in findings)
                    assert all(item["reproduction_steps"] for item in findings)
                    steps = client.get(f"{API}/api/v1/executions/{run_id}/steps", headers=headers).json()
                    assert any(item["action"] == "verify_login" for item in steps)
                    assert all("fixture-only-password" not in str(item) for item in steps)
                    finding_id = findings[0]["id"]
                    assert client.get(f"{API}/api/v1/findings/{finding_id}/evidence").status_code == 401
                    evidence = client.get(f"{API}/api/v1/findings/{finding_id}/evidence", headers=headers).json()
                    assert any(item["kind"] == "screenshot" for item in evidence)
                    screenshot = next(item for item in evidence if item["kind"] == "screenshot")
                    content = client.get(f"{API}/api/v1/evidence/{screenshot['id']}", headers=headers).content
                    assert content.startswith(b"\x89PNG")
                    assert "relative_path" not in str(evidence)
                    report = client.get(f"{API}/api/v1/executions/{run_id}/report", headers=headers)
                    assert report.status_code == 200 and "fixture-only-password" not in report.text
                    with page.expect_download() as download:
                        page.get_by_role("button", name="Descargar reporte HTML").click()
                    assert download.value.suggested_filename.endswith(".html")
                    page.get_by_role("button", name="Repetir escenario").click()
                    page.wait_for_function("previous => location.pathname.startsWith('/executions/') && "
                                           "location.pathname.split('/').pop() !== previous", arg=run_id)
                    retest_id = page.url.rstrip("/").split("/")[-1]
                    assert retest_id != run_id
                    deadline = time.monotonic() + 100
                    while time.monotonic() < deadline:
                        retest = client.get(f"{API}/api/v1/executions/{retest_id}", headers=headers).json()
                        if retest["status"] in {"completed", "failed", "cancelled"}:
                            break
                        time.sleep(1)
                    assert retest["status"] == "completed"
                    comparison = client.get(f"{API}/api/v1/executions/{retest_id}/comparison", headers=headers).json()
                    assert comparison["complete"]
                    assert all(item["assessment"] == "persisting" for item in comparison["findings"])
                    page.reload()
                    page.get_by_label("Clave de operador").fill(operator_key)
                    page.get_by_role("button", name="Entrar a TestLab").click()
                    page.get_by_role("link", name="Resumen").click()
                    page.get_by_role("heading", name="Tu espacio de pruebas").wait_for()
                    page.wait_for_function("document.querySelectorAll('.stat-card strong').length === 4")
                    assert int(page.locator(".stat-card strong").nth(1).inner_text()) == baseline + 2
                    page.get_by_role("link", name="Ver historial").click()
                    page.get_by_text(f"{baseline + 2} registros en PostgreSQL").wait_for()
                    vite = processes[-1]
                    vite.terminate()
                    vite.wait(timeout=8)
                    start("vite-restarted", [node, str(ROOT / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"),
                                             "preview", "--host", "127.0.0.1", "--port", "5175"], ROOT / "frontend")
                    wait_http(FRONTEND)
                    page.reload()
                    page.get_by_label("Clave de operador").fill(operator_key)
                    page.get_by_role("button", name="Entrar a TestLab").click()
                    page.get_by_role("link", name="Resumen").click()
                    page.get_by_role("heading", name="Tu espacio de pruebas").wait_for()
                    page.get_by_role("link", name="Ver historial").click()
                    page.get_by_text(f"{baseline + 2} registros en PostgreSQL").wait_for()
                    assert not errors, "Frontend emitted a JavaScript error"
                    print({"project_id": project_id, "run_id": run_id, "retest_id": retest_id,
                           "status": run["status"], "findings": sorted(kinds), "evidence": len(evidence),
                           "steps": len(steps), "comparison": "persisting", "reload": "passed",
                           "frontend_restart": "passed"})
                browser.close()
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
            for process in reversed(processes):
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            for handle in handles:
                handle.close()
            # Windows may release inherited log handles slightly after process.wait().
            time.sleep(1)


if __name__ == "__main__":
    main()
