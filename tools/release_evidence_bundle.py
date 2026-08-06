from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema


@dataclass(frozen=True)
class ArtifactSpec:
    name: str
    path: Path
    kind: str
    content_type: str
    bk_r11_evidence_type: str
    schema_ref: str | None = None


ARCHITECTURE_BASELINE_ARTIFACTS: tuple[ArtifactSpec, ...] = (
    ArtifactSpec(
        name="architecture-baseline-v1",
        path=Path("docs/ARCHITECTURE-BASELINE-v1.0.md"),
        kind="architecture_baseline",
        content_type="text/markdown",
        bk_r11_evidence_type="architecture-baseline-freeze-candidate",
    ),
    ArtifactSpec(
        name="r-audit-01",
        path=Path("docs/R-AUDIT-01-current-state-repository-audit.md"),
        kind="repository_audit",
        content_type="text/markdown",
        bk_r11_evidence_type="repository-audit",
    ),
    ArtifactSpec(
        name="r-audit-02",
        path=Path("docs/R-AUDIT-02-r1-r22-alignment-matrix.md"),
        kind="alignment_matrix",
        content_type="text/markdown",
        bk_r11_evidence_type="requirements-traceability-matrix",
    ),
    ArtifactSpec(
        name="r-rev-01",
        path=Path("docs/R-REV-01-corrected-r-series-baseline.md"),
        kind="corrected_baseline",
        content_type="text/markdown",
        bk_r11_evidence_type="baseline-correction-record",
    ),
    ArtifactSpec(
        name="r-series-alignment-report",
        path=Path("artifacts/r-series-alignment-report.json"),
        kind="r_series_alignment_report",
        content_type="application/json",
        bk_r11_evidence_type="machine-verifiable-alignment-report",
        schema_ref="schemas/architecture-baseline/r-series-alignment-report.schema.json",
    ),
)


RELEASE_ARTIFACTS: tuple[ArtifactSpec, ...] = (
    ArtifactSpec(
        name="release-verification-json",
        path=Path("artifacts/release-verification.json"),
        kind="release_verification",
        content_type="application/json",
        bk_r11_evidence_type="release-verification",
        schema_ref="schemas/release-artifacts/release-verification.schema.json",
    ),
    ArtifactSpec(
        name="release-verification-markdown",
        path=Path("artifacts/release-verification.md"),
        kind="release_verification_summary",
        content_type="text/markdown",
        bk_r11_evidence_type="human-review-summary",
    ),
    ArtifactSpec(
        name="release-verification-check",
        path=Path("artifacts/release-verification-check.json"),
        kind="release_verification_check",
        content_type="application/json",
        bk_r11_evidence_type="consistency-check",
        schema_ref="schemas/release-artifacts/release-verification-check.schema.json",
    ),
    ArtifactSpec(
        name="release-gate-evidence",
        path=Path("artifacts/gate-evidence.json"),
        kind="release_gate_evidence",
        content_type="application/json",
        bk_r11_evidence_type="gate-execution-evidence",
    ),
    *ARCHITECTURE_BASELINE_ARTIFACTS,
)


PRODUCTION_ARTIFACTS: tuple[ArtifactSpec, ...] = (
    ArtifactSpec(
        name="production-release-verification-json",
        path=Path("artifacts/production-release-verification.json"),
        kind="production_release_verification",
        content_type="application/json",
        bk_r11_evidence_type="production-release-verification",
        schema_ref="schemas/release-artifacts/release-verification.schema.json",
    ),
    ArtifactSpec(
        name="production-release-verification-markdown",
        path=Path("artifacts/production-release-verification.md"),
        kind="production_release_verification_summary",
        content_type="text/markdown",
        bk_r11_evidence_type="human-review-summary",
    ),
    ArtifactSpec(
        name="production-release-verification-check",
        path=Path("artifacts/production-release-verification-check.json"),
        kind="production_release_verification_check",
        content_type="application/json",
        bk_r11_evidence_type="consistency-check",
        schema_ref="schemas/release-artifacts/release-verification-check.schema.json",
    ),
    ArtifactSpec(
        name="production-readiness-contracts",
        path=Path("artifacts/production-readiness-contracts.json"),
        kind="production_readiness_contracts",
        content_type="application/json",
        bk_r11_evidence_type="readiness-contract-validation",
    ),
    ArtifactSpec(
        name="production-readiness",
        path=Path("artifacts/production-readiness.json"),
        kind="production_readiness",
        content_type="application/json",
        bk_r11_evidence_type="semantic-readiness-validation",
    ),
    ArtifactSpec(
        name="production-evidence-plan",
        path=Path("artifacts/production-evidence-plan.json"),
        kind="production_evidence_plan",
        content_type="application/json",
        bk_r11_evidence_type="readiness-remediation-plan",
    ),
    ArtifactSpec(
        name="production-evidence-status-json",
        path=Path("artifacts/production-evidence-status.json"),
        kind="production_evidence_status",
        content_type="application/json",
        bk_r11_evidence_type="readiness-status",
    ),
    ArtifactSpec(
        name="production-evidence-status-markdown",
        path=Path("artifacts/production-evidence-status.md"),
        kind="production_evidence_status_summary",
        content_type="text/markdown",
        bk_r11_evidence_type="human-review-summary",
    ),
    ArtifactSpec(
        name="release-gate-evidence",
        path=Path("artifacts/gate-evidence.json"),
        kind="release_gate_evidence",
        content_type="application/json",
        bk_r11_evidence_type="gate-execution-evidence",
    ),
    *ARCHITECTURE_BASELINE_ARTIFACTS,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(document: dict[str, Any]) -> str:
    payload = {key: value for key, value in document.items() if key != "bundle_hash"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _artifact_record(root: Path, spec: ArtifactSpec) -> dict[str, Any]:
    target = root / spec.path
    present = target.is_file()
    return {
        "name": spec.name,
        "path": str(spec.path),
        "kind": spec.kind,
        "required": True,
        "present": present,
        "sha256": _sha256(target) if present else None,
        "size_bytes": target.stat().st_size if present else None,
        "content_type": spec.content_type,
        "schema_ref": spec.schema_ref,
        "bk_r11_evidence_type": spec.bk_r11_evidence_type,
    }


def _ensure_derived_artifacts(root: Path, specs: tuple[ArtifactSpec, ...]) -> None:
    paths = {spec.path.as_posix() for spec in specs}
    if "artifacts/r-series-alignment-report.json" not in paths:
        return
    target = root / "artifacts" / "r-series-alignment-report.json"
    if not (root / "tools" / "r_series_alignment.py").is_file():
        return
    module = _load_r_series_alignment(root)
    report = module._report(module.build_alignment(root))
    _validate_alignment_report(root, module, report)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _validate_alignment_report(root: Path, module: Any, report: dict[str, Any]) -> None:
    expected_hash = module._stable_hash(
        {key: value for key, value in report.items() if key != "alignment_hash"}
    )
    if report.get("alignment_hash") != expected_hash:
        raise RuntimeError("R-series alignment report hash verification failed")
    schema_ref = report.get("schema_ref")
    if not isinstance(schema_ref, str):
        raise TypeError("R-series alignment report schema reference is missing")
    schema_path = root / schema_ref
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(report, schema)


def _load_r_series_alignment(root: Path) -> Any:
    module_name = "_release_evidence_bundle_r_series_alignment"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(
        module_name,
        root / "tools" / "r_series_alignment.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("r_series_alignment.py could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def build_manifest(
    root: Path,
    *,
    production: bool = False,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(UTC)
    specs = PRODUCTION_ARTIFACTS if production else RELEASE_ARTIFACTS
    _ensure_derived_artifacts(root, specs)
    artifacts = [_artifact_record(root, spec) for spec in specs]
    missing = [item["path"] for item in artifacts if item["required"] and not item["present"]]
    document: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at": generated_at.isoformat(),
        "bundle_type": "production" if production else "release",
        "status": "blocked" if missing else "complete",
        "artifacts": artifacts,
        "missing_artifacts": missing,
        "artifact_count": len(artifacts),
        "required_artifact_count": len([item for item in artifacts if item["required"]]),
        "present_artifact_count": len([item for item in artifacts if item["present"]]),
        "archive_policy": {
            "target_runtime": "BK/R11 evidence audit",
            "fail_closed_when_required_artifact_missing": True,
            "archive_only_when_status_complete": True,
            "schemas_are_recorded_when_available": True,
            "hash_algorithm": "sha256",
        },
        "next_action": (
            "Archive this bundle manifest and all listed artifacts with BK/R11."
            if not missing
            else "Generate the missing artifacts, then rebuild the evidence bundle manifest."
        ),
    }
    document["bundle_hash"] = _stable_hash(document)
    return document


def write_manifest(root: Path, output: Path, *, production: bool = False) -> dict[str, Any]:
    document = build_manifest(root, production=production)
    target = output if output.is_absolute() else root / output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return document


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write a BK/R11-ready release evidence bundle manifest."
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="artifacts/release-evidence-bundle.json")
    parser.add_argument("--production", action="store_true")
    args = parser.parse_args()

    document = write_manifest(
        Path(args.root).resolve(),
        Path(args.output),
        production=args.production,
    )
    print(json.dumps(document, sort_keys=True))
    return 0 if document["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
