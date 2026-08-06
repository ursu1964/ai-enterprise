"""Schema validation helpers for production-readiness operator input files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import jsonschema

SCHEMA_ROOT = Path(__file__).resolve().parents[1] / "schemas" / "production-readiness"


def validate_document(
    payload: dict[str, Any],
    *,
    schema_name: str,
) -> list[str]:
    schema = json.loads((SCHEMA_ROOT / schema_name).read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    findings: list[str] = []
    for error in sorted(validator.iter_errors(payload), key=lambda item: item.json_path):
        findings.append(f"{error.json_path}: {error.message}")
    return findings


def validate_infrastructure_decisions(payload: dict[str, Any]) -> list[str]:
    return validate_document(payload, schema_name="infrastructure-decisions.schema.json")


def validate_production_evidence(payload: dict[str, Any]) -> list[str]:
    return validate_document(payload, schema_name="production-evidence.schema.json")


def verify_files(
    *,
    choices_file: Path,
    evidence_file: Path,
) -> dict[str, Any]:
    checks = [
        _validate_file(
            name="infrastructure_decisions",
            path=choices_file,
            schema_name="infrastructure-decisions.schema.json",
        ),
        _validate_file(
            name="production_evidence",
            path=evidence_file,
            schema_name="production-evidence.schema.json",
        ),
    ]
    findings = [
        f"{check['name']}: {finding}"
        for check in checks
        for finding in check["findings"]
    ]
    return {
        "schema_version": "1.0",
        "status": "valid" if not findings else "invalid",
        "conformant": not findings,
        "checks": checks,
        "findings": findings,
        "next_action": (
            "Run rtk make production-readiness for semantic validation."
            if not findings
            else "Fix schema findings before running semantic production readiness."
        ),
    }


def _validate_file(*, name: str, path: Path, schema_name: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "name": name,
            "path": str(path),
            "schema": schema_name,
            "status": "missing",
            "findings": [f"{path}: file is missing"],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "name": name,
            "path": str(path),
            "schema": schema_name,
            "status": "invalid",
            "findings": [f"{path}: invalid JSON: {exc}"],
        }
    if not isinstance(payload, dict):
        findings = [f"{path}: document must be a JSON object"]
    else:
        findings = validate_document(payload, schema_name=schema_name)
    return {
        "name": name,
        "path": str(path),
        "schema": schema_name,
        "status": "valid" if not findings else "invalid",
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--choices",
        type=Path,
        default=Path("docs/enterprise/real-world-infrastructure-decisions.json"),
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("docs/enterprise/production-readiness-evidence.json"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = verify_files(choices_file=args.choices, evidence_file=args.evidence)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["conformant"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
