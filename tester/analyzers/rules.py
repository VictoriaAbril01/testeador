"""Convert browser observations into cautious, evidence-backed classifications."""

from dataclasses import dataclass

from tester.scenarios.types import Observation


@dataclass(frozen=True)
class Classification:
    error_type: str
    severity: str
    certainty: str
    description: str


def classify(observation: Observation) -> Classification | None:
    """A technical signal is not a confirmed product-level functional defect."""
    if observation.kind == "javascript_error":
        return Classification("javascript_error", "medium", "pending_confirmation", "Browser JavaScript exception observed")
    if observation.kind == "http_response" and observation.status_code is not None:
        if observation.status_code >= 500:
            return Classification("http_5xx", "high", "pending_confirmation", "HTTP server error observed")
        if observation.status_code == 404 and observation.technical_failure:
            return Classification("broken_link", "medium", "detected", "A navigated link returned HTTP 404")
        if observation.status_code >= 400:
            return Classification("http_4xx", "low", "pending_confirmation", "HTTP client error observed")
    if observation.kind in {"navigation_failure", "request_failure", "timeout"}:
        return Classification(observation.kind, "medium", "pending_confirmation", "Navigation or network failure observed")
    if observation.kind == "unexpected_response":
        return Classification("unexpected_response", "low", "pending_confirmation", "Response did not match a configured status rule")
    return None
