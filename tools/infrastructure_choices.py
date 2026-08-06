#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import production_readiness_contracts

REQUIRED_SECTIONS: dict[str, tuple[str, ...]] = {
    "domain_tls": ("domain", "tls_provider", "certificate_owner", "renewal_proof"),
    "identity_proxy": (
        "provider",
        "signature_owner",
        "hmac_secret_source",
        "signed_headers",
    ),
    "model_service": (
        "provider",
        "base_url",
        "model",
        "capacity_owner",
        "verification_command",
    ),
    "github_access": ("mode", "organization", "repository_policy", "secret_source"),
    "database": (
        "mode",
        "connection_secret",
        "backup_policy",
        "restore_drill_frequency",
    ),
    "object_storage": (
        "provider",
        "bucket",
        "region",
        "encryption",
        "retention_policy",
    ),
    "kubernetes": (
        "enabled",
        "registry",
        "namespace",
        "ingress_class",
        "storage_class",
        "worker_replicas",
    ),
    "backup_restore": (
        "schedule_owner",
        "backup_timer",
        "last_restore_drill",
        "restore_drill_evidence",
    ),
    "notification": ("alert_channel", "oncall_owner", "escalation_policy"),
}

PLACEHOLDER_TOKENS = {
    "",
    "ai-enterprise.example.com",
    "example-org",
    "server-secret-manager-path",
    "link-or-command-that-proves-renewal-is-automated",
    "link-to-runbook-output-or-ticket",
    "link-to-policy",
    "YYYY-MM-DD",
}


def load_choices(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def verify(path: Path, *, allow_placeholders: bool = False) -> dict[str, Any]:
    findings: list[str] = []
    if not path.exists():
        return {
            "status": "needs_setup",
            "conformant": False,
            "path": str(path),
            "summary": "Infrastructure choices file is missing.",
            "findings": [
                (
                    f"Create {path} from "
                    "docs/enterprise/real-world-infrastructure-decisions.template.json."
                )
            ],
            "next_action": (
                "Copy the template, fill real provider values, then run "
                "make infrastructure-choices-verify."
            ),
        }
    try:
        payload = load_choices(path)
    except json.JSONDecodeError as exc:
        return {
            "status": "needs_setup",
            "conformant": False,
            "path": str(path),
            "summary": "Infrastructure choices file is not valid JSON.",
            "findings": [f"JSON error: {exc}"],
            "next_action": "Fix JSON syntax and run the verifier again.",
        }
    schema_findings = production_readiness_contracts.validate_infrastructure_decisions(payload)
    findings.extend(f"schema: {finding}" for finding in schema_findings)
    for section, fields in REQUIRED_SECTIONS.items():
        value = payload.get(section)
        if not isinstance(value, dict):
            findings.append(f"{section}: section is missing")
            continue
        for field in fields:
            if field not in value:
                findings.append(f"{section}.{field}: field is missing")
                continue
            field_value = value[field]
            if not allow_placeholders and _contains_placeholder(field_value):
                findings.append(f"{section}.{field}: replace placeholder with real value")
    if "identity_proxy" in payload:
        headers = set(payload["identity_proxy"].get("signed_headers", []))
        required_headers = {
            "X-Actor-ID",
            "X-Actor-Type",
            "X-Actor-Role",
            "X-Proxy-Timestamp",
            "X-Proxy-Signature",
        }
        missing_headers = sorted(required_headers - headers)
        if missing_headers:
            findings.append(
                "identity_proxy.signed_headers: missing "
                + ", ".join(missing_headers)
            )
    return {
        "status": "ready" if not findings else "needs_setup",
        "conformant": not findings,
        "path": str(path),
        "summary": (
            "Real infrastructure choices are recorded and ready for deployment gates."
            if not findings
            else "Infrastructure choices file does not match the published schema."
            if schema_findings
            else f"{len(findings)} infrastructure choice item(s) need real values."
        ),
        "sections": sorted(REQUIRED_SECTIONS),
        "findings": findings,
        "next_action": (
            "Use these choices to generate .env.server and server/provider configuration."
            if not findings
            else (
                "Fix the file shape against "
                "schemas/production-readiness/infrastructure-decisions.schema.json."
            )
            if schema_findings
            else (
                "Replace placeholders with real domain, identity, model, GitHub, "
                "database, storage, Kubernetes, backup, and alert choices."
            )
        ),
    }


def _contains_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped in PLACEHOLDER_TOKENS or "example.com" in stripped
    if isinstance(value, list):
        return any(_contains_placeholder(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_placeholder(item) for item in value.values())
    return value is None


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify real infrastructure choices.")
    parser.add_argument(
        "--choices",
        default="docs/enterprise/real-world-infrastructure-decisions.json",
    )
    parser.add_argument("--allow-placeholders", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = verify(Path(args.choices), allow_placeholders=args.allow_placeholders)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["conformant"]:
        print(report["summary"])
    else:
        for finding in report["findings"]:
            print(finding)
    return 0 if report["conformant"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
