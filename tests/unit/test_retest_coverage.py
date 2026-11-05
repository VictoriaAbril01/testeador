"""A clean retest needs the original action and the original rule to run again."""

import pytest

from tester.reproduction.coverage import assess_coverage
from tester.scenarios.types import RuleEvaluation


PAGE = "https://example.test/users"
SCENARIO = {"page_url": PAGE, "target_url": PAGE, "rule_key": "http_5xx",
            "resource_type": "document", "requires_login": True}


@pytest.mark.parametrize(
    ("pages", "navigations", "login", "evaluations"),
    [
        (set(), {PAGE}, True, [RuleEvaluation("http_5xx", PAGE, PAGE, "document", False, 200)]),
        ({PAGE}, set(), True, [RuleEvaluation("http_5xx", PAGE, PAGE, "document", False, 200)]),
        ({PAGE}, {PAGE}, False, [RuleEvaluation("http_5xx", PAGE, PAGE, "document", False, 200)]),
        ({PAGE}, {PAGE}, True, []),
        ({PAGE}, {PAGE}, True, [RuleEvaluation("http_5xx", "https://example.test/other", PAGE, "document", False, 200)]),
        ({PAGE}, {PAGE}, True, [RuleEvaluation("http_4xx", PAGE, PAGE, "document", False, 200)]),
        ({PAGE}, {PAGE}, True, [RuleEvaluation("http_5xx", PAGE, PAGE, "fetch", False, 200)]),
    ],
)
def test_missing_page_action_login_or_same_rule_is_inconclusive(pages, navigations, login, evaluations):
    assert assess_coverage(SCENARIO, pages, navigations, login, evaluations).status == "inconclusive"


def test_repeated_rule_distinguishes_error_from_evaluated_clean_result():
    clean = RuleEvaluation("http_5xx", PAGE, PAGE, "document", False, 200)
    failing = RuleEvaluation("http_5xx", PAGE, PAGE, "document", True, 500)
    assert assess_coverage(SCENARIO, {PAGE}, {PAGE}, True, [clean]).status == "not_observed_pending_verification"
    result = assess_coverage(SCENARIO, {PAGE}, {PAGE}, True, [clean, failing])
    assert result.status == "persisting" and result.observed_status == 500


def test_legacy_finding_without_scenario_is_inconclusive():
    assert assess_coverage(None, {PAGE}, {PAGE}, True,
                           [RuleEvaluation("http_5xx", PAGE, PAGE, "document", False, 200)]).status == "inconclusive"
