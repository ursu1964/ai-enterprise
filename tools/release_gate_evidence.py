#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema

GATE_EVIDENCE_SCHEMA = "release-gate-evidence.schema.json"
SCHEMA_ROOT = Path(__file__).resolve().parents[1] / "schemas" / "release-artifacts"

FAST_GATE_COMMANDS: dict[str, str] = {
    "lint": "cd apps/api && .venv/bin/ruff check src tests ../../migrations",
    "typecheck": "cd apps/api && .venv/bin/mypy src",
    "test": "cd apps/api && .venv/bin/pytest -q",
}

CI_GATE_COMMANDS: dict[str, str] = {
    **FAST_GATE_COMMANDS,
    "docker-smoke": "python tools/docker_smoke.py --require-worker",
    "architecture-baseline-manifest": (
        "python tools/architecture_baseline_manifest.py "
        "--output artifacts/architecture-baseline-manifest.json"
    ),
    "roadmap-sequence-gate": (
        "python tools/roadmap_sequence_gate.py --output artifacts/roadmap-sequence-gate.json"
    ),
    "engineering-static": "python tools/engineering_verify.py --static --json",
    "evolution-check": "python tools/evolution_verify.py --json",
    "federation-check": "python tools/federation_verify.py --json",
    "intelligence-check": "python tools/intelligence_verify.py --json",
    "engineering-full": "python tools/engineering_verify.py --full --json",
    "etra-check": "python tools/etra_conformance.py --root . --json",
}

RELEASE_GATE_COMMANDS: dict[str, str] = {
    "compose-check": "docker compose config --quiet",
    "migration-check": (
        "cd apps/api && .venv/bin/alembic heads && "
        ".venv/bin/alembic upgrade head --sql >/dev/null && "
        "cd ../.. && python tools/migration_verify.py --json"
    ),
    **FAST_GATE_COMMANDS,
    "secret-scan": "python tools/secret_scan.py --all",
    "docker-smoke": "python tools/docker_smoke.py --require-worker",
    "architecture-baseline-manifest": (
        "python tools/architecture_baseline_manifest.py "
        "--output artifacts/architecture-baseline-manifest.json"
    ),
    "roadmap-sequence-gate": (
        "python tools/roadmap_sequence_gate.py --output artifacts/roadmap-sequence-gate.json"
    ),
    "dashboard-verify": (
        'python tools/dashboard_verify.py --base-url "${DASHBOARD_BASE_URL:-http://127.0.0.1:8000}"'
    ),
    "dashboard-browser-verify": (
        "apps/api/.venv/bin/python tools/dashboard_browser_verify.py "
        + '--base-url "${DASHBOARD_BASE_URL:-http://127.0.0.1:8000}"'
    ),
    "engineering-static": "python tools/engineering_verify.py --static --json",
    "evolution-check": "python tools/evolution_verify.py --json",
    "federation-check": "python tools/federation_verify.py --json",
    "intelligence-check": "python tools/intelligence_verify.py --json",
    "engineering-full": "python tools/engineering_verify.py --full --json",
    "etra-check": "python tools/etra_conformance.py --root . --json",
}

GATE_COMMAND_PROFILES: dict[str, dict[str, str]] = {
    "fast": FAST_GATE_COMMANDS,
    "ci": CI_GATE_COMMANDS,
    "release": RELEASE_GATE_COMMANDS,
}


def _safe_name(name: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in name)


def run_gate(
    *,
    root: Path,
    name: str,
    command: str,
    output_dir: Path,
    timeout: int,
) -> dict[str, Any]:
    started = time.monotonic()
    target_dir = output_dir if output_dir.is_absolute() else root / output_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / f"{_safe_name(name)}.log"
    result = subprocess.run(
        command,
        cwd=root,
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    duration = round(time.monotonic() - started, 3)
    output_content = (
        result.stdout + ("\n" if result.stdout and result.stderr else "") + result.stderr
    )
    output_path.write_text(output_content, encoding="utf-8")
    return {
        "status": "passed" if result.returncode == 0 else "failed",
        "command": command,
        "return_code": result.returncode,
        "duration_seconds": duration,
        "output_path": str(output_path.relative_to(root)),
        "output_sha256": hashlib.sha256(output_content.encode("utf-8")).hexdigest(),
        "recorded_at": datetime.now(UTC).isoformat(),
    }


def write_evidence(
    *,
    root: Path,
    gate_commands: dict[str, str],
    output: Path,
    output_dir: Path,
    timeout: int,
) -> dict[str, Any]:
    git_before = _git_identity(root)
    gates = {
        name: run_gate(
            root=root,
            name=name,
            command=command,
            output_dir=output_dir,
            timeout=timeout,
        )
        for name, command in gate_commands.items()
    }
    git_after = _git_identity(root)
    provenance_valid = (
        _git_identity_valid(git_before)
        and _git_identity_valid(git_after)
        and git_before == git_after
    )
    document = {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": (
            "passed"
            if provenance_valid and all(gate["status"] == "passed" for gate in gates.values())
            else "failed"
        ),
        "git": git_after,
        "git_before": git_before,
        "provenance_valid": provenance_valid,
        "gates": gates,
    }
    _validate_evidence(document)
    target = output if output.is_absolute() else root / output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return document


def _schema() -> dict[str, Any]:
    schema = json.loads((SCHEMA_ROOT / GATE_EVIDENCE_SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return schema


def _validate_evidence(document: dict[str, Any]) -> None:
    try:
        jsonschema.validate(document, _schema())
    except jsonschema.ValidationError as exc:
        raise RuntimeError(
            f"{GATE_EVIDENCE_SCHEMA}: generated release gate evidence does not validate: "
            f"{exc.message}"
        ) from exc


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


def _parse_gate_command(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("gate command must use name=command")
    name, command = value.split("=", 1)
    name = name.strip()
    command = command.strip()
    if not name or not command:
        raise argparse.ArgumentTypeError("gate command requires non-empty name and command")
    return name, command


def _resolve_gate_commands(
    profiles: list[str] | None,
    gate_commands: list[tuple[str, str]] | None,
) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for profile in profiles or []:
        resolved.update(GATE_COMMAND_PROFILES[profile])
    resolved.update(dict(gate_commands or []))
    if not resolved:
        raise argparse.ArgumentTypeError("at least one --profile or --gate-command is required")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture release gate command evidence.")
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--profile",
        action="append",
        choices=sorted(GATE_COMMAND_PROFILES),
        help=(
            "Named gate command profile. May be repeated; explicit gate commands override profiles."
        ),
    )
    parser.add_argument(
        "--gate-command",
        action="append",
        type=_parse_gate_command,
        help="Gate command in name=command form. May be repeated.",
    )
    parser.add_argument("--output", default="artifacts/gate-evidence.json")
    parser.add_argument("--output-dir", default="artifacts/release-gates")
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    document = write_evidence(
        root=root,
        gate_commands=_resolve_gate_commands(args.profile, args.gate_command),
        output=Path(args.output),
        output_dir=Path(args.output_dir),
        timeout=args.timeout,
    )
    print(json.dumps(document, sort_keys=True))
    return 0 if document["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
