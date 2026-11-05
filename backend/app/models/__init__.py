"""Import all mapped classes for Alembic metadata discovery."""

from app.models.entities import (
    AuthorizedTarget,
    Credential,
    DiscoveredPage,
    Environment,
    Evidence,
    Finding,
    FindingValidation,
    Project,
    RuleEvaluation,
    TestRun,
    TestStep,
)

__all__ = [
    "AuthorizedTarget",
    "Credential",
    "DiscoveredPage",
    "Environment",
    "Evidence",
    "Finding",
    "FindingValidation",
    "Project",
    "RuleEvaluation",
    "TestRun",
    "TestStep",
]
