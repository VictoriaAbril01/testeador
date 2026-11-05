"""Isolated, bounded Black Box browser run."""

import asyncio
import time
from collections import deque
from collections.abc import Callable
from datetime import datetime, timezone

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Request, Response, async_playwright

from tester.blackbox.policy import ScopeError, ScopePolicy, clean_url
from tester.discovery.dom import inspect_page
from tester.evidence.screenshots import capture_page
from tester.scenarios.types import Limits, LoginConfig, Observation, RuleEvaluation, RunReport, StepRecord


class BlackBoxRunner:
    def __init__(
        self,
        *,
        base_url: str,
        policy: ScopePolicy,
        limits: Limits,
        login: LoginConfig | None = None,
        chromium_executable: str | None = None,
        expected_statuses: dict[str, frozenset[int]] | None = None,
        scenario_urls: tuple[str, ...] = (),
        cancellation_check: Callable[[], bool] | None = None,
    ) -> None:
        self.base_url = base_url
        self.policy = policy
        self.limits = limits
        self.login = login
        self.chromium_executable = chromium_executable
        self.expected_statuses = expected_statuses or {}
        self.scenario_urls = scenario_urls
        self.cancellation_check = cancellation_check

    async def run(self) -> RunReport:
        report = RunReport()
        owner = asyncio.current_task()

        async def watch_cancellation() -> None:
            while True:
                if self.cancellation_check and await asyncio.to_thread(self.cancellation_check):
                    if owner:
                        owner.cancel()
                    return
                await asyncio.sleep(0.5)

        watcher = asyncio.create_task(watch_cancellation()) if self.cancellation_check else None
        try:
            async with asyncio.timeout(self.limits.execution_timeout_ms / 1000):
                await asyncio.to_thread(self.policy.prepare)
                self.policy.check(self.base_url, navigation=True)
                if self.login:
                    self.policy.check(self.login.url, navigation=True)
                for url in self.scenario_urls:
                    self.policy.check(url, navigation=True)
                await self._browse(report)
        except TimeoutError:
            report.stop_reason = "execution_timeout"
            last_page = next(reversed(report.screenshot_diagnostics), None)
            report.observations.append(Observation("timeout", last_page, last_page, None,
                                                   "Execution time limit reached"))
        except asyncio.CancelledError:
            report.cancelled = True
            report.stop_reason = "cancelled"
        finally:
            if watcher:
                watcher.cancel()
                try:
                    await watcher
                except asyncio.CancelledError:
                    pass
        return report

    async def _browse(self, report: RunReport) -> None:
        blocked: set[str] = set()
        login_post_url: str | None = None
        current_page = None

        async def guard(session, event: dict) -> None:
            nonlocal login_post_url
            request = event["request"]
            url = request["url"]
            request_id = event["requestId"]
            try:
                self.policy.check(url, navigation=event.get("resourceType") == "Document")
                method = request["method"].upper()
                allowed_login_write = login_post_url is not None and method == "POST" and clean_url(url) == login_post_url
                if method not in {"GET", "HEAD"} and not allowed_login_write:
                    raise ScopeError("Non-read-only request blocked")
                if report.requests >= self.limits.max_requests:
                    report.stop_reason = "request_limit"
                    raise ScopeError("Request limit reached")
                report.requests += 1
                await session.send("Fetch.continueRequest", {"requestId": request_id})
            except ValueError as exc:
                blocked.add(url)
                safe_target = self._safe_url(url)
                safe_page = self._safe_url(current_page.url) if current_page else None
                report.observations.append(Observation("scope_blocked", safe_target, safe_page, None, str(exc)))
                report.steps.append(StepRecord(
                    order=len(report.steps) + 1, action="block_request", page=safe_page,
                    module=None, element=safe_target, result="blocked",
                ))
                await session.send("Fetch.failRequest", {"requestId": request_id, "errorReason": "BlockedByClient"})

        def on_response(response: Response) -> None:
            safe_url = clean_url(response.url)
            resource_type = response.request.resource_type
            page_url = safe_url if response.request.is_navigation_request() else self._safe_url(current_page.url) if current_page else None
            if len(report.http_events) < self.limits.max_requests:
                report.http_events.append({"url": safe_url, "status": response.status,
                                           "method": response.request.method, "resource_type": resource_type,
                                           "page": page_url})
            if page_url:
                for rule_key, matched in (("http_5xx", response.status >= 500),
                                          ("http_4xx", 400 <= response.status < 500 and not (response.status == 404 and response.request.is_navigation_request()))):
                    report.rule_evaluations.append(RuleEvaluation(rule_key, safe_url, page_url, resource_type, matched, response.status))
                if response.request.is_navigation_request():
                    report.rule_evaluations.append(RuleEvaluation("broken_link", safe_url, page_url, resource_type, response.status == 404, response.status))
                    report.rule_evaluations.append(RuleEvaluation("navigation_failure", safe_url, page_url, resource_type, False, response.status))
                report.rule_evaluations.append(RuleEvaluation("request_failure", safe_url, page_url, resource_type, False, response.status))
            expected = self.expected_statuses.get(safe_url)
            if expected is not None and response.status not in expected:
                report.observations.append(Observation(
                    "unexpected_response", safe_url,
                    page_url, None,
                    f"Expected HTTP {sorted(expected)}; observed {response.status}", response.status,
                    resource_type=resource_type,
                ))
            if expected is not None and page_url:
                report.rule_evaluations.append(RuleEvaluation("unexpected_response", safe_url, page_url, resource_type, response.status not in expected, response.status))
            if response.status >= 400:
                request = response.request
                report.observations.append(Observation(
                    "http_response", safe_url,
                    page_url, None,
                    f"HTTP {response.status} on {request.resource_type}", response.status,
                    response.status == 404 and request.is_navigation_request(),
                    resource_type=resource_type,
                ))

        def on_request_failed(request: Request) -> None:
            if request.url not in blocked:
                safe_url = clean_url(request.url)
                page_url = safe_url if request.is_navigation_request() else self._safe_url(current_page.url) if current_page else None
                if page_url:
                    report.rule_evaluations.append(RuleEvaluation("request_failure", safe_url, page_url, request.resource_type, True))
                report.observations.append(Observation(
                    "request_failure", safe_url,
                    page_url, None,
                    f"{request.resource_type} request failed",
                    resource_type=request.resource_type,
                ))

        def on_page_error(error: Exception) -> None:
            if len(report.console_events) < 100:
                report.console_events.append({"level": "pageerror", "page": self._safe_url(current_page.url) if current_page else None,
                                              "message": "JavaScript exception observed; raw message withheld"})
            if "TestLab blocked" in str(error):
                report.observations.append(Observation(
                    "scope_blocked", self._safe_url(current_page.url) if current_page else None,
                    self._safe_url(current_page.url) if current_page else None, None,
                    "Browser API blocked by scope policy",
                ))
                return
            # Exception messages can contain secrets; keep only the error class and page.
            report.observations.append(Observation(
                "javascript_error", clean_url(current_page.url) if current_page else None,
                clean_url(current_page.url) if current_page else None, None,
                f"JavaScript {type(error).__name__} observed",
            ))

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True,
                executable_path=self.chromium_executable,
                args=["--no-proxy-server", "--dns-prefetch-disable", *([f"--host-resolver-rules={self.policy.chromium_rules()}"] if self.policy.chromium_rules() else [])],
            )
            context = None
            try:
                context = await browser.new_context(service_workers="block", accept_downloads=False,
                                                    viewport={"width": 1280, "height": 720})
                await context.add_init_script("""(() => {
                    const deny = name => Object.defineProperty(window, name, { configurable: false, value: class {
                        constructor() { throw new DOMException('TestLab blocked ' + name, 'SecurityError'); }
                    }});
                    for (const name of ['Worker', 'SharedWorker', 'WebSocket', 'RTCPeerConnection', 'webkitRTCPeerConnection', 'WebTransport']) deny(name);
                    Object.defineProperty(window, 'open', { configurable: false, value: () => null });
                    document.addEventListener('click', event => {
                        const element = event.target?.closest?.('a[target],button[formtarget]');
                        const target = element?.getAttribute('target') || element?.getAttribute('formtarget');
                        if (target && target !== '_self') event.preventDefault();
                    }, true);
                })();""")
                context.set_default_timeout(self.limits.page_timeout_ms)
                context.set_default_navigation_timeout(self.limits.page_timeout_ms)
                page = await context.new_page()
                current_page = page
                cdp = await context.new_cdp_session(page)
                await cdp.send("Network.enable")
                await cdp.send("Network.setBlockedURLs", {"urls": ["ws://*", "wss://*"]})
                cdp.on("Fetch.requestPaused", lambda event: asyncio.create_task(guard(cdp, event)))
                await cdp.send("Fetch.enable", {"patterns": [{"urlPattern": "*", "requestStage": "Request"}]})
                page.on("response", on_response)
                page.on("requestfailed", on_request_failed)
                page.on("pageerror", on_page_error)
                page.on("console", lambda message: report.console_events.append({
                    "level": message.type, "page": self._safe_url(page.url),
                    "message": "Console message withheld to protect sensitive data",
                }) if message.type in {"error", "warning"} and len(report.console_events) < 100 else None)

                if self.login:
                    if not await self._navigate(page, self.login.url, 0, report):
                        report.stop_reason = report.stop_reason or "login_navigation_failed"
                        return
                    try:
                        await page.locator(self.login.username_selector).fill(self.login.username)
                        self._step(report, "fill_username", page.url, "username field", "completed")
                        await page.locator(self.login.password_selector).fill(self.login.password)
                        self._step(report, "fill_password", page.url, "password field", "completed")
                        form = await page.locator(self.login.submit_selector).evaluate("el => ({ action: el.form?.action || null, method: el.form?.method || null, target: el.form?.target || null })")
                        if not form["action"] or form["method"].lower() != "post" or form["target"] not in (None, "", "_self"):
                            raise ValueError("Login requires a POST form")
                        login_post_url = self.policy.check(form["action"], navigation=True)
                        await page.locator(self.login.submit_selector).click()
                        self._step(report, "submit_login", page.url, "login form", "completed")
                        if self.login.success_selector:
                            await page.locator(self.login.success_selector).wait_for(state="visible")
                        elif self.login.success_url_pattern:
                            await page.wait_for_function("pattern => location.href.includes(pattern)", arg=self.login.success_url_pattern)
                        else:
                            raise ValueError("Login requires a success condition")
                        self._step(report, "verify_login", page.url, None, "success")
                    except (PlaywrightError, ValueError):
                        self._step(report, "verify_login", page.url, None, "failed")
                        report.observations.append(Observation("authentication_failure", clean_url(page.url), clean_url(page.url), None, "Configured login success condition was not met"))
                        report.stop_reason = "authentication_failed"
                        return
                    finally:
                        login_post_url = None

                queue: deque[tuple[str, int]] = deque([(self.base_url, 0), *((url, 0) for url in self.scenario_urls)])
                seen: set[str] = set()
                while queue and len(report.pages) < self.limits.max_pages and report.stop_reason is None:
                    url, depth = queue.popleft()
                    safe = self.policy.check(url, navigation=True)
                    if safe in seen:
                        continue
                    seen.add(safe)
                    if not await self._navigate(page, url, depth, report):
                        continue
                    if depth >= self.limits.max_depth:
                        continue
                    for element in report.pages[-1].elements:
                        if element.kind != "a" or not element.href:
                            continue
                        try:
                            candidate = self.policy.check(element.href, navigation=True)
                        except ScopeError:
                            continue
                        if candidate not in seen and all(candidate != item[0] for item in queue):
                            queue.append((candidate, depth + 1))
                if report.stop_reason is None:
                    report.completed = bool(report.pages)
                    if not report.pages:
                        report.stop_reason = "no_pages"
            finally:
                if context is not None:
                    await context.close()
                await browser.close()

    async def _navigate(self, page, url: str, depth: int, report: RunReport) -> bool:
        start = time.monotonic()
        safe = clean_url(url)
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=self.limits.page_timeout_ms)
            elapsed = int((time.monotonic() - start) * 1000)
            if response is None:
                raise PlaywrightError("Navigation returned no response")
            actual = self.policy.check(page.url, navigation=True)
            shot, diagnostic = await capture_page(page, timeout_ms=self.limits.page_timeout_ms)
            captured_url = self.policy.check(page.url, navigation=True)
            if captured_url != actual:
                report.screenshot_diagnostics[actual] = {
                    "status": "unavailable", "reason": "page_changed_during_capture",
                    "captured_at": diagnostic["captured_at"],
                }
                actual = captured_url
            report.screenshot_diagnostics[actual] = diagnostic
            if shot is not None:
                report.screenshots[actual] = shot
            record = await inspect_page(page, url=actual, depth=depth, navigation_ms=elapsed)
            report.pages.append(record)
            self._step(report, "navigate", actual, safe, f"HTTP {response.status}", record.title, record.module)
            report.rule_evaluations.append(RuleEvaluation("timeout", actual, actual, "document", False, response.status))
            report.rule_evaluations.append(RuleEvaluation(
                "javascript_error", actual, actual, None,
                any(item.kind == "javascript_error" and item.url == actual for item in report.observations),
            ))
            return True
        except (PlaywrightError, ScopeError):
            report.screenshot_diagnostics.setdefault(safe, {
                "status": "unavailable", "reason": "navigation_failed",
                "captured_at": datetime.now(timezone.utc).isoformat(),
            })
            self._step(report, "navigate", safe, safe, "failed")
            report.rule_evaluations.append(RuleEvaluation("navigation_failure", safe, safe, "document", True))
            report.observations.append(Observation("navigation_failure", safe, safe, None,
                                                   "Navigation did not complete", resource_type="document"))
            return False
        except asyncio.CancelledError:
            report.screenshot_diagnostics.setdefault(safe, {
                "status": "unavailable", "reason": "navigation_interrupted",
                "captured_at": datetime.now(timezone.utc).isoformat(),
            })
            raise

    @staticmethod
    def _safe_url(url: str) -> str | None:
        try:
            return clean_url(url) if url.startswith(("http://", "https://")) else None
        except ValueError:
            return None

    @staticmethod
    def _step(
        report: RunReport, action: str, page: str, element: str | None, result: str,
        page_name: str | None = None, module: str | None = None,
    ) -> None:
        report.steps.append(StepRecord(
            order=len(report.steps) + 1, action=action,
            page=page_name or clean_url(page), module=module,
            element=element, result=result,
            page_url=clean_url(page),
        ))
