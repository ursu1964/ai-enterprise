#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema
import migration_verify
import production_evidence_plan
import production_readiness
import production_readiness_contracts

SCHEMA_ROOT = Path(__file__).resolve().parents[1] / "schemas" / "release-artifacts"

DEFAULT_GATES = (
    ("compose-check", "docker compose config --quiet"),
    ("migration-check", "alembic heads, upgrade SQL, migration graph verification"),
    ("lint", "cd apps/api && .venv/bin/ruff check src tests ../../migrations"),
    ("typecheck", "cd apps/api && .venv/bin/mypy src"),
    ("test", "cd apps/api && .venv/bin/pytest -q"),
    ("secret-scan", "python tools/secret_scan.py --all"),
    ("docker-smoke", "python tools/docker_smoke.py --require-worker"),
    (
        "dashboard-verify",
        'python tools/dashboard_verify.py --base-url "${DASHBOARD_BASE_URL:-http://127.0.0.1:8000}"',
    ),
    (
        "dashboard-browser-verify",
        "apps/api/.venv/bin/python tools/dashboard_browser_verify.py "
        + '--base-url "${DASHBOARD_BASE_URL:-http://127.0.0.1:8000}"',
    ),
    ("engineering-static", "python tools/engineering_verify.py --static --json"),
    ("evolution-check", "python tools/evolution_verify.py --json"),
    ("federation-check", "python tools/federation_verify.py --json"),
    ("intelligence-check", "python tools/intelligence_verify.py --json"),
    ("engineering-full", "python tools/engineering_verify.py --full --json"),
    ("etra-check", "python tools/etra_conformance.py --root . --json"),
)


def _git(args: list[str], root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _artifact_hash(document: dict[str, Any]) -> str:
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _recomputed_artifact_hash(document: dict[str, Any]) -> str:
    payload = {key: value for key, value in document.items() if key != "artifact_hash"}
    return _artifact_hash(payload)


def _schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMA_ROOT / name).read_text(encoding="utf-8"))


def _validate_schema_document(document: dict[str, Any], *, schema_name: str) -> None:
    schema = _schema(schema_name)
    jsonschema.Draft202012Validator.check_schema(schema)
    try:
        jsonschema.validate(document, schema)
    except jsonschema.ValidationError as exc:
        raise RuntimeError(
            f"{schema_name}: generated document does not validate: {exc.message}"
        ) from exc


def _load_gate_evidence(root: Path, evidence_file: Path | None) -> dict[str, Any]:
    if evidence_file is None:
        return {"loaded": False, "path": None, "sha256": None, "git": {}, "gates": {}}
    path = evidence_file if evidence_file.is_absolute() else root / evidence_file
    if not path.exists():
        return {
            "loaded": False,
            "path": str(evidence_file),
            "sha256": None,
            "git": {},
            "gates": {},
        }
    raw_payload = path.read_bytes()
    payload = json.loads(raw_payload)
    if not isinstance(payload, dict):
        return {"loaded": False, "path": str(evidence_file), "sha256": None, "git": {}, "gates": {}}
    gates = payload.get("gates", {})
    if not isinstance(gates, dict):
        return {"loaded": False, "path": str(evidence_file), "sha256": None, "git": {}, "gates": {}}
    return {
        "loaded": True,
        "path": str(evidence_file),
        "sha256": hashlib.sha256(raw_payload).hexdigest(),
        "status": payload.get("status"),
        "provenance_valid": payload.get("provenance_valid"),
        "git": payload.get("git", {}) if isinstance(payload.get("git", {}), dict) else {},
        "gates": {
            str(name): evidence for name, evidence in gates.items() if isinstance(evidence, dict)
        },
    }


def _git_identity(root: Path) -> dict[str, Any]:
    status = _git(["status", "--porcelain", "--untracked-files=all"], root)
    return {
        "commit": _git(["rev-parse", "HEAD"], root),
        "tree": _git(["rev-parse", "HEAD^{tree}"], root),
        "branch": _git(["branch", "--show-current"], root),
        "dirty": status == "unknown" or bool(status),
    }


def _git_identity_valid(identity: dict[str, Any]) -> bool:
    return (
        identity.get("commit") not in {None, "", "unknown"}
        and identity.get("tree") not in {None, "", "unknown"}
        and identity.get("dirty") is False
    )


def _gate_log_integrity(root: Path, evidence: dict[str, Any]) -> dict[str, Any]:
    output_path = evidence.get("output_path")
    expected_hash = evidence.get("output_sha256")
    if not output_path:
        return {"checked": False, "valid": True, "actual_sha256": None}
    path = Path(str(output_path))
    resolved_root = root.resolve()
    resolved = (path if path.is_absolute() else root / path).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        return {"checked": True, "valid": False, "actual_sha256": None}
    if not resolved.is_file() or not expected_hash:
        return {"checked": True, "valid": False, "actual_sha256": None}
    actual_hash = hashlib.sha256(resolved.read_bytes()).hexdigest()
    return {
        "checked": True,
        "valid": actual_hash == expected_hash,
        "actual_sha256": actual_hash,
    }


def build_artifact(
    root: Path,
    *,
    status: str = "passed",
    evidence_file: Path | None = None,
    require_evidence_for: tuple[str, ...] = (),
    production: bool = False,
    archive_path: Path = Path("artifacts/release-verification.json"),
    production_readiness_file: Path = Path("docs/enterprise/production-readiness-evidence.json"),
    infrastructure_choices_file: Path = Path(
        "docs/enterprise/real-world-infrastructure-decisions.json"
    ),
) -> dict[str, Any]:
    generated_at = datetime.now(UTC)
    migration_report = migration_verify.verify(root / "migrations" / "versions")
    evidence_payload = _load_gate_evidence(root, evidence_file)
    gate_evidence = evidence_payload["gates"]
    current_git = _git_identity(root)
    evidence_git = evidence_payload["git"]
    missing_required_evidence = [name for name in require_evidence_for if name not in gate_evidence]
    evidence_commit_matches = (
        not evidence_payload["loaded"] or evidence_git.get("commit") == current_git["commit"]
    )
    evidence_tree_matches = (
        not evidence_payload["loaded"] or evidence_git.get("tree") == current_git["tree"]
    )
    current_git_valid = _git_identity_valid(current_git)
    evidence_git_valid = not evidence_payload["loaded"] or (
        _git_identity_valid(evidence_git) and evidence_payload.get("provenance_valid") is True
    )
    gate_log_integrity = {
        name: _gate_log_integrity(root, evidence) for name, evidence in gate_evidence.items()
    }
    gate_status = status if migration_report["conformant"] else "failed"
    gates = [
        {
            "name": name,
            "command": command,
            "status": (
                "failed"
                if (
                    name in missing_required_evidence
                    or not current_git_valid
                    or not evidence_git_valid
                    or not evidence_commit_matches
                    or not evidence_tree_matches
                    or not gate_log_integrity.get(name, {"valid": True})["valid"]
                )
                else gate_evidence.get(name, {}).get("status", gate_status)
            ),
            "required": True,
            "evidence_required": name in require_evidence_for,
            "evidence": {
                "source": "make check-release dependency",
                "recorded_by": "tools/release_artifact.py",
                "executed_before_artifact": True,
                "missing_required_evidence": name in missing_required_evidence,
                **gate_evidence.get(name, {}),
                "log_integrity": gate_log_integrity.get(
                    name, {"checked": False, "valid": True, "actual_sha256": None}
                ),
            },
        }
        for name, command in DEFAULT_GATES
    ]
    gate_failure_count = sum(1 for gate in gates if gate["status"] != "passed")
    readiness = (
        production_readiness.verify(
            root,
            production_readiness_file,
            infrastructure_choices_file,
            now=generated_at,
        )
        if production
        else None
    )
    evidence_plan = (
        production_evidence_plan.build_plan(
            root,
            production_readiness_file,
            infrastructure_choices_file,
            now=generated_at,
        )
        if production
        else None
    )
    readiness_contracts = (
        production_readiness_contracts.verify_files(
            choices_file=(
                infrastructure_choices_file
                if infrastructure_choices_file.is_absolute()
                else root / infrastructure_choices_file
            ),
            evidence_file=(
                production_readiness_file
                if production_readiness_file.is_absolute()
                else root / production_readiness_file
            ),
        )
        if production
        else None
    )
    production_blocked = bool(readiness and not readiness["production_allowed"])
    production_contracts_blocked = bool(
        readiness_contracts and not readiness_contracts["conformant"]
    )
    document: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at": generated_at.isoformat(),
        "status": (
            "failed"
            if gate_failure_count or production_blocked or production_contracts_blocked
            else gate_status
        ),
        "release_environment": "production" if production else "non-production",
        "production_readiness_contracts": readiness_contracts,
        "production_readiness": readiness,
        "production_evidence_plan": evidence_plan,
        "git": current_git,
        "gates": gates,
        "gate_summary": {
            "total": len(gates),
            "passed": sum(1 for gate in gates if gate["status"] == "passed"),
            "failed": gate_failure_count,
            "captured_evidence_required": sorted(require_evidence_for),
            "captured_evidence_missing": missing_required_evidence,
            "execution_model": (
                "Release gates are executed by make check-release before this artifact is written."
            ),
        },
        "gate_evidence_file": {
            "path": evidence_payload["path"],
            "loaded": evidence_payload["loaded"],
            "sha256": evidence_payload.get("sha256"),
            "git": evidence_git,
            "provenance_valid": evidence_git_valid,
            "commit_matches_current": evidence_commit_matches,
            "tree_matches_current": evidence_tree_matches,
            "missing_required_gates": missing_required_evidence,
        },
        "migration_verification": migration_report,
        "artifact_policy": {
            "created_after_successful_release_gate": True,
            "archive_path": str(archive_path),
            "fails_when_migration_verification_fails": True,
            "fails_when_required_gate_evidence_missing": True,
            "fails_when_gate_evidence_commit_mismatch": True,
            "fails_when_git_is_dirty_or_unknown": True,
            "fails_when_gate_evidence_tree_mismatch": True,
            "fails_when_gate_log_integrity_fails": True,
            "fails_when_production_readiness_contracts_invalid": True,
            "fails_when_production_readiness_is_blocked": True,
            "records_production_readiness_contracts": production is True,
            "records_production_evidence_plan": production is True,
        },
    }
    document["artifact_hash"] = _artifact_hash(document)
    _validate_schema_document(document, schema_name="release-verification.schema.json")
    return document


def render_markdown(document: dict[str, Any]) -> str:
    readiness = document.get("production_readiness") or {}
    contracts = document.get("production_readiness_contracts") or {}
    plan = document.get("production_evidence_plan") or {}
    gate_summary = document["gate_summary"]
    lines = [
        "# Release Verification Artifact",
        "",
        f"- Status: `{document['status']}`",
        f"- Environment: `{document['release_environment']}`",
        f"- Artifact hash: `{document['artifact_hash']}`",
        f"- Git commit: `{document['git'].get('commit')}`",
        f"- Git dirty: `{str(document['git'].get('dirty')).lower()}`",
        "",
        "## Gate summary",
        "",
        f"- Total gates: `{gate_summary['total']}`",
        f"- Passed gates: `{gate_summary['passed']}`",
        f"- Failed gates: `{gate_summary['failed']}`",
        f"- Required captured evidence: `{len(gate_summary['captured_evidence_required'])}`",
        f"- Missing captured evidence: `{len(gate_summary['captured_evidence_missing'])}`",
        "",
        "## Production readiness",
        "",
    ]
    if document["release_environment"] != "production":
        lines.append("- Not a production artifact.")
    else:
        lines.extend(
            [
                f"- Structural contracts: `{contracts.get('status')}`",
                f"- Structural contract findings: `{len(contracts.get('findings', []))}`",
                f"- Semantic readiness: `{readiness.get('status')}`",
                f"- Production allowed: `{str(readiness.get('production_allowed')).lower()}`",
                f"- Semantic readiness findings: `{len(readiness.get('findings', []))}`",
                f"- Evidence plan status: `{plan.get('status')}`",
            ]
        )
        for finding in contracts.get("findings", [])[:20]:
            lines.append(f"  - Contract finding: {finding}")
        for finding in readiness.get("findings", [])[:20]:
            lines.append(f"  - Readiness finding: {finding}")
    lines.extend(["", "## Failed gates", ""])
    failed_gates = [gate for gate in document["gates"] if gate["status"] != "passed"]
    if not failed_gates:
        lines.append("- None")
    for gate in failed_gates:
        lines.append(f"- [ ] `{gate['name']}` — {gate['command']}")
        if gate["evidence"].get("missing_required_evidence"):
            lines.append("  - Missing required captured evidence.")
        log_integrity = gate["evidence"].get("log_integrity", {})
        if log_integrity.get("checked") and not log_integrity.get("valid"):
            lines.append("  - Gate log integrity failed.")
    lines.extend(
        [
            "",
            "## Policy",
            "",
        ]
    )
    for key, value in sorted(document["artifact_policy"].items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    return "\n".join(lines)


def verify_markdown_summary(json_path: Path, markdown_path: Path) -> dict[str, Any]:
    findings: list[str] = []
    try:
        document = json.loads(json_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        document = {}
        findings.append(f"{json_path}: JSON artifact is missing")
    except json.JSONDecodeError as exc:
        document = {}
        findings.append(f"{json_path}: invalid JSON: {exc}")
    if not isinstance(document, dict):
        document = {}
        findings.append(f"{json_path}: JSON artifact must be an object")

    stored_hash = document.get("artifact_hash")
    recomputed_hash = _recomputed_artifact_hash(document) if document else None
    if not isinstance(stored_hash, str) or len(stored_hash) != 64:
        findings.append("artifact_hash: missing or invalid")
    elif stored_hash != recomputed_hash:
        findings.append("artifact_hash: stored hash does not match JSON content")

    try:
        markdown = markdown_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        markdown = ""
        findings.append(f"{markdown_path}: Markdown summary is missing")
    expected_fragment = f"Artifact hash: `{stored_hash}`" if isinstance(stored_hash, str) else None
    if expected_fragment and expected_fragment not in markdown:
        findings.append("markdown: artifact hash reference is missing or stale")

    report = {
        "schema_version": "1.0",
        "status": "valid" if not findings else "invalid",
        "valid": not findings,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "stored_artifact_hash": stored_hash,
        "recomputed_artifact_hash": recomputed_hash,
        "findings": findings,
        "next_action": (
            "Archive JSON and Markdown together."
            if not findings
            else "Regenerate the release artifact JSON and Markdown summary together."
        ),
    }
    _validate_schema_document(report, schema_name="release-verification-check.schema.json")
    return report


def write_artifact(
    root: Path,
    output: Path,
    *,
    status: str = "passed",
    evidence_file: Path | None = None,
    require_evidence_for: tuple[str, ...] = (),
    production: bool = False,
    production_readiness_file: Path = Path("docs/enterprise/production-readiness-evidence.json"),
    infrastructure_choices_file: Path = Path(
        "docs/enterprise/real-world-infrastructure-decisions.json"
    ),
    markdown_output: Path | None = None,
) -> dict[str, Any]:
    document = build_artifact(
        root,
        status=status,
        evidence_file=evidence_file,
        require_evidence_for=require_evidence_for,
        production=production,
        archive_path=output,
        production_readiness_file=production_readiness_file,
        infrastructure_choices_file=infrastructure_choices_file,
    )
    target = output if output.is_absolute() else root / output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if markdown_output is not None:
        markdown_target = (
            markdown_output if markdown_output.is_absolute() else root / markdown_output
        )
        markdown_target.parent.mkdir(parents=True, exist_ok=True)
        markdown_target.write_text(render_markdown(document), encoding="utf-8")
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a release verification artifact.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="artifacts/release-verification.json")
    parser.add_argument("--status", default="passed", choices=("passed", "failed"))
    parser.add_argument(
        "--evidence-file",
        default=None,
        help="Optional JSON file with per-gate evidence under a top-level gates object.",
    )
    parser.add_argument(
        "--require-evidence-for",
        default="",
        help="Comma-separated gate names that must have captured evidence.",
    )
    parser.add_argument("--production", action="store_true")
    parser.add_argument(
        "--production-readiness-file",
        default="docs/enterprise/production-readiness-evidence.json",
    )
    parser.add_argument(
        "--infrastructure-choices-file",
        default="docs/enterprise/real-world-infrastructure-decisions.json",
    )
    parser.add_argument("--markdown-output", default=None)
    parser.add_argument("--verify-json", default=None)
    parser.add_argument("--verify-markdown", default=None)
    parser.add_argument("--verify-output", default=None)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    if args.verify_json or args.verify_markdown:
        if not args.verify_json or not args.verify_markdown:
            parser.error("--verify-json and --verify-markdown must be provided together")
        report = verify_markdown_summary(
            Path(args.verify_json),
            Path(args.verify_markdown),
        )
        if args.verify_output:
            target = Path(args.verify_output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, sort_keys=True))
        return 0 if report["valid"] else 1
    evidence_file = Path(args.evidence_file) if args.evidence_file else None
    document = write_artifact(
        root,
        Path(args.output),
        status=args.status,
        evidence_file=evidence_file,
        require_evidence_for=tuple(
            item.strip() for item in args.require_evidence_for.split(",") if item.strip()
        ),
        production=args.production,
        production_readiness_file=Path(args.production_readiness_file),
        infrastructure_choices_file=Path(args.infrastructure_choices_file),
        markdown_output=Path(args.markdown_output) if args.markdown_output else None,
    )
    print(json.dumps(document, sort_keys=True))
    return 0 if document["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
