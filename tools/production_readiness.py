#!/usr/bin/env python3
"""Validate auditable evidence required to call a deployment production ready."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import infrastructure_choices
import production_readiness_contracts

REQUIRED_PROOF: dict[str, tuple[str, ...]] = {
    "tls": ("endpoint", "certificate_expires_at"),
    "proxy_identity": ("provider", "signed_headers_verified"),
    "server_secrets": ("secret_manager", "rotation_due_at"),
    "backup_restore": ("restored_database", "restore_completed_at"),
    "object_storage": ("bucket", "read_write_delete_verified"),
    "model_endpoint": ("endpoint", "model"),
    "prometheus": ("endpoint", "scrape_target"),
    "grafana": ("endpoint", "dashboard"),
    "alert_routing": ("channel", "test_alert_id"),
    "production_owners": (
        "product_owner",
        "technical_owner",
        "operations_owner",
        "security_owner",
    ),
    "pilot_results": (
        "pilot_project",
        "manifest_to_project_passed",
        "feedback_reviewed",
    ),
    "infrastructure_credentials": (
        "credential_inventory",
        "secret_manager",
        "raw_secret_values_absent",
    ),
    "production_run_artifacts": (
        "release_artifact",
        "gate_evidence",
        "deployment_audit_id",
    ),
    "r16_graph_backend": (
        "backend",
        "deployment_evidence",
        "connectivity_evidence",
        "credential_reference",
        "restore_or_export_evidence",
        "owner_approval",
    ),
}


def _datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def verify(
    root: Path,
    evidence_file: Path,
    choices_file: Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    now = now or datetime.now(UTC)
    evidence_path = evidence_file if evidence_file.is_absolute() else root / evidence_file
    choices_path = choices_file if choices_file.is_absolute() else root / choices_file
    findings: list[str] = []

    choices = infrastructure_choices.verify(choices_path)
    if not choices["conformant"]:
        findings.append("infrastructure_choices: real reviewed provider decisions are required")

    try:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        payload = {}
        findings.append(f"evidence_bundle: create {evidence_path}")
    except json.JSONDecodeError as exc:
        payload = {}
        findings.append(f"evidence_bundle: invalid JSON: {exc}")
    if payload:
        schema_findings = production_readiness_contracts.validate_production_evidence(payload)
        findings.extend(f"evidence_schema: {finding}" for finding in schema_findings)

    environment = payload.get("environment")
    if environment != "production":
        findings.append("environment: must be production")
    reviewed_by = payload.get("reviewed_by")
    if not isinstance(reviewed_by, str) or not reviewed_by.strip():
        findings.append("reviewed_by: production owner is required")

    proof = payload.get("proof", {})
    if not isinstance(proof, dict):
        proof = {}
        findings.append("proof: object is required")
    checks: list[dict[str, Any]] = []
    for name, fields in REQUIRED_PROOF.items():
        item = proof.get(name)
        item_findings: list[str] = []
        if not isinstance(item, dict):
            item = {}
            item_findings.append("proof record is missing")
        if item.get("status") != "passed":
            item_findings.append("status must be passed")
        checked_at = _datetime(item.get("checked_at"))
        if checked_at is None:
            item_findings.append("checked_at must be an ISO-8601 timestamp")
        elif checked_at > now:
            item_findings.append("checked_at cannot be in the future")
        valid_until = _datetime(item.get("valid_until"))
        if valid_until is None:
            item_findings.append("valid_until must be an ISO-8601 timestamp")
        elif valid_until <= now:
            item_findings.append("evidence has expired")
        evidence = item.get("evidence")
        if not isinstance(evidence, str) or not evidence.strip():
            item_findings.append("evidence path, URL, ticket, or command output is required")
        for field in fields:
            value = item.get(field)
            if value is not True and (not isinstance(value, str) or not value.strip()):
                item_findings.append(f"{field} is required")
            if _contains_inline_secret_value(value):
                item_findings.append(f"{field} must be a reference, not a secret value")
        findings.extend(f"{name}: {finding}" for finding in item_findings)
        checks.append(
            {
                "name": name,
                "status": "passed" if not item_findings else "blocked",
                "checked_at": item.get("checked_at"),
                "valid_until": item.get("valid_until"),
                "evidence": item.get("evidence"),
                "findings": item_findings,
            }
        )

    ready = not findings
    return {
        "schema_version": "1.0",
        "status": "ready" if ready else "blocked",
        "production_allowed": ready,
        "environment": environment,
        "reviewed_by": reviewed_by,
        "evidence_file": str(evidence_path),
        "choices": choices,
        "checks": checks,
        "findings": findings,
        "next_action": (
            "Archive this report with the production release artifact."
            if ready
            else "Complete every blocked proof and rerun make production-readiness."
        ),
    }


def _contains_inline_secret_value(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in {"secret", "password", "token", "api_key", "private_key"}:
                return True
            if _contains_inline_secret_value(item):
                return True
    if isinstance(value, list):
        return any(_contains_inline_secret_value(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return any(marker in lowered for marker in ("password=", "token=", "secret="))
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("docs/enterprise/production-readiness-evidence.json"),
    )
    parser.add_argument(
        "--choices",
        type=Path,
        default=Path("docs/enterprise/real-world-infrastructure-decisions.json"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(args.root, args.evidence, args.choices)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        target = args.output if args.output.is_absolute() else args.root / args.output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["production_allowed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
