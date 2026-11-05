"""Persistence entities. Input validation and policy checks belong to later layers."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, MappedColumn, mapped_column, relationship

from app.database.base import Base


def id_column() -> MappedColumn[UUID]:
    return mapped_column(primary_key=True, default=uuid4)


def created_column() -> MappedColumn[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("environment IN ('development', 'staging', 'production', 'other')", name="environment"),
        CheckConstraint("modality IN ('blackbox', 'whitebox', 'hybrid')", name="modality"),
    )

    id: Mapped[UUID] = id_column()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    modality: Mapped[str] = mapped_column(String(20), nullable=False, server_default="blackbox")
    created_at: Mapped[datetime] = created_column()
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    authorized_targets: Mapped[list["AuthorizedTarget"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    environments: Mapped[list["Environment"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    credential: Mapped["Credential | None"] = relationship(back_populates="project", cascade="all, delete-orphan", uselist=False)
    runs: Mapped[list["TestRun"]] = relationship(back_populates="project")


class Environment(Base):
    __tablename__ = "environments"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_environments_project_name"),
        CheckConstraint("name IN ('development', 'staging', 'production', 'other')", name="name"),
    )

    id: Mapped[UUID] = id_column()
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(20), nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = created_column()

    project: Mapped[Project] = relationship(back_populates="environments")


class AuthorizedTarget(Base):
    __tablename__ = "authorized_targets"
    __table_args__ = (
        UniqueConstraint("project_id", "scheme", "hostname", "port", name="uq_authorized_target_origin"),
        CheckConstraint("scheme IN ('http', 'https')", name="scheme"),
        CheckConstraint("port BETWEEN 1 AND 65535", name="port"),
    )

    id: Mapped[UUID] = id_column()
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    scheme: Mapped[str] = mapped_column(String(5), nullable=False)
    hostname: Mapped[str] = mapped_column(String(253), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = created_column()

    project: Mapped[Project] = relationship(back_populates="authorized_targets")


class Credential(Base):
    __tablename__ = "credentials"
    __table_args__ = (CheckConstraint("auth_type IN ('form')", name="auth_type"),)

    id: Mapped[UUID] = id_column()
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)
    auth_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="form")
    login_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    username_selector: Mapped[str] = mapped_column(String(500), nullable=False)
    password_selector: Mapped[str] = mapped_column(String(500), nullable=False)
    submit_selector: Mapped[str] = mapped_column(String(500), nullable=False)
    success_selector: Mapped[str | None] = mapped_column(String(500))
    success_url_pattern: Mapped[str | None] = mapped_column(String(500))
    username_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    password_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = created_column()

    project: Mapped[Project] = relationship(back_populates="credential")


class TestRun(Base):
    __tablename__ = "test_runs"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'queued', 'running', 'cancelling', 'completed', 'failed', 'cancelled')", name="status"),
        CheckConstraint("max_pages > 0 AND max_depth >= 0 AND max_requests > 0 AND max_concurrency > 0", name="limits"),
        CheckConstraint("page_timeout_ms > 0 AND execution_timeout_ms > 0", name="timeouts"),
        Index("ix_test_runs_project_requested_at", "project_id", "requested_at"),
    )

    id: Mapped[UUID] = id_column()
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False)
    retest_of_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("test_runs.id", ondelete="SET NULL"), index=True)
    retry_of_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("test_runs.id", ondelete="SET NULL"), index=True)
    scenario_urls: Mapped[list | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    idempotency_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    request_fingerprint: Mapped[str | None] = mapped_column(String(64))
    dispatch_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    max_pages: Mapped[int] = mapped_column(Integer, nullable=False)
    max_depth: Mapped[int] = mapped_column(Integer, nullable=False)
    max_requests: Mapped[int] = mapped_column(Integer, nullable=False)
    max_concurrency: Mapped[int] = mapped_column(Integer, nullable=False)
    page_timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    slow_navigation_ms: Mapped[int | None] = mapped_column(Integer)
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_at: Mapped[datetime] = created_column()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="runs")
    pages: Mapped[list["DiscoveredPage"]] = relationship(back_populates="run")
    steps: Mapped[list["TestStep"]] = relationship(back_populates="run")
    findings: Mapped[list["Finding"]] = relationship(back_populates="run")
    rule_evaluations: Mapped[list["RuleEvaluation"]] = relationship(back_populates="run")


class DiscoveredPage(Base):
    __tablename__ = "discovered_pages"
    __table_args__ = (UniqueConstraint("run_id", "url", name="uq_discovered_pages_run_url"),)

    id: Mapped[UUID] = id_column()
    run_id: Mapped[UUID] = mapped_column(ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    module_name: Mapped[str] = mapped_column(String(200), nullable=False, server_default="No identificado")
    depth: Mapped[int] = mapped_column(Integer, nullable=False)
    navigation_ms: Mapped[int | None] = mapped_column(Integer)
    discovered_at: Mapped[datetime] = created_column()

    run: Mapped[TestRun] = relationship(back_populates="pages")


class TestStep(Base):
    __tablename__ = "test_steps"
    __table_args__ = (UniqueConstraint("run_id", "step_number", name="uq_test_steps_run_number"),)

    id: Mapped[UUID] = id_column()
    run_id: Mapped[UUID] = mapped_column(ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    module_name: Mapped[str | None] = mapped_column(String(200))
    page_name: Mapped[str | None] = mapped_column(String(500))
    page_url: Mapped[str | None] = mapped_column(String(2048))
    target: Mapped[str | None] = mapped_column(String(2048))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    observed_at: Mapped[datetime] = created_column()

    run: Mapped[TestRun] = relationship(back_populates="steps")


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint("run_id", "fingerprint", name="uq_findings_run_fingerprint"),
        CheckConstraint("severity IN ('info', 'low', 'medium', 'high', 'critical')", name="severity"),
        CheckConstraint("validation_status IN ('detected', 'pending_confirmation', 'confirmed', 'not_reproducible', 'false_positive', 'fixed', 'retested')", name="validation_status"),
        Index("ix_findings_run_created_at", "run_id", "created_at"),
        Index("ix_findings_fingerprint", "fingerprint"),
    )

    id: Mapped[UUID] = id_column()
    run_id: Mapped[UUID] = mapped_column(ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    error_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="detected")
    module_name: Mapped[str | None] = mapped_column(String(200))
    page_name: Mapped[str | None] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(String(2048))
    element: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    expected_result: Mapped[str | None] = mapped_column(Text)
    observed_result: Mapped[str] = mapped_column(Text, nullable=False)
    reproduction_steps: Mapped[list | None] = mapped_column(JSONB)
    scenario: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_column()

    run: Mapped[TestRun] = relationship(back_populates="findings")
    evidence: Mapped[list["Evidence"]] = relationship(back_populates="finding")
    validations: Mapped[list["FindingValidation"]] = relationship(back_populates="finding", order_by="FindingValidation.validated_at")

    @property
    def project_id(self) -> UUID:
        return self.run.project_id

    @property
    def environment(self) -> str:
        return self.run.project.environment


class RuleEvaluation(Base):
    __tablename__ = "rule_evaluations"
    __table_args__ = (Index("ix_rule_evaluations_run_rule_url", "run_id", "rule_key", "url"),)

    id: Mapped[UUID] = id_column()
    run_id: Mapped[UUID] = mapped_column(ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False)
    rule_key: Mapped[str] = mapped_column(String(50), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    page_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(50))
    matched: Mapped[bool] = mapped_column(Boolean, nullable=False)
    observed_status: Mapped[int | None] = mapped_column(Integer)

    run: Mapped[TestRun] = relationship(back_populates="rule_evaluations")


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (CheckConstraint("size_bytes >= 0", name="size_bytes"),)

    id: Mapped[UUID] = id_column()
    finding_id: Mapped[UUID] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = created_column()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    finding: Mapped[Finding] = relationship(back_populates="evidence")


class FindingValidation(Base):
    __tablename__ = "finding_validations"
    __table_args__ = (
        CheckConstraint("to_status IN ('pending_confirmation', 'confirmed', 'not_reproducible', 'false_positive', 'fixed', 'retested')", name="to_status"),
        Index("ix_finding_validations_finding_at", "finding_id", "validated_at"),
    )

    id: Mapped[UUID] = id_column()
    finding_id: Mapped[UUID] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), nullable=False)
    from_status: Mapped[str] = mapped_column(String(30), nullable=False)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    validated_at: Mapped[datetime] = created_column()

    finding: Mapped[Finding] = relationship(back_populates="validations")
