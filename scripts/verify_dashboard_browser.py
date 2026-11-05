"""Read-only browser check against the local API and Vite preview.

Run with PYTHONPATH=backend;. after starting API and Vite preview on port 5174.
The operator key is read from .env and is never printed or persisted by this script.
"""

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright


load_dotenv(Path(__file__).resolve().parents[1] / ".env")
key = os.environ["TESTLAB_API_KEY"]
snapshot = httpx.get("http://127.0.0.1:8000/api/v1/dashboard",
                     headers={"Authorization": f"Bearer {key}"}, timeout=15)
snapshot.raise_for_status()
data = snapshot.json()

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True,
                                         executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    page = browser.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def connect_and_check() -> list[int]:
        page.get_by_label("Clave de operador").fill(key)
        page.get_by_role("button", name="Entrar a TestLab").click()
        page.get_by_text("Tu espacio de pruebas").wait_for(timeout=15000)
        page.wait_for_function("document.querySelectorAll('.stat-card strong').length === 4")
        values = [int(item.inner_text()) for item in page.locator(".stat-card strong").all()]
        expected = [data["total_projects"], data["total_executions"], data["total_findings"]]
        assert values[:3] == expected, (values, expected)
        return values

    page.goto("http://127.0.0.1:5174", wait_until="domcontentloaded")
    before = connect_and_check()
    page.reload(wait_until="domcontentloaded")
    after = connect_and_check()
    assert before == after
    page.get_by_role("link", name="Ver historial").click()
    page.get_by_role("heading", name="Historial de ejecuciones").wait_for()
    page.get_by_text(f"{data['total_executions']} registros en PostgreSQL").wait_for()
    assert not errors, errors
    print({"reload": "passed", "counts": after, "history_visible": True, "page_errors": len(errors)})
    browser.close()
