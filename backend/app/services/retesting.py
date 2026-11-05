"""Conservative retest assessment based on recorded actions and rule coverage."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DiscoveredPage, Finding, RuleEvaluation, TestRun, TestStep
from tester.reproduction.coverage import assess_coverage
from tester.scenarios.types import RuleEvaluation as RecordedEvaluation


@dataclass(frozen=True)
class RetestAssessment:
    status: str
    current_finding: Finding | None = None
    observed_status: int | None = None


def assess_finding(session: Session, original: Finding, retest: TestRun) -> RetestAssessment:
    if retest.retest_of_run_id != original.run_id or retest.project_id != original.run.project_id:
        return RetestAssessment("inconclusive")
    if retest.status == "failed":
        return RetestAssessment("technical_failure")
    if retest.status in {"pending", "running"}:
        return RetestAssessment("unknown")
    if retest.status != "completed":
        return RetestAssessment("inconclusive")

    scenario = original.scenario
    if not isinstance(scenario, dict) or not all(scenario.get(key) for key in ("page_url", "target_url", "rule_key")):
        return RetestAssessment("inconclusive")
    pages = set(session.scalars(select(DiscoveredPage.url).where(DiscoveredPage.run_id == retest.id)))
    steps = list(session.scalars(select(TestStep).where(TestStep.run_id == retest.id)))
    navigations = {step.page_url for step in steps if step.action == "navigate" and step.status.startswith("HTTP ")
                   and step.page_url}
    login_succeeded = any(step.action == "verify_login" and step.status == "success" for step in steps)
    recorded = [RecordedEvaluation(item.rule_key, item.url, item.page_url, item.resource_type,
                                   item.matched, item.observed_status)
                for item in session.scalars(select(RuleEvaluation).where(
                    RuleEvaluation.run_id == retest.id, RuleEvaluation.rule_key == scenario["rule_key"],
                    RuleEvaluation.url == scenario["target_url"], RuleEvaluation.page_url == scenario["page_url"]))]
    result = assess_coverage(scenario, pages, navigations, login_succeeded, recorded)
    if result.status == "persisting":
        target_url = scenario["target_url"]
        current = session.scalar(select(Finding).where(
            Finding.run_id == retest.id, Finding.error_type == original.error_type,
            Finding.url == target_url).order_by(Finding.created_at, Finding.id))
        return RetestAssessment("persisting", current, result.observed_status)
    return RetestAssessment(result.status, observed_status=result.observed_status)
