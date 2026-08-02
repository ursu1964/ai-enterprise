#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


def _check(
    checks: list[dict[str, Any]], key: str, ok: bool, message: str, action: str
) -> None:
    checks.append(
        {
            "key": key,
            "status": "pass" if ok else "fail",
            "message": message,
            "action": action,
        }
    )


def _run(command: list[str], cwd: Path, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def verify(root: Path, backup_root: Path, *, docker: bool = True) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    backup_root.mkdir(parents=True, exist_ok=True)
    _check(
        checks,
        "backup_root",
        backup_root.exists() and backup_root.is_dir(),
        f"Backup root is available at {backup_root}.",
        "Create a durable server backup directory outside the application container.",
    )
    marker = backup_root / ".write-test"
    try:
        marker.write_text("ok", encoding="utf-8")
        marker.unlink(missing_ok=True)
        writable = True
    except OSError:
        writable = False
    _check(
        checks,
        "backup_root_writable",
        writable,
        "Backup root is writable by the operator.",
        "Fix filesystem ownership or mount permissions for the backup directory.",
    )
    artifacts = root / "artifacts"
    runtime_data = root / "runtime-data"
    _check(
        checks,
        "artifact_source",
        artifacts.exists(),
        f"Artifact source is available at {artifacts}.",
        "Create or mount artifact storage before relying on backup verification.",
    )
    _check(
        checks,
        "runtime_source",
        runtime_data.exists(),
        f"Runtime source is available at {runtime_data}.",
        "Create or mount runtime-data storage before relying on backup verification.",
    )
    if docker:
        result = _run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "postgres",
                "pg_dump",
                "-U",
                "ai_enterprise",
                "-d",
                "ai_enterprise",
                "--schema-only",
            ],
            cwd=root,
        )
        ok = result.returncode == 0 and "CREATE TABLE" in result.stdout
        _check(
            checks,
            "postgres_schema_dump",
            ok,
            "Postgres schema dump completed.",
            "Start Postgres and verify credentials before scheduling database backups.",
        )
    failures = [item for item in checks if item["status"] == "fail"]
    return {
        "conformant": not failures,
        "backup_root": str(backup_root),
        "checks": checks,
        "findings": [f"{item['key']}: {item['action']}" for item in failures],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify AI Enterprise backup readiness.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--backup-root", default="runtime-data/backups")
    parser.add_argument("--no-docker", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    backup_root = Path(args.backup_root)
    if not backup_root.is_absolute():
        backup_root = root / backup_root
    report = verify(root, backup_root, docker=not args.no_docker)
    if args.json:
        print(json.dumps(report, sort_keys=True))
    elif report["conformant"]:
        print("Backup readiness verified")
    else:
        for finding in report["findings"]:
            print(finding)
    return 0 if report["conformant"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
