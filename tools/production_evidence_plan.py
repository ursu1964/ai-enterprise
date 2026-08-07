"""Build the operational work plan for production readiness evidence.

This tool does not approve production and does not invent proof. It converts the
same fail-closed readiness rules used by ``production_readiness.py`` into a
deterministic collection plan for operators.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import infrastructure_choices
import jsonschema
import production_readiness

SCHEMA_ROOT = Path(__file__).resolve().parents[1] / "schemas" / "production-readiness"
PLAN_SCHEMA = "production-evidence-plan.schema.json"

OWNER_HINTS: dict[str, str] = {
    "tls": "platform owner",
    "proxy_identity": "security/platform owner",
    "server_secrets": "security/platform owner",
    "backup_restore": "platform operations owner",
    "object_storage": "platform owner",
    "model_endpoint": "AI platform owner",
    "prometheus": "observability owner",
    "grafana": "observability owner",
    "alert_routing": "on-call operations owner",
    "production_owners": "release owner",
    "pilot_results": "product owner and pilot stakeholders",
    "infrastructure_credentials": "security/platform owner",
    "production_run_artifacts": "release manager",
    "r16_graph_backend": "data platform and knowledge graph owners",
}

ACTION_HINTS: dict[str, str] = {
    "tls": "Run the TLS/certificate probe and archive the endpoint evidence.",
    "proxy_identity": "Verify trusted proxy signed headers with a real request trace.",
    "server_secrets": "Attach secret-manager and rotation proof references.",
    "backup_restore": "Run an isolated restore drill and archive the restore output.",
    "object_storage": "Run read/write/delete storage probes against the production bucket.",
    "model_endpoint": "Run the model endpoint verifier against the selected model.",
    "prometheus": "Capture production scrape-target evidence.",
    "grafana": "Archive the production dashboard URL or immutable snapshot.",
    "alert_routing": "Send a test alert and record the delivered alert/ticket ID.",
    "production_owners": "Record named product, technical, operations, and security owners.",
    "pilot_results": "Attach pilot project proof, Manifest-to-project pass, and reviewed feedback.",
    "infrastructure_credentials": "Attach credential inventory and secret-manager references only.",
    "production_run_artifacts": "Attach release artifact, gate evidence, and deployment audit ID.",
    "r16_graph_backend": (
        "Attach graph backend deployment, connectivity, credential reference, restore/export, "
        "and owner approval evidence for Neo4j/RDF/custom production operation."
    ),
}

VALIDATION_COMMANDS = (
    "rtk make infrastructure-choices-verify",
    "rtk make production-readiness-contracts",
    "rtk make production-readiness",
    "rtk make release-gate-evidence-release",
    "rtk make production-release-artifact",
)


def build_plan(
    root: Path,
    evidence_file: Path,
    choices_file: Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    evidence_path = evidence_file if evidence_file.is_absolute() else root / evidence_file
    choices_path = choices_file if choices_file.is_absolute() else root / choices_file
    now = now or datetime.now(UTC)

    evidence_payload = _read_json_object(evidence_path)
    proof = evidence_payload.get("proof", {}) if isinstance(evidence_payload, dict) else {}
    if not isinstance(proof, dict):
        proof = {}

    choices_payload = _read_json_object(choices_path)
    readiness = production_readiness.verify(
        root,
        evidence_file,
        choices_file,
        now=now,
    )
    choice_report = readiness["choices"]

    plan_without_hash: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "status": "ready" if readiness["production_allowed"] else "blocked",
        "production_allowed": readiness["production_allowed"],
        "evidence_file": str(evidence_path),
        "choices_file": str(choices_path),
        "proof_requirements": _proof_requirements(
            proof,
            readiness_findings=readiness["findings"],
        ),
        "infrastructure_choice_requirements": _choice_requirements(
            choices_payload,
            choice_findings=choice_report["findings"],
        ),
        "readiness_findings": readiness["findings"],
        "validation_commands": list(VALIDATION_COMMANDS),
        "next_action": (
            "Archive this plan with the production release artifact."
            if readiness["production_allowed"]
            else (
                "Assign every blocked proof and infrastructure-choice item to a real "
                "owner, attach durable evidence references, then rerun validation."
            )
        ),
        "readiness_report": {
            "status": readiness["status"],
            "production_allowed": readiness["production_allowed"],
            "choices_status": choice_report["status"],
            "choices_conformant": choice_report["conformant"],
        },
    }
    plan = {
        **plan_without_hash,
        "plan_hash": _stable_hash(plan_without_hash),
    }
    _validate_plan(plan)
    return plan


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _proof_requirements(
    proof: dict[str, Any],
    *,
    readiness_findings: list[str],
) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    for name, fields in production_readiness.REQUIRED_PROOF.items():
        item = proof.get(name)
        if not isinstance(item, dict):
            item = {}
        missing_fields = [
            field
            for field in ("status", "checked_at", "valid_until", "evidence", *fields)
            if _missing(item.get(field))
        ]
        requirements.append(
            {
                "name": name,
                "owner_hint": OWNER_HINTS.get(name, "production owner"),
                "required_fields": list(fields),
                "required_metadata": ["status", "checked_at", "valid_until", "evidence"],
                "current_status": item.get("status", "missing"),
                "present_fields": sorted(key for key, value in item.items() if not _missing(value)),
                "missing_fields": missing_fields,
                "validation_findings": _findings_for_prefix(readiness_findings, f"{name}:"),
                "blocked": bool(missing_fields)
                or bool(_findings_for_prefix(readiness_findings, f"{name}:")),
                "evidence_action": ACTION_HINTS.get(
                    name,
                    "Collect durable production evidence and record its reference.",
                ),
                "completion_rule": (
                    "Set status to passed only after the real evidence reference is "
                    "reviewed, current, and valid for the production release."
                ),
            }
        )
    return requirements


def _choice_requirements(
    choices_payload: dict[str, Any],
    *,
    choice_findings: list[str],
) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    for section, fields in infrastructure_choices.REQUIRED_SECTIONS.items():
        section_value = choices_payload.get(section)
        if not isinstance(section_value, dict):
            section_value = {}
        missing_fields = [field for field in fields if _missing(section_value.get(field))]
        requirements.append(
            {
                "section": section,
                "required_fields": list(fields),
                "present_fields": sorted(
                    key for key, value in section_value.items() if not _missing(value)
                ),
                "missing_fields": missing_fields,
                "validation_findings": _choice_findings(choice_findings, section),
                "blocked": bool(missing_fields) or bool(_choice_findings(choice_findings, section)),
                "evidence_action": (
                    "Record reviewed real infrastructure choices from the production "
                    "environment; placeholders and inline secrets are not acceptable."
                ),
            }
        )
    return requirements


def _findings_for_prefix(findings: list[str], prefix: str) -> list[str]:
    return [item for item in findings if item.startswith(prefix)]


def _choice_findings(findings: list[str], section: str) -> list[str]:
    return [
        item
        for item in findings
        if item.startswith((f"{section}.", f"{section}:", f"schema: $.{section}"))
        or f"'{section}'" in item
    ]


def _missing(value: Any) -> bool:
    if value is True:
        return False
    if isinstance(value, str):
        return not value.strip()
    return value is None


def _stable_hash(payload: dict[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _schema() -> dict[str, Any]:
    schema = json.loads((SCHEMA_ROOT / PLAN_SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return schema


def _validate_plan(plan: dict[str, Any]) -> None:
    try:
        jsonschema.validate(plan, _schema())
    except jsonschema.ValidationError as exc:
        raise RuntimeError(
            f"{PLAN_SCHEMA}: generated production evidence plan does not validate: {exc.message}"
        ) from exc


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
    plan = build_plan(args.root, args.evidence, args.choices)
    rendered = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    if args.output:
        target = args.output if args.output.is_absolute() else args.root / args.output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if plan["production_allowed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
