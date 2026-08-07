#!/usr/bin/env python3
"""Generate the AEB-1.0 architecture baseline manifest.

The manifest is a machine-readable freeze record for R1-R22, R-INDEX,
architecture baseline documents, audit/revision artifacts, post-R22 governance,
and clause-verification evidence. It records SHA-256 hashes for every included
artifact and a deterministic root fingerprint for the complete baseline set.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema

SCHEMA_REF = "schemas/architecture-baseline/architecture-baseline-manifest.schema.json"
BASELINE_ID = "AEB-1.0"
BASELINE_VERSION = "1.0.0"
OWNER = "enterprise-architecture"


@dataclass(frozen=True)
class ArtifactSpec:
    artifact_id: str
    artifact_type: str
    path: str
    version: str = BASELINE_VERSION


def build_manifest(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    root = root.resolve()
    now = now or datetime.now(UTC)
    specs = _artifact_specs()
    artifacts = [_artifact(root, spec) for spec in specs]
    findings = [
        {
            "severity": "critical",
            "message": "Required baseline artifact is missing",
            "path": item["source_path"],
        }
        for item in artifacts
        if item["status"] == "missing"
    ]
    manifest = {
        "schema_version": "1.0",
        "schema_ref": SCHEMA_REF,
        "baseline_id": BASELINE_ID,
        "baseline_version": BASELINE_VERSION,
        "status": "incomplete" if findings else "frozen",
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "scope": {
            "requirements": {
                "first": "R1",
                "last": "R22",
                "count": 22,
            },
            "r_index": "docs/R-INDEX.md",
            "architecture_baseline": "docs/ARCHITECTURE-BASELINE-v1.0.md",
        },
        "governance": {
            "immutable": True,
            "change_process": "R-REV",
            "direct_modification": "prohibited",
        },
        "implementation": {
            "first_slice": "P12",
            "first_target": "R2",
            "phase_range": "P12-P32",
        },
        "future_modules": {
            "R23": {
                "allowed": False,
                "authorization": "requires accepted ADR after post-R22 governance",
            }
        },
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "root_hash": {
            "algorithm": "SHA-256",
            "value": _root_hash(artifacts),
        },
        "findings": findings,
        "next_action": (
            "Use AEB-1.0 as the immutable architecture reference."
            if not findings
            else "Restore every missing baseline artifact before treating AEB-1.0 as frozen."
        ),
    }
    _validate_manifest(root, manifest)
    return manifest


def _artifact_specs() -> list[ArtifactSpec]:
    specs = [
        ArtifactSpec(f"R{number}", "requirement_specification", f"1/r{number}.txt")
        for number in range(1, 23)
    ]
    specs.extend(
        [
            ArtifactSpec("R-INDEX", "control_artifact", "docs/R-INDEX.md"),
            ArtifactSpec(
                BASELINE_ID,
                "control_artifact",
                "docs/ARCHITECTURE-BASELINE-v1.0.md",
            ),
            ArtifactSpec(
                "R-AUDIT-01",
                "audit_artifact",
                "docs/R-AUDIT-01-current-state-repository-audit.md",
            ),
            ArtifactSpec(
                "R-AUDIT-02",
                "audit_artifact",
                "docs/R-AUDIT-02-r1-r22-alignment-matrix.md",
            ),
            ArtifactSpec(
                "R-REV-01",
                "revision_artifact",
                "docs/R-REV-01-corrected-r-series-baseline.md",
            ),
            ArtifactSpec(
                "ADR-0007",
                "governance_adr",
                "docs/adrs/0007-post-r22-roadmap-governance.md",
            ),
        ]
    )
    specs.extend(
        ArtifactSpec(
            f"P{number + 10}-R{number}-CLAUSE-VERIFICATION",
            "implementation_evidence",
            f"implementation/r{number:02d}/clause-verification.md",
        )
        for number in range(2, 23)
    )
    return specs


def _artifact(root: Path, spec: ArtifactSpec) -> dict[str, Any]:
    path = root / spec.path
    return {
        "id": spec.artifact_id,
        "type": spec.artifact_type,
        "version": spec.version,
        "baseline_id": BASELINE_ID,
        "owner": OWNER,
        "source_path": spec.path,
        "content_hash": {
            "algorithm": "SHA-256",
            "value": _content_hash(path) if path.is_file() else _missing_hash(spec.path),
        },
        "status": "frozen" if path.is_file() else "missing",
    }


def _content_hash(path: Path) -> str:
    content = path.read_text(encoding="utf-8", errors="replace")
    canonical = content.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _missing_hash(path: str) -> str:
    return hashlib.sha256(f"missing:{path}".encode()).hexdigest()


def _root_hash(artifacts: list[dict[str, Any]]) -> str:
    lines = [
        f"{item['id']}:{item['source_path']}:{item['content_hash']['value']}"
        for item in sorted(artifacts, key=lambda artifact: artifact["id"])
    ]
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()


def _schema(root: Path) -> dict[str, Any]:
    schema = json.loads((root / SCHEMA_REF).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return schema


def _validate_manifest(root: Path, manifest: dict[str, Any]) -> None:
    try:
        jsonschema.validate(manifest, _schema(root))
    except jsonschema.ValidationError as exc:
        raise RuntimeError(
            f"{SCHEMA_REF}: generated architecture baseline manifest does not validate: "
            f"{exc.message}"
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/architecture-baseline-manifest.json"),
    )
    args = parser.parse_args()

    root = args.root.resolve()
    manifest = build_manifest(root)
    rendered = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))
    return 0 if manifest["status"] == "frozen" else 1


if __name__ == "__main__":
    raise SystemExit(main())
