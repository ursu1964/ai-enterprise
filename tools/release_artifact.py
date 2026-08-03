#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import migration_verify

DEFAULT_GATES = (
    ("compose-check", "docker compose config --quiet"),
    ("migration-check", "alembic heads, upgrade SQL, migration graph verification"),
    ("lint", "cd apps/api && .venv/bin/ruff check src tests ../../migrations"),
    ("typecheck", "cd apps/api && .venv/bin/mypy src"),
    ("test", "cd apps/api && .venv/bin/pytest -q"),
    ("secret-scan", "python tools/secret_scan.py --all"),
    ("docker-smoke", "python tools/docker_smoke.py --require-worker"),
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


def _load_gate_evidence(root: Path, evidence_file: Path | None) -> dict[str, Any]:
    if evidence_file is None:
        return {"loaded": False, "path": None, "git": {}, "gates": {}}
    path = evidence_file if evidence_file.is_absolute() else root / evidence_file
    if not path.exists():
        return {"loaded": False, "path": str(evidence_file), "git": {}, "gates": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"loaded": False, "path": str(evidence_file), "git": {}, "gates": {}}
    gates = payload.get("gates", {})
    if not isinstance(gates, dict):
        return {"loaded": False, "path": str(evidence_file), "git": {}, "gates": {}}
    return {
        "loaded": True,
        "path": str(evidence_file),
        "git": payload.get("git", {}) if isinstance(payload.get("git", {}), dict) else {},
        "gates": {
            str(name): evidence
            for name, evidence in gates.items()
            if isinstance(evidence, dict)
        },
    }


def build_artifact(
    root: Path,
    *,
    status: str = "passed",
    evidence_file: Path | None = None,
    require_evidence_for: tuple[str, ...] = (),
) -> dict[str, Any]:
    migration_report = migration_verify.verify(root / "migrations" / "versions")
    evidence_payload = _load_gate_evidence(root, evidence_file)
    gate_evidence = evidence_payload["gates"]
    current_git = {
        "commit": _git(["rev-parse", "HEAD"], root),
        "branch": _git(["branch", "--show-current"], root),
        "dirty": bool(_git(["status", "--porcelain"], root)),
    }
    evidence_git = evidence_payload["git"]
    missing_required_evidence = [
        name for name in require_evidence_for if name not in gate_evidence
    ]
    evidence_commit_matches = (
        not evidence_payload["loaded"]
        or not evidence_git.get("commit")
        or evidence_git.get("commit") == current_git["commit"]
    )
    gate_status = status if migration_report["conformant"] else "failed"
    gates = [
        {
            "name": name,
            "command": command,
            "status": (
                "failed"
                if name in missing_required_evidence or not evidence_commit_matches
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
            },
        }
        for name, command in DEFAULT_GATES
    ]
    gate_failure_count = sum(1 for gate in gates if gate["status"] != "passed")
    document: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "failed" if gate_failure_count else gate_status,
        "git": current_git,
        "gates": gates,
        "gate_summary": {
            "total": len(gates),
            "passed": sum(1 for gate in gates if gate["status"] == "passed"),
            "failed": gate_failure_count,
            "captured_evidence_required": sorted(require_evidence_for),
            "captured_evidence_missing": missing_required_evidence,
            "execution_model": (
                "Release gates are executed by make check-release before this "
                "artifact is written."
            ),
        },
        "gate_evidence_file": {
            "path": evidence_payload["path"],
            "loaded": evidence_payload["loaded"],
            "git": evidence_git,
            "commit_matches_current": evidence_commit_matches,
            "missing_required_gates": missing_required_evidence,
        },
        "migration_verification": migration_report,
        "artifact_policy": {
            "created_after_successful_release_gate": True,
            "archive_path": "artifacts/release-verification.json",
            "fails_when_migration_verification_fails": True,
            "fails_when_required_gate_evidence_missing": True,
            "fails_when_gate_evidence_commit_mismatch": True,
        },
    }
    document["artifact_hash"] = _artifact_hash(document)
    return document


def write_artifact(
    root: Path,
    output: Path,
    *,
    status: str = "passed",
    evidence_file: Path | None = None,
    require_evidence_for: tuple[str, ...] = (),
) -> dict[str, Any]:
    document = build_artifact(
        root,
        status=status,
        evidence_file=evidence_file,
        require_evidence_for=require_evidence_for,
    )
    target = output if output.is_absolute() else root / output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
    args = parser.parse_args()
    root = Path(args.root).resolve()
    evidence_file = Path(args.evidence_file) if args.evidence_file else None
    document = write_artifact(
        root,
        Path(args.output),
        status=args.status,
        evidence_file=evidence_file,
        require_evidence_for=tuple(
            item.strip() for item in args.require_evidence_for.split(",") if item.strip()
        ),
    )
    print(json.dumps(document, sort_keys=True))
    return 0 if document["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
