"""Pure rule and action coverage check for one recorded Black Box scenario."""

from dataclasses import dataclass

from tester.scenarios.types import RuleEvaluation


@dataclass(frozen=True)
class CoverageResult:
    status: str
    observed_status: int | None = None


def assess_coverage(
    scenario: dict | None,
    visited_pages: set[str],
    successful_navigations: set[str],
    login_succeeded: bool,
    evaluations: list[RuleEvaluation],
) -> CoverageResult:
    if not isinstance(scenario, dict) or not all(scenario.get(key) for key in ("page_url", "target_url", "rule_key")):
        return CoverageResult("inconclusive")
    page_url = scenario["page_url"]
    if page_url not in visited_pages or page_url not in successful_navigations:
        return CoverageResult("inconclusive")
    if scenario.get("requires_login") and not login_succeeded:
        return CoverageResult("inconclusive")
    matching = [item for item in evaluations if item.rule_key == scenario["rule_key"]
                and item.url == scenario["target_url"] and item.page_url == page_url
                and item.resource_type == scenario.get("resource_type")]
    if not matching:
        return CoverageResult("inconclusive")
    matched = next((item for item in matching if item.matched), None)
    if matched:
        return CoverageResult("persisting", matched.observed_status)
    return CoverageResult("not_observed_pending_verification", matching[-1].observed_status)
