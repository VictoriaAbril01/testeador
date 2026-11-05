"""Build only steps supported by recorded browser actions."""

import hashlib
import json

from tester.blackbox.policy import clean_url
from tester.scenarios.types import Observation, StepRecord


def fingerprint(error_type: str, observation: Observation, module: str | None, element: str | None = None) -> str:
    value = [error_type, clean_url(observation.url) if observation.url else None,
             observation.detail.strip(), module or None, element or None]
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def reproduction_steps(observation: Observation, steps: list[StepRecord]) -> list[str]:
    """Describe recorded navigation and login actions; expose gaps explicitly."""
    navigated = {clean_url(step.element) for step in steps if step.action == "navigate" and
                 step.result.startswith("HTTP") and step.element}
    target_url = observation.url if observation.url and clean_url(observation.url) in navigated else observation.page or observation.url
    target = clean_url(target_url) if target_url else None
    result: list[str] = []
    visited: set[str] = set()
    for step in steps:
        if step.action == "navigate" and step.result.startswith("HTTP") and step.element:
            url = clean_url(step.element)
            if url not in visited:
                result.append(f"Abrir {url}.")
                visited.add(url)
            if target and url == target:
                break
        elif step.action == "submit_login" and step.result == "completed":
            result.append("Enviar el formulario de acceso con una cuenta de pruebas autorizada.")
    if target and target not in visited:
        result.append(f"Falta una navegación registrada hasta {target}; completar el recorrido manualmente.")
    if not result:
        result.append("No hay acciones suficientes registradas para reproducir este hallazgo.")
    result.append(f"Observar el resultado: {observation.detail}.")
    return result
