"""Render a concise production-evidence blocker summary for operators."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import jsonschema
import production_evidence_plan

SCHEMA_ROOT = Path(__file__).resolve().parents[1] / "schemas" / "production-readiness"
STATUS_SCHEMA = "production-evidence-status.schema.json"


def build_status(
    root: Path,
    *,
    evidence_file: Path = Path("docs/enterprise/production-readiness-evidence.json"),
    choices_file: Path = Path("docs/enterprise/real-world-infrastructure-decisions.json"),
) -> dict[str, Any]:
    plan = production_evidence_plan.build_plan(
        root,
        evidence_file,
        choices_file,
    )
    blocked_proofs = [
        _proof_summary(item) for item in plan["proof_requirements"] if item["blocked"]
    ]
    blocked_choices = [
        _choice_summary(item)
        for item in plan["infrastructure_choice_requirements"]
        if item["blocked"]
    ]
    status = {
        "schema_version": "1.0",
        "status": plan["status"],
        "production_allowed": plan["production_allowed"],
        "evidence_file": plan["evidence_file"],
        "choices_file": plan["choices_file"],
        "blocked_proof_count": len(blocked_proofs),
        "blocked_choice_count": len(blocked_choices),
        "blocked_proofs": blocked_proofs,
        "blocked_choices": blocked_choices,
        "readiness_finding_count": len(plan["readiness_findings"]),
        "next_commands": plan["validation_commands"],
        "next_action": plan["next_action"],
    }
    _validate_status(status)
    return status


def render_markdown(status: dict[str, Any]) -> str:
    lines = [
        "# Production Evidence Status",
        "",
        f"- Status: `{status['status']}`",
        f"- Production allowed: `{str(status['production_allowed']).lower()}`",
        f"- Blocked proof groups: `{status['blocked_proof_count']}`",
        f"- Blocked infrastructure choice sections: `{status['blocked_choice_count']}`",
        f"- Readiness findings: `{status['readiness_finding_count']}`",
        "",
        "## Blocked proof groups",
        "",
    ]
    if not status["blocked_proofs"]:
        lines.append("- None")
    for proof in status["blocked_proofs"]:
        lines.extend(
            [
                f"- [ ] `{proof['name']}` — {proof['owner_hint']}",
                f"  - Current status: `{proof['current_status']}`",
                f"  - Action: {proof['action']}",
            ]
        )
        for finding in proof["findings"]:
            lines.append(f"  - Finding: {finding}")
    lines.extend(["", "## Blocked infrastructure choices", ""])
    if not status["blocked_choices"]:
        lines.append("- None")
    for choice in status["blocked_choices"]:
        lines.extend(
            [
                f"- [ ] `{choice['section']}`",
                f"  - Action: {choice['action']}",
            ]
        )
        for finding in choice["findings"]:
            lines.append(f"  - Finding: {finding}")
    lines.extend(["", "## Next commands", ""])
    for command in status["next_commands"]:
        lines.append(f"- `{command}`")
    lines.extend(["", f"Next action: {status['next_action']}", ""])
    return "\n".join(lines)


def _proof_summary(item: dict[str, Any]) -> dict[str, Any]:
    findings = item["validation_findings"] or [
        f"missing {field}" for field in item["missing_fields"]
    ]
    return {
        "name": item["name"],
        "owner_hint": item["owner_hint"],
        "current_status": item["current_status"],
        "findings": findings,
        "action": item["evidence_action"],
    }


def _choice_summary(item: dict[str, Any]) -> dict[str, Any]:
    findings = item["validation_findings"] or [
        f"missing {field}" for field in item["missing_fields"]
    ]
    return {
        "section": item["section"],
        "findings": findings,
        "action": item["evidence_action"],
    }


def _schema() -> dict[str, Any]:
    schema = json.loads((SCHEMA_ROOT / STATUS_SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return schema


def _validate_status(status: dict[str, Any]) -> None:
    try:
        jsonschema.validate(status, _schema())
    except jsonschema.ValidationError as exc:
        raise RuntimeError(
            f"{STATUS_SCHEMA}: generated production evidence status does not validate: "
            f"{exc.message}"
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
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()

    status = build_status(args.root, evidence_file=args.evidence, choices_file=args.choices)
    rendered = json.dumps(status, indent=2, sort_keys=True) + "\n"
    if args.output:
        target = args.output if args.output.is_absolute() else args.root / args.output
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
    if args.markdown_output:
        target = (
            args.markdown_output
            if args.markdown_output.is_absolute()
            else args.root / args.markdown_output
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_markdown(status), encoding="utf-8")
    print(rendered, end="")
    return 0 if status["production_allowed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
