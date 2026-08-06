import hashlib
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import jsonschema


def _repo_root() -> Path:
    for candidate in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
        if (candidate / "tools").is_dir():
            return candidate
    raise AssertionError("Could not locate repository root with tools directory")


def _load(name: str):
    root = _repo_root()
    spec = importlib.util.spec_from_file_location(name, root / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


release_evidence_bundle = _load("release_evidence_bundle")
SCHEMA = json.loads(
    (
        _repo_root() / "schemas" / "release-artifacts" / "release-evidence-bundle.schema.json"
    ).read_text(encoding="utf-8")
)


def _write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def test_release_evidence_bundle_records_hashes_and_schema_references(tmp_path: Path) -> None:
    _write(tmp_path / "artifacts" / "release-verification.json", '{"status":"passed"}\n')
    _write(tmp_path / "artifacts" / "release-verification.md", "# Release\n")
    _write(tmp_path / "artifacts" / "release-verification-check.json", '{"valid":true}\n')
    _write(tmp_path / "artifacts" / "gate-evidence.json", '{"gates":{}}\n')
    _write_architecture_artifacts(tmp_path)

    document = release_evidence_bundle.build_manifest(
        tmp_path,
        generated_at=datetime(2026, 8, 6, tzinfo=UTC),
    )

    assert document["schema_version"] == "1.0"
    assert document["bundle_type"] == "release"
    assert document["status"] == "complete"
    assert document["missing_artifacts"] == []
    assert document["artifact_count"] == 9
    assert document["present_artifact_count"] == 9
    assert len(document["bundle_hash"]) == 64
    artifacts = {item["name"]: item for item in document["artifacts"]}
    verification = artifacts["release-verification-json"]
    assert verification["schema_ref"] == (
        "schemas/release-artifacts/release-verification.schema.json"
    )
    assert verification["bk_r11_evidence_type"] == "release-verification"
    assert verification["sha256"] == hashlib.sha256(b'{"status":"passed"}\n').hexdigest()
    assert artifacts["release-verification-markdown"]["schema_ref"] is None
    alignment = artifacts["r-series-alignment-report"]
    assert alignment["schema_ref"] == (
        "schemas/architecture-baseline/r-series-alignment-report.schema.json"
    )
    assert alignment["bk_r11_evidence_type"] == "machine-verifiable-alignment-report"
    assert artifacts["architecture-baseline-v1"]["bk_r11_evidence_type"] == (
        "architecture-baseline-freeze-candidate"
    )
    assert document["archive_policy"] == {
        "target_runtime": "BK/R11 evidence audit",
        "fail_closed_when_required_artifact_missing": True,
        "archive_only_when_status_complete": True,
        "schemas_are_recorded_when_available": True,
        "hash_algorithm": "sha256",
    }
    jsonschema.validate(document, SCHEMA)


def test_release_evidence_bundle_blocks_when_required_artifact_is_missing(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "artifacts" / "release-verification.json", "{}\n")

    document = release_evidence_bundle.build_manifest(
        tmp_path,
        generated_at=datetime(2026, 8, 6, tzinfo=UTC),
    )

    assert document["status"] == "blocked"
    assert document["present_artifact_count"] == 1
    assert document["missing_artifacts"] == [
        "artifacts/release-verification.md",
        "artifacts/release-verification-check.json",
        "artifacts/gate-evidence.json",
        "docs/ARCHITECTURE-BASELINE-v1.0.md",
        "docs/R-AUDIT-01-current-state-repository-audit.md",
        "docs/R-AUDIT-02-r1-r22-alignment-matrix.md",
        "docs/R-REV-01-corrected-r-series-baseline.md",
        "artifacts/r-series-alignment-report.json",
    ]
    missing = [
        item for item in document["artifacts"] if item["path"] in document["missing_artifacts"]
    ]
    assert all(item["sha256"] is None for item in missing)
    assert all(item["size_bytes"] is None for item in missing)
    assert "Generate the missing artifacts" in document["next_action"]
    jsonschema.validate(document, SCHEMA)


def test_production_evidence_bundle_includes_readiness_and_status_outputs(
    tmp_path: Path,
) -> None:
    for spec in release_evidence_bundle.PRODUCTION_ARTIFACTS:
        if spec.name != "r-series-alignment-report":
            _write(tmp_path / spec.path, f"{spec.name}\n")
    _write(tmp_path / "artifacts" / "r-series-alignment-report.json", "{}\n")

    document = release_evidence_bundle.build_manifest(
        tmp_path,
        production=True,
        generated_at=datetime(2026, 8, 6, tzinfo=UTC),
    )

    assert document["bundle_type"] == "production"
    assert document["status"] == "complete"
    assert document["artifact_count"] == 14
    assert document["missing_artifacts"] == []
    artifacts = {item["path"]: item for item in document["artifacts"]}
    assert "artifacts/production-readiness-contracts.json" in artifacts
    assert "artifacts/production-readiness.json" in artifacts
    assert "artifacts/production-evidence-plan.json" in artifacts
    assert "artifacts/production-evidence-status.json" in artifacts
    assert "artifacts/production-evidence-status.md" in artifacts
    assert "docs/ARCHITECTURE-BASELINE-v1.0.md" in artifacts
    assert "artifacts/r-series-alignment-report.json" in artifacts
    assert artifacts["artifacts/production-release-verification.json"]["schema_ref"] == (
        "schemas/release-artifacts/release-verification.schema.json"
    )
    assert (
        artifacts["artifacts/production-release-verification-check.json"]["schema_ref"]
        == "schemas/release-artifacts/release-verification-check.schema.json"
    )
    jsonschema.validate(document, SCHEMA)


def test_write_manifest_returns_non_complete_document_when_artifacts_missing(
    tmp_path: Path,
) -> None:
    output = tmp_path / "artifacts" / "release-evidence-bundle.json"

    document = release_evidence_bundle.write_manifest(tmp_path, output)

    assert document["status"] == "blocked"
    assert output.is_file()
    assert json.loads(output.read_text(encoding="utf-8"))["bundle_hash"] == document["bundle_hash"]


def test_release_evidence_bundle_derives_alignment_report_without_rewriting_docs(
    tmp_path: Path,
) -> None:
    root = _repo_root()
    for spec in release_evidence_bundle.RELEASE_ARTIFACTS:
        if spec.name in {
            "release-verification-json",
            "release-verification-markdown",
            "release-verification-check",
            "release-gate-evidence",
        }:
            _write(tmp_path / spec.path, spec.name + "\n")
        elif spec.name != "r-series-alignment-report":
            source = root / spec.path
            target = tmp_path / spec.path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    # The derivation needs the real repository structure but should write only the
    # ignored report artifact under artifacts/.
    document = release_evidence_bundle.build_manifest(
        root,
        generated_at=datetime(2026, 8, 6, tzinfo=UTC),
    )

    artifacts = {item["name"]: item for item in document["artifacts"]}
    assert artifacts["r-series-alignment-report"]["present"] is True
    assert (root / "artifacts" / "r-series-alignment-report.json").is_file()


def _write_architecture_artifacts(root: Path) -> None:
    _write(root / "docs" / "ARCHITECTURE-BASELINE-v1.0.md", "# Baseline\n")
    _write(root / "docs" / "R-AUDIT-01-current-state-repository-audit.md", "# Audit 01\n")
    _write(root / "docs" / "R-AUDIT-02-r1-r22-alignment-matrix.md", "# Audit 02\n")
    _write(root / "docs" / "R-REV-01-corrected-r-series-baseline.md", "# Rev 01\n")
    _write(root / "artifacts" / "r-series-alignment-report.json", "{}\n")
