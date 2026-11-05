"""Typed, secret-free records produced by a Black Box run."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class LoginConfig:
    url: str
    username_selector: str
    password_selector: str
    submit_selector: str
    success_selector: str | None
    success_url_pattern: str | None
    username: str = field(repr=False)
    password: str = field(repr=False)


@dataclass(frozen=True)
class Limits:
    max_pages: int = 20
    max_depth: int = 3
    max_requests: int = 200
    max_concurrency: int = 1
    page_timeout_ms: int = 15000
    execution_timeout_ms: int = 120000

    def __post_init__(self) -> None:
        if not (1 <= self.max_pages <= 1000 and 0 <= self.max_depth <= 20):
            raise ValueError("Invalid page or depth limit")
        if not (1 <= self.max_requests <= 10000 and 1 <= self.max_concurrency <= 10):
            raise ValueError("Invalid request or concurrency limit")
        if not (1000 <= self.page_timeout_ms <= 120000 and 1000 <= self.execution_timeout_ms <= 3600000):
            raise ValueError("Invalid timeout")


@dataclass(frozen=True)
class Element:
    kind: str
    text: str | None
    selector: str | None
    href: str | None = None


@dataclass(frozen=True)
class PageRecord:
    url: str
    title: str | None
    module: str | None
    depth: int
    navigation_ms: int | None
    headings: tuple[str, ...]
    menus: tuple[str, ...]
    elements: tuple[Element, ...]


@dataclass(frozen=True)
class StepRecord:
    order: int
    action: str
    page: str | None
    module: str | None
    element: str | None
    result: str
    timestamp: datetime = field(default_factory=utc_now)
    page_url: str | None = None


@dataclass(frozen=True)
class Observation:
    kind: str
    url: str | None
    page: str | None
    module: str | None
    detail: str
    status_code: int | None = None
    technical_failure: bool = False
    timestamp: datetime = field(default_factory=utc_now)
    resource_type: str | None = None


@dataclass(frozen=True)
class RuleEvaluation:
    rule_key: str
    url: str
    page_url: str
    resource_type: str | None
    matched: bool
    observed_status: int | None = None


@dataclass
class RunReport:
    pages: list[PageRecord] = field(default_factory=list)
    steps: list[StepRecord] = field(default_factory=list)
    observations: list[Observation] = field(default_factory=list)
    rule_evaluations: list[RuleEvaluation] = field(default_factory=list)
    screenshots: dict[str, bytes] = field(default_factory=dict)
    screenshot_diagnostics: dict[str, dict] = field(default_factory=dict)
    console_events: list[dict] = field(default_factory=list)
    http_events: list[dict] = field(default_factory=list)
    requests: int = 0
    completed: bool = False
    cancelled: bool = False
    stop_reason: str | None = None
