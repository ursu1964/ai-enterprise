#!/usr/bin/env python3
"""Verify the live operator dashboard through a real Chromium browser."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

TAB_JOURNEYS = {
    "overview": "Living Enterprise Pulse",
    "execution": "Project Execution Control",
    "factory": "Manifesto Launcher",
    "problems": "Guided Recovery Center",
    "metrics": "Business Telemetry",
    "projects": "Project Intelligence Graph",
    "graph": "Blueprint Graph Hub",
}
REDUNDANT_DASHBOARD_REQUESTS = {
    "/api/v1/query/operating-picture",
    "/dashboard/telemetry-summary",
    "/api/v1/projects",
    "/api/v1/operator/jobs",
    "/api/v1/operator/jobs/worker-instances",
}


def _require_playwright() -> Any:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Run `cd apps/api && uv sync --group dev`, then "
            "`.venv/bin/playwright install chromium`."
        ) from exc
    return sync_playwright


def _visible_panel_text(page: Any, view: str) -> list[str]:
    return page.locator(f"#{view} article").all_inner_texts()


def _assert_populated_view(page: Any, view: str, expected_heading: str) -> dict[str, Any]:
    panel = page.locator(f"#{view}")
    panel.wait_for(state="visible")
    panel.get_by_text(expected_heading, exact=True).wait_for(state="visible")
    blank_panels = [text for text in _visible_panel_text(page, view) if not text.strip()]
    if blank_panels:
        raise RuntimeError(f"{view} contains {len(blank_panels)} blank operator panels")
    return {"view": view, "heading": expected_heading, "panels": panel.locator("article").count()}


def run_browser_verify(
    *,
    base_url: str,
    headless: bool = True,
    timeout_ms: int = 15_000,
    screenshot_dir: Path | None = None,
) -> dict[str, Any]:
    sync_playwright = _require_playwright()
    base_url = base_url.rstrip("/")
    console_errors: list[str] = []
    dashboard_requests: list[str] = []
    dashboard_request_urls: list[str] = []
    checks: list[dict[str, Any]] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.set_default_timeout(timeout_ms)
        page.on(
            "console",
            lambda message: (
                console_errors.append(message.text) if message.type == "error" else None
            ),
        )
        page.on(
            "request",
            lambda request: (
                dashboard_requests.append(urlparse(request.url).path),
                dashboard_request_urls.append(request.url),
            ),
        )
        try:
            response = page.goto(f"{base_url}/dashboard", wait_until="networkidle")
            if response is None or response.status != 200:
                raise RuntimeError("dashboard did not return HTTP 200")
            page.get_by_role("heading", name="AI Enterprise Command Center").wait_for()
            page.locator("#businessBoard .business-card").first.wait_for()

            for view, heading in TAB_JOURNEYS.items():
                page.locator(f'button.tab[data-view="{view}"]').click()
                checks.append(_assert_populated_view(page, view, heading))

            page.locator('button.tab[data-view="factory"]').click()
            page.locator("#previewMockFactory").click()
            page.locator("#launchContract").get_by_text("Preview", exact=False).first.wait_for()
            checks.append({"view": "factory-preview", "status": "rendered"})

            page.locator('button.tab[data-view="projects"]').click()
            project_options = page.locator("#projectSelect option").count()
            if project_options:
                page.locator("#loadProject").click()
                page.locator("#projectGraph .cards").wait_for()
            checks.append(
                {
                    "view": "project-inspector",
                    "projects": project_options,
                    "status": "rendered" if project_options else "empty-with-guidance",
                }
            )

            redundant = sorted(REDUNDANT_DASHBOARD_REQUESTS & set(dashboard_requests))
            if redundant:
                raise RuntimeError(
                    "dashboard refresh made redundant read-model requests: " + ", ".join(redundant)
                )
            manager_requests = dashboard_requests.count("/api/v1/query/dashboard-manager")
            if manager_requests != 1:
                raise RuntimeError(
                    f"dashboard refresh expected one manager request, observed {manager_requests}"
                )
            context_requests = dashboard_requests.count("/dashboard/context")
            if context_requests != 1:
                raise RuntimeError(
                    f"dashboard refresh expected one context request, observed {context_requests}"
                )
            manager_url = next(
                url
                for url in dashboard_request_urls
                if urlparse(url).path == "/api/v1/query/dashboard-manager"
            )
            if parse_qs(urlparse(manager_url).query).get("compact") != ["true"]:
                raise RuntimeError("dashboard manager request did not use compact mode")
            checks.append(
                {
                    "view": "refresh-performance",
                    "manager_requests": manager_requests,
                    "context_requests": context_requests,
                    "compact": True,
                    "redundant_requests": redundant,
                }
            )
            page.evaluate("Promise.all([refresh(), refresh(), refresh()])")
            manager_after_concurrent_refresh = dashboard_requests.count(
                "/api/v1/query/dashboard-manager"
            )
            if manager_after_concurrent_refresh != manager_requests + 1:
                raise RuntimeError(
                    "concurrent refresh calls were not coalesced into one manager request"
                )
            if dashboard_requests.count("/dashboard/context") != context_requests:
                raise RuntimeError("stable dashboard context was fetched again during refresh")
            checks.append(
                {
                    "view": "refresh-coalescing",
                    "requested_refreshes": 3,
                    "manager_requests": manager_after_concurrent_refresh - manager_requests,
                }
            )
            recovery_groups = page.evaluate(
                """groupedRecoveryItems([
                  {job_id: "job-1", status: "dead_letter", failure_class: "retry_exhausted", explanation: "Retry exhausted", likely_cause: "Repeated failure", next_action: "Review", raw_diagnostic: "proof-a"},
                  {job_id: "job-2", status: "dead_letter", failure_class: "retry_exhausted", explanation: "Retry exhausted", likely_cause: "Repeated failure", next_action: "Review", raw_diagnostic: "proof-b"},
                  {job_id: "job-3", status: "dead_letter", failure_class: "missing_artifact", explanation: "Artifact missing", likely_cause: "Result contract", next_action: "Repair", raw_diagnostic: "proof-c"}
                ])"""
            )
            if len(recovery_groups) != 2 or recovery_groups[0]["occurrence_count"] != 2:
                raise RuntimeError("repeated recovery items were not grouped by failure pattern")
            if recovery_groups[0]["job_ids"] != ["job-1", "job-2"]:
                raise RuntimeError("grouped recovery proof did not preserve affected job IDs")
            checks.append(
                {
                    "view": "recovery-pattern-grouping",
                    "source_jobs": 3,
                    "rendered_patterns": len(recovery_groups),
                    "largest_pattern": recovery_groups[0]["occurrence_count"],
                }
            )

            for path, heading in (
                ("/dashboard/demo", "AI Enterprise Demo Story"),
                ("/dashboard/documentation-hub", "Documentation Hub"),
            ):
                response = page.goto(f"{base_url}{path}", wait_until="networkidle")
                if response is None or response.status != 200:
                    raise RuntimeError(f"{path} did not return HTTP 200")
                page.get_by_role("heading", name=heading, exact=True).wait_for()
                checks.append({"path": path, "heading": heading, "status": 200})

            response = page.goto(f"{base_url}/client-portal", wait_until="networkidle")
            if response is None or response.status != 200:
                raise RuntimeError("/client-portal did not return HTTP 200")
            page.get_by_role("heading", name="Universal Experience Runtime", exact=True).wait_for()
            page.get_by_role("button", name="Bootstrap R10 Workspace", exact=True).wait_for()
            page.locator("#roleSelect").select_option("operator")
            page.locator("#deviceSelect").select_option("mobile")
            page.locator("#experienceRecords").wait_for(state="visible")
            page.set_viewport_size({"width": 390, "height": 900})
            runtime_box = page.locator(".runtime-grid").bounding_box()
            if runtime_box is None or runtime_box["width"] > 390:
                raise RuntimeError("R10 client runtime is not responsive at mobile width")
            checks.append(
                {
                    "path": "/client-portal",
                    "heading": "Universal Experience Runtime",
                    "r10_runtime": True,
                    "mobile_width": 390,
                }
            )
            page.set_viewport_size({"width": 1440, "height": 1000})

            response = page.goto(f"{base_url}/dashboard/graphify", wait_until="domcontentloaded")
            if response is None or response.status != 200:
                raise RuntimeError("/dashboard/graphify did not return HTTP 200")
            checks.append({"path": "/dashboard/graphify", "status": 200})

            if console_errors:
                raise RuntimeError(f"browser console errors: {' | '.join(console_errors)}")
        except Exception:
            if screenshot_dir is not None:
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                page.screenshot(
                    path=str(screenshot_dir / "dashboard-browser-failure.png"), full_page=True
                )
            raise
        finally:
            browser.close()

    return {"conformant": True, "base_url": base_url, "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--timeout-ms", type=int, default=15_000)
    parser.add_argument("--screenshot-dir", type=Path, default=Path("artifacts/browser"))
    args = parser.parse_args()
    try:
        report = run_browser_verify(
            base_url=args.base_url,
            headless=not args.headed,
            timeout_ms=args.timeout_ms,
            screenshot_dir=args.screenshot_dir,
        )
    except Exception as exc:  # noqa: BLE001 - CLI must provide one actionable failure.
        print(json.dumps({"conformant": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
