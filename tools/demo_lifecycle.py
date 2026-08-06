#!/usr/bin/env python3
"""Preview or execute the local mock portfolio without erasing failure evidence."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import tempfile
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

CANONICAL_PORTFOLIO = (
    (
        "AI Enterprise Product Factory Demo",
        "/home/user/projects/mock-enterprise/ai-enterprise-product-factory",
    ),
    (
        "ISO Certification Consulting Module Demo",
        "/home/user/projects/mock-enterprise/iso-certification-consulting-module",
    ),
    (
        "Application Verification Debug Module Demo",
        "/home/user/projects/mock-enterprise/application-verification-debug-module",
    ),
    (
        "Enterprise Blueprint Catalog Demo",
        "/home/user/projects/mock-enterprise/enterprise-blueprint-catalog",
    ),
)
PROBLEM_JOB_STATUSES = frozenset({"failed", "dead_letter", "abandoned"})
UNHEALTHY_WORKFLOW_STATES = frozenset({"failed", "manual_intervention"})
UNHEALTHY_PROJECT_STATUSES = frozenset(
    {
        "requirements_failed",
        "requirements_rejected",
        "architecture_failed",
        "architecture_rejected",
        "work_package_failed",
        "execution_failed",
        "integration_failed",
    }
)


class DemoLifecycleError(RuntimeError):
    """Raised when the lifecycle gate refuses to start the demo."""


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def _is_loopback(base_url: str) -> bool:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return False
    if parsed.hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(parsed.hostname or "").is_loopback
    except ValueError:
        return False


def _request_json(
    base_url: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    timeout: float = 10,
) -> dict[str, Any] | list[dict[str, Any]]:
    data = b"{}" if method == "POST" else None
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise DemoLifecycleError(f"{method} {path} returned {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise DemoLifecycleError(f"{method} {path} failed: {exc}") from exc
    if not isinstance(payload, (dict, list)):
        raise DemoLifecycleError(f"{method} {path} returned an invalid JSON document")
    return payload


def _require_object(value: object, source: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DemoLifecycleError(f"{source} must return a JSON object")
    return value


def _validate_portfolio(preview: dict[str, Any]) -> list[dict[str, Any]]:
    raw_projects = preview.get("projects")
    if not isinstance(raw_projects, list) or not all(
        isinstance(item, dict) for item in raw_projects
    ):
        raise DemoLifecycleError("Mock-factory preview did not return a project list")
    projects: list[dict[str, Any]] = raw_projects
    actual = {(item.get("name"), item.get("repository_path")) for item in projects}
    expected = set(CANONICAL_PORTFOLIO)
    if actual != expected or len(projects) != len(expected):
        missing = sorted(expected - actual)
        extra = sorted(actual - expected, key=str)
        raise DemoLifecycleError(
            f"Mock portfolio differs from the canonical definition; missing={missing}, extra={extra}"
        )
    blocked = [item["name"] for item in projects if item.get("ready") is not True]
    if blocked or preview.get("status") != "ready":
        raise DemoLifecycleError(f"Mock-factory preview is not ready: {blocked}")
    return projects


def _unresolved_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        job
        for job in jobs
        if job.get("status") in PROBLEM_JOB_STATUSES
        and not (
            isinstance(job.get("operator_resolution"), dict)
            and job["operator_resolution"].get("state") == "acknowledged"
        )
    ]


def _unhealthy_canonical_projects(
    manager: dict[str, Any], canonical_names: set[str]
) -> list[dict[str, Any]]:
    raw_projects = manager.get("projects")
    if not isinstance(raw_projects, list):
        raise DemoLifecycleError("Dashboard manager did not return project summaries")
    by_name = {item.get("name"): item for item in raw_projects if isinstance(item, dict)}
    unhealthy: list[dict[str, Any]] = []
    for name in sorted(canonical_names):
        project = by_name.get(name)
        if project is None:
            continue  # A project which preview will create has no stale workflow to inspect.
        workflow = project.get("workflow")
        workflow_state = workflow.get("state") if isinstance(workflow, dict) else None
        tasks = project.get("tasks")
        problem_tasks = tasks.get("problems", 0) if isinstance(tasks, dict) else 0
        status = project.get("status")
        if (
            workflow_state in UNHEALTHY_WORKFLOW_STATES
            or status in UNHEALTHY_PROJECT_STATUSES
            or isinstance(status, str)
            and status.endswith(("_failed", "_rejected"))
            or isinstance(problem_tasks, int)
            and problem_tasks > 0
        ):
            unhealthy.append(
                {
                    "project_id": str(project.get("id")),
                    "name": name,
                    "project_status": status,
                    "workflow_state": workflow_state,
                    "problem_tasks": problem_tasks,
                }
            )
    return unhealthy


def _safe_job_evidence(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(job.get("id")),
            "project_id": str(job.get("project_id")),
            "job_type": job.get("job_type"),
            "status": job.get("status"),
            "failure_class": job.get("last_failure_class"),
        }
        for job in jobs
    ]


def _write_evidence(document: dict[str, Any], output_dir: Path) -> Path:
    unsigned = dict(document)
    unsigned.pop("integrity_sha256", None)
    digest = hashlib.sha256(_canonical_json(unsigned)).hexdigest()
    document["integrity_sha256"] = digest
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = str(document["generated_at"]).replace(":", "").replace("+00:00", "Z")
    destination = output_dir / f"demo-lifecycle-{timestamp}-{digest[:12]}.json"
    descriptor, temporary_name = tempfile.mkstemp(prefix=".demo-lifecycle-", dir=output_dir)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2, sort_keys=True, default=str)
            handle.write("\n")
        os.replace(temporary_name, destination)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return destination


def run_lifecycle(
    *,
    base_url: str,
    execute: bool,
    output_dir: Path,
    timeout: float = 10,
) -> tuple[dict[str, Any], Path | None]:
    if not _is_loopback(base_url):
        raise DemoLifecycleError("Demo lifecycle is restricted to a loopback URL")

    context = _require_object(
        _request_json(base_url, "/dashboard/context", timeout=timeout),
        "Dashboard context",
    )
    authority = context.get("authority")
    if not isinstance(authority, dict) or authority.get("mode") != "local-dashboard-context":
        raise DemoLifecycleError("API did not provide local development authority")
    headers = context.get("actor_headers")
    if not isinstance(headers, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in headers.items()
    ):
        raise DemoLifecycleError("Dashboard context did not provide valid actor headers")

    preview = _require_object(
        _request_json(
            base_url,
            "/api/v1/project-formation/mock-factory/preview",
            headers=headers,
            timeout=timeout,
        ),
        "Mock-factory preview",
    )
    portfolio = _validate_portfolio(preview)
    manager = _require_object(
        _request_json(
            base_url,
            "/api/v1/query/dashboard-manager",
            headers=headers,
            timeout=timeout,
        ),
        "Dashboard manager",
    )
    raw_jobs = _request_json(
        base_url,
        "/api/v1/operator/jobs?limit=500",
        headers=headers,
        timeout=timeout,
    )
    if not isinstance(raw_jobs, list) or not all(isinstance(item, dict) for item in raw_jobs):
        raise DemoLifecycleError("Operator jobs endpoint did not return a job list")
    jobs: list[dict[str, Any]] = raw_jobs
    unresolved = _unresolved_jobs(jobs)
    unhealthy = _unhealthy_canonical_projects(
        manager, {name for name, _repository_path in CANONICAL_PORTFOLIO}
    )
    generated_at = datetime.now(UTC).isoformat()
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": generated_at,
        "mode": "execute" if execute else "preview",
        "base_url": base_url.rstrip("/"),
        "policy": {
            "non_destructive": True,
            "deletes_records": False,
            "acknowledges_jobs": False,
            "local_context_required": True,
        },
        "portfolio": [
            {
                "name": item["name"],
                "repository_path": item["repository_path"],
                "action": item.get("action"),
                "existing_project_id": item.get("existing_project_id"),
            }
            for item in portfolio
        ],
        "preflight": {
            "status": "blocked" if unresolved or unhealthy else "ready",
            "unresolved_jobs": _safe_job_evidence(unresolved),
            "unhealthy_canonical_projects": unhealthy,
        },
        "execution": None,
    }
    if unresolved or unhealthy:
        evidence_path = _write_evidence(report, output_dir)
        raise DemoLifecycleError(
            "Demo start blocked: resolve or explicitly review all reported failures first. "
            f"Evidence: {evidence_path}"
        )
    if not execute:
        return report, None

    result = _require_object(
        _request_json(
            base_url,
            "/api/v1/project-formation/mock-factory/start",
            headers=headers,
            method="POST",
            timeout=timeout,
        ),
        "Mock-factory start",
    )
    result_projects = result.get("projects")
    if not isinstance(result_projects, list):
        raise DemoLifecycleError("Mock-factory start did not return projects")
    actual_names = [item.get("name") for item in result_projects if isinstance(item, dict)]
    expected_names = {name for name, _repository_path in CANONICAL_PORTFOLIO}
    if (
        result.get("status") != "started"
        or result.get("failed_count") != 0
        or result.get("blocked_count") != 0
        or len(actual_names) != 4
        or set(actual_names) != expected_names
    ):
        report["execution"] = {"status": "invalid_or_partial", "response": result}
        evidence_path = _write_evidence(report, output_dir)
        raise DemoLifecycleError(
            f"Mock-factory execution was incomplete. Evidence: {evidence_path}"
        )
    report["execution"] = {"status": "started", "response": result}
    return report, _write_evidence(report, output_dir)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview the local demo lifecycle; use --execute only after preflight passes."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/demo-runs"))
    parser.add_argument("--timeout", type=float, default=10)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        report, evidence_path = run_lifecycle(
            base_url=args.base_url,
            execute=args.execute,
            output_dir=args.output_dir,
            timeout=args.timeout,
        )
    except DemoLifecycleError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    if evidence_path is not None:
        print(f"Evidence: {evidence_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
