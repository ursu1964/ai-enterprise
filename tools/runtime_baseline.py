#!/usr/bin/env python3
"""Capture a hashed, read-only local runtime baseline before remediation."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
PROBLEM_STATUSES = {"failed", "dead_letter", "abandoned"}


class BaselineError(RuntimeError):
    """Raised when trustworthy local baseline evidence cannot be captured."""


def _canonical_hash(document: dict[str, Any]) -> str:
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise BaselineError("Git provenance is unavailable") from exc


def _request(url: str, *, headers: dict[str, str] | None = None) -> tuple[bytes, Any]:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
            return response.read(), response.headers
    except (urllib.error.URLError, TimeoutError) as exc:
        raise BaselineError(f"Runtime evidence request failed: {url}") from exc


def _json(url: str, *, headers: dict[str, str] | None = None) -> tuple[dict[str, Any], Any]:
    raw, response_headers = _request(url, headers=headers)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BaselineError(f"Runtime evidence was not JSON: {url}") from exc
    if not isinstance(payload, dict):
        raise BaselineError(f"Runtime evidence must be an object: {url}")
    return payload, response_headers


def _metric_snapshot(raw: str) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for line in raw.splitlines():
        if not line or line.startswith("#"):
            continue
        name, _, value = line.partition(" ")
        if not name.startswith("ai_enterprise_http_route_") or not value:
            continue
        try:
            metrics[name.split("{", 1)[0]] = float(value)
        except ValueError:
            continue
    return dict(sorted(metrics.items()))


def build_baseline(root: Path, base_url: str) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in LOCAL_HOSTS:
        raise BaselineError("Runtime baseline is restricted to a loopback HTTP dashboard")
    base_url = base_url.rstrip("/")
    context, _ = _json(f"{base_url}/dashboard/context")
    actor_headers = context.get("actor_headers")
    if not isinstance(actor_headers, dict) or not actor_headers:
        raise BaselineError("Local dashboard context did not provide actor headers")
    headers = {str(name): str(value) for name, value in actor_headers.items()}
    manager_url = f"{base_url}/api/v1/query/dashboard-manager?compact=true&limit=100"
    organization_id = context.get("organization_id")
    if organization_id:
        manager_url += "&organization_id=" + urllib.parse.quote(str(organization_id))
    manager_raw, manager_headers = _request(manager_url, headers=headers)
    try:
        manager = json.loads(manager_raw)
    except json.JSONDecodeError as exc:
        raise BaselineError("Dashboard manager evidence was not JSON") from exc
    jobs = manager.get("records", {}).get("jobs", [])
    problems = [job for job in jobs if job.get("status") in PROBLEM_STATUSES]
    failure_patterns: dict[tuple[str, str], dict[str, Any]] = {}
    for job in problems:
        key = (str(job.get("last_failure_class") or "unknown"), str(job.get("last_error") or ""))
        pattern = failure_patterns.setdefault(
            key,
            {
                "failure_class": key[0],
                "diagnostic": key[1],
                "count": 0,
                "job_ids": [],
                "job_types": [],
            },
        )
        pattern["count"] += 1
        pattern["job_ids"].append(str(job.get("id")))
        job_type = str(job.get("job_type") or "unknown")
        if job_type not in pattern["job_types"]:
            pattern["job_types"].append(job_type)
    metrics_raw, _ = _request(f"{base_url}/metrics")
    document: dict[str, Any] = {
        "schema_version": "1.0",
        "captured_at": datetime.now(UTC).isoformat(),
        "proof_level": "local_demo",
        "source": {"base_url": base_url, "read_only": True},
        "git": {
            "commit": _git(root, "rev-parse", "HEAD"),
            "tree": _git(root, "rev-parse", "HEAD^{tree}"),
            "dirty": bool(_git(root, "status", "--porcelain")),
        },
        "manager": {
            "headline": manager.get("headline"),
            "totals": manager.get("totals"),
            "runtime": manager.get("telemetry_summary", {}).get("runtime"),
            "response_bytes": len(manager_raw),
            "server_timing": manager_headers.get("Server-Timing"),
        },
        "failure_patterns": sorted(
            failure_patterns.values(),
            key=lambda item: (-item["count"], item["failure_class"], item["diagnostic"]),
        ),
        "route_metrics": _metric_snapshot(metrics_raw.decode("utf-8")),
    }
    document["evidence_hash"] = _canonical_hash(document)
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", default="artifacts/runtime-baseline.json")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    try:
        document = build_baseline(root, args.base_url)
    except BaselineError as exc:
        print(json.dumps({"captured": False, "error": str(exc)}))
        return 1
    target = Path(args.output)
    if not target.is_absolute():
        target = root / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"captured": True, "output": str(target), **document["git"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
