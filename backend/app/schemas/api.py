from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr, model_validator


def origin_of(url: str | AnyHttpUrl) -> str:
    parts = urlsplit(str(url))
    hostname = parts.hostname
    if not hostname:
        raise ValueError("URL must include a host")
    host = f"[{hostname}]" if ":" in hostname else hostname
    port = parts.port or (443 if parts.scheme == "https" else 80)
    return f"{parts.scheme}://{host}:{port}"


def target_origin(scheme: str, hostname: str, port: int) -> str:
    host = f"[{hostname}]" if ":" in hostname else hostname
    return f"{scheme}://{host}:{port}"


def validate_navigation_url(url: AnyHttpUrl, *, origin_only: bool = False) -> None:
    parts = urlsplit(str(url))
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("URL must not contain credentials, query or fragment")
    if origin_only and parts.path not in ("", "/"):
        raise ValueError("Authorized origins must not include a path")


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    base_url: AnyHttpUrl
    environment: Literal["development", "staging", "production", "other"]
    modality: Literal["blackbox"] = "blackbox"
    authorized_origins: list[AnyHttpUrl] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_scope(self) -> "ProjectCreate":
        validate_navigation_url(self.base_url)
        origins = set()
        for url in self.authorized_origins:
            validate_navigation_url(url, origin_only=True)
            origins.add(origin_of(url))
        if len(origins) != len(self.authorized_origins):
            raise ValueError("Authorized origins must be unique")
        if origin_of(self.base_url) not in origins:
            raise ValueError("The base URL origin must be explicitly authorized")
        return self


class EnvironmentRead(BaseModel):
    id: UUID
    name: str
    base_url: str
    is_active: bool


class ProjectRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    base_url: str
    environment: str
    modality: str
    created_at: datetime
    is_active: bool
    authorized_origins: list[str]
    environments: list[EnvironmentRead]


class CredentialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login_url: AnyHttpUrl
    username_selector: str = Field(min_length=1, max_length=500)
    password_selector: str = Field(min_length=1, max_length=500)
    submit_selector: str = Field(min_length=1, max_length=500)
    success_selector: str | None = Field(default=None, max_length=500)
    success_url_pattern: str | None = Field(default=None, max_length=500)
    username: SecretStr = Field(min_length=1)
    password: SecretStr = Field(min_length=1)

    @model_validator(mode="after")
    def validate_login_url(self) -> "CredentialCreate":
        validate_navigation_url(self.login_url)
        if not self.success_selector and not self.success_url_pattern:
            raise ValueError("A success condition is required")
        return self


class CredentialRead(BaseModel):
    id: UUID
    project_id: UUID
    login_url: str
    auth_type: str
    created_at: datetime


class ExecutionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    max_pages: int = Field(default=20, ge=1, le=1000)
    max_depth: int = Field(default=3, ge=0, le=20)
    max_requests: int = Field(default=200, ge=1, le=10000)
    max_concurrency: int = Field(default=1, ge=1, le=10)
    page_timeout_ms: int = Field(default=15000, ge=1000, le=120000)
    execution_timeout_ms: int = Field(default=120000, ge=1000, le=3600000)
    slow_navigation_ms: int | None = Field(default=None, ge=1)


class ExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    retest_of_run_id: UUID | None
    retry_of_run_id: UUID | None
    status: str
    max_pages: int
    max_depth: int
    max_requests: int
    max_concurrency: int
    page_timeout_ms: int
    execution_timeout_ms: int
    slow_navigation_ms: int | None
    cancellation_requested: bool
    heartbeat_at: datetime | None
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None


class ExecutionSummaryRead(BaseModel):
    id: UUID
    project_id: UUID
    project_name: str
    modality: str
    status: str
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    finding_count: int
    retest_of_run_id: UUID | None
    retry_of_run_id: UUID | None


class ExecutionHistoryRead(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ExecutionSummaryRead]


class DashboardProjectRead(BaseModel):
    id: UUID
    name: str
    modality: str
    latest_execution: ExecutionSummaryRead | None


class DashboardRead(BaseModel):
    total_projects: int
    total_executions: int
    executions_by_status: dict[str, int]
    total_findings: int
    findings_pending_confirmation: int
    recent_executions: list[ExecutionSummaryRead]
    recent_projects: list[DashboardProjectRead]


class FindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    project_id: UUID
    environment: str
    fingerprint: str
    error_type: str
    severity: str
    validation_status: str
    module_name: str | None
    page_name: str | None
    url: str | None
    element: str | None
    description: str
    expected_result: str | None
    observed_result: str
    reproduction_steps: list | None
    scenario: dict | None
    created_at: datetime


class EvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    finding_id: UUID
    kind: str
    size_bytes: int
    sha256: str
    created_at: datetime
    expires_at: datetime
    capture_status: str | None = None
    capture_reason: str | None = None
    page_url: str | None = None
    captured_at: datetime | None = None
    width: int | None = None
    height: int | None = None


class ValidationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["pending_confirmation", "confirmed", "not_reproducible", "false_positive", "fixed", "retested"]
    notes: str | None = Field(default=None, max_length=2000)


class ValidationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    finding_id: UUID
    from_status: str
    to_status: str
    actor: str
    notes: str | None
    validated_at: datetime


class StepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    step_number: int
    action: str
    module_name: str | None
    page_name: str | None
    page_url: str | None
    target: str | None
    status: str
    observed_at: datetime


class RuleEvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    rule_key: str
    url: str
    page_url: str
    resource_type: str | None
    matched: bool
    observed_status: int | None
