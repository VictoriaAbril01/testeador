"""Standalone, escaped HTML report containing no embedded secret or evidence bytes."""

from collections import Counter
from html import escape
from tester.evidence.storage import read_screenshot_status


def render_report(run, project, findings, evidence_by_finding) -> str:
    def e(value) -> str:
        return escape(str(value if value is not None else "No registrado"), quote=True)

    types = Counter(f.error_type for f in findings)
    modules = Counter(f.module_name or "No identificado" for f in findings)
    states = Counter(f.validation_status for f in findings)
    rows = []
    for finding in findings:
        steps = "".join(f"<li>{e(step)}</li>" for step in (finding.reproduction_steps or []))
        artifacts = "".join(
            f"<li>{e(item.kind)} · {e(item.id)} · {e(item.size_bytes)} bytes"
            + (f" · Captura: {e(detail['status'])} ({e(detail['reason'])}) · URL: {e(detail['page_url'])}"
               if item.kind == "screenshot_status" and (detail := read_screenshot_status(item.relative_path)) else "")
            + "</li>" for item in evidence_by_finding.get(finding.id, []))
        rows.append(f"<article><h3>{e(finding.error_type)} · {e(finding.id)}</h3>"
                    f"<p>Severidad: {e(finding.severity)} · Validación: {e(finding.validation_status)}</p>"
                    f"<p>Módulo: {e(finding.module_name)} · Pantalla: {e(finding.page_name)} · Elemento: {e(finding.element)}</p>"
                    f"<p>URL: {e(finding.url)} · Detectado: {e(finding.created_at)}</p>"
                    f"<p>{e(finding.description)}</p><p>Esperado: {e(finding.expected_result)}</p>"
                    f"<p>Observado: {e(finding.observed_result)}</p><h4>Reproducción</h4><ol>{steps}</ol>"
                    f"<h4>Evidencias privadas</h4><ul>{artifacts}</ul></article>")

    def summary(counter) -> str:
        return "".join(f"<li>{e(key)}: {count}</li>" for key, count in sorted(counter.items()))

    return ("<!doctype html><html lang='es'><head><meta charset='utf-8'>"
            "<title>TestLab · Reporte</title><style>body{font:16px system-ui;max-width:900px;margin:3rem auto;"
            "padding:0 1rem;color:#172033}article{border-top:1px solid #ccd;padding:1rem 0}"
            "h1,h2,h3{color:#142c50}li{margin:.3rem 0}p{overflow-wrap:anywhere}</style></head><body>"
            f"<h1>Reporte de ejecución {e(run.id)}</h1><p>Proyecto: {e(project.name)} · Entorno: {e(project.environment)}</p>"
            f"<p>Estado: {e(run.status)} · Solicitada: {e(run.requested_at)} · Finalizada: {e(run.finished_at)}</p>"
            f"<h2>Resumen</h2><p>Observaciones/incidencias: {len(findings)}</p>"
            f"<h3>Tipos</h3><ul>{summary(types)}</ul><h3>Módulos</h3><ul>{summary(modules)}</ul>"
            f"<h3>Validación</h3><ul>{summary(states)}</ul><h2>Incidencias</h2>{''.join(rows)}"
            "<p>Los archivos de evidencia requieren acceso autenticado en TestLab.</p></body></html>")
