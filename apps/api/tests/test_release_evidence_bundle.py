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
    _copy_schema_refs(tmp_path, release_evidence_bundle.RELEASE_ARTIFACTS)
    release_payload = _release_verification_payload()
    release_rendered = json.dumps(release_payload, sort_keys=True) + "\n"
    _write(tmp_path / "artifacts" / "release-verification.json", release_rendered)
    _write(tmp_path / "artifacts" / "release-verification.md", "# Release\n")
    _write(
        tmp_path / "artifacts" / "release-verification-check.json",
        json.dumps(_release_verification_check_payload(), sort_keys=True) + "\n",
    )
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
    assert verification["sha256"] == hashlib.sha256(release_rendered.encode()).hexdigest()
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
    _copy_schema_refs(tmp_path, release_evidence_bundle.PRODUCTION_ARTIFACTS)
    for spec in release_evidence_bundle.PRODUCTION_ARTIFACTS:
        if spec.name == "production-release-verification-json":
            _write(
                tmp_path / spec.path,
                json.dumps(_release_verification_payload(production=True), sort_keys=True) + "\n",
            )
        elif spec.name == "production-release-verification-check":
            _write(
                tmp_path / spec.path,
                json.dumps(_release_verification_check_payload(), sort_keys=True) + "\n",
            )
        elif spec.name == "production-readiness-contracts":
            _write(
                tmp_path / spec.path,
                json.dumps(_production_readiness_contracts_payload(), sort_keys=True) + "\n",
            )
        elif spec.name == "production-readiness":
            _write(
                tmp_path / spec.path,
                json.dumps(_production_readiness_payload(), sort_keys=True) + "\n",
            )
        elif spec.name == "production-evidence-plan":
            _write(
                tmp_path / spec.path,
                json.dumps(_production_evidence_plan_payload(), sort_keys=True) + "\n",
            )
        elif spec.name == "production-evidence-status-json":
            _write(
                tmp_path / spec.path,
                json.dumps(_production_evidence_status_payload(), sort_keys=True) + "\n",
            )
        elif spec.name == "r-series-alignment-report":
            _write(
                tmp_path / spec.path,
                json.dumps(_alignment_report_payload(), sort_keys=True) + "\n",
            )
        else:
            _write(tmp_path / spec.path, f"{spec.name}\n")

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
    assert artifacts["artifacts/production-readiness-contracts.json"]["schema_ref"] == (
        "schemas/production-readiness/production-readiness-contracts-report.schema.json"
    )
    assert artifacts["artifacts/production-readiness.json"]["schema_ref"] == (
        "schemas/production-readiness/production-readiness-report.schema.json"
    )
    assert artifacts["artifacts/production-evidence-plan.json"]["schema_ref"] == (
        "schemas/production-readiness/production-evidence-plan.schema.json"
    )
    assert artifacts["artifacts/production-evidence-status.json"]["schema_ref"] == (
        "schemas/production-readiness/production-evidence-status.schema.json"
    )
    assert artifacts["artifacts/production-release-verification.json"]["schema_ref"] == (
        "schemas/release-artifacts/release-verification.schema.json"
    )
    assert (
        artifacts["artifacts/production-release-verification-check.json"]["schema_ref"]
        == "schemas/release-artifacts/release-verification-check.schema.json"
    )
    jsonschema.validate(document, SCHEMA)


def test_release_evidence_bundle_rejects_invalid_schema_backed_artifact(
    tmp_path: Path,
) -> None:
    _copy_schema_refs(tmp_path, release_evidence_bundle.RELEASE_ARTIFACTS)
    _write(tmp_path / "artifacts" / "release-verification.json", '{"status":"passed"}\n')
    _write(tmp_path / "artifacts" / "release-verification.md", "# Release\n")
    _write(
        tmp_path / "artifacts" / "release-verification-check.json",
        json.dumps(_release_verification_check_payload(), sort_keys=True) + "\n",
    )
    _write(tmp_path / "artifacts" / "gate-evidence.json", '{"gates":{}}\n')
    _write_architecture_artifacts(tmp_path)

    try:
        release_evidence_bundle.build_manifest(
            tmp_path,
            generated_at=datetime(2026, 8, 6, tzinfo=UTC),
        )
    except RuntimeError as exc:
        assert "release-verification.json does not validate" in str(exc)
    else:
        raise AssertionError("invalid schema-backed release artifact was accepted")


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
    report_path = root / "artifacts" / "r-series-alignment-report.json"
    assert report_path.is_file()
    assert json.loads(report_path.read_text(encoding="utf-8"))["reconciliation_verdict"] == (
        "complete"
    )


def test_release_evidence_bundle_regenerates_stale_alignment_report() -> None:
    root = _repo_root()
    report_path = root / "artifacts" / "r-series-alignment-report.json"
    previous = report_path.read_text(encoding="utf-8") if report_path.exists() else None
    try:
        _write(report_path, '{"schema_version":"stale"}\n')
        release_evidence_bundle.build_manifest(
            root,
            generated_at=datetime(2026, 8, 6, tzinfo=UTC),
        )
        regenerated = json.loads(report_path.read_text(encoding="utf-8"))
        assert regenerated["schema_version"] == "1.0"
        assert regenerated["reconciliation_verdict"] == "complete"
    finally:
        if previous is not None:
            report_path.write_text(previous, encoding="utf-8")


def test_release_evidence_bundle_rejects_invalid_generated_alignment_hash(
    monkeypatch,
) -> None:
    root = _repo_root()
    module = release_evidence_bundle._load_r_series_alignment(root)
    original_report = module._report

    def broken_report(alignments):
        report = original_report(alignments)
        return {**report, "alignment_hash": "0" * 64}

    monkeypatch.setattr(module, "_report", broken_report)

    try:
        try:
            release_evidence_bundle.build_manifest(
                root,
                generated_at=datetime(2026, 8, 6, tzinfo=UTC),
            )
        except RuntimeError as exc:
            assert "hash verification failed" in str(exc)
        else:
            raise AssertionError("invalid generated alignment hash was accepted")
    finally:
        monkeypatch.setattr(module, "_report", original_report)


def _write_architecture_artifacts(root: Path) -> None:
    _write(root / "docs" / "ARCHITECTURE-BASELINE-v1.0.md", "# Baseline\n")
    _write(root / "docs" / "R-AUDIT-01-current-state-repository-audit.md", "# Audit 01\n")
    _write(root / "docs" / "R-AUDIT-02-r1-r22-alignment-matrix.md", "# Audit 02\n")
    _write(root / "docs" / "R-REV-01-corrected-r-series-baseline.md", "# Rev 01\n")
    _write(
        root / "artifacts" / "r-series-alignment-report.json",
        json.dumps(_alignment_report_payload(), sort_keys=True) + "\n",
    )


def _copy_schema_refs(root: Path, specs: tuple[release_evidence_bundle.ArtifactSpec, ...]) -> None:
    repo = _repo_root()
    for spec in specs:
        if spec.schema_ref is None:
            continue
        source = repo / spec.schema_ref
        target = root / spec.schema_ref
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def _release_verification_payload(*, production: bool = False) -> dict:
    return {
        "schema_version": "1.0",
        "generated_at": "2026-08-06T00:00:00+00:00",
        "status": "passed",
        "release_environment": "production" if production else "non-production",
        "production_readiness_contracts": {} if production else None,
        "production_readiness": {} if production else None,
        "production_evidence_plan": {} if production else None,
        "git": {
            "commit": "a" * 40,
            "tree": "b" * 40,
            "branch": "main",
            "dirty": False,
        },
        "gates": [],
        "gate_summary": {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "captured_evidence_required": [],
            "captured_evidence_missing": [],
            "execution_model": "test fixture",
        },
        "gate_evidence_file": {},
        "migration_verification": {},
        "artifact_policy": {},
        "artifact_hash": "c" * 64,
    }


def _release_verification_check_payload() -> dict:
    return {
        "schema_version": "1.0",
        "status": "valid",
        "valid": True,
        "json_path": "artifacts/release-verification.json",
        "markdown_path": "artifacts/release-verification.md",
        "stored_artifact_hash": "d" * 64,
        "recomputed_artifact_hash": "d" * 64,
        "findings": [],
        "next_action": "Archive JSON and Markdown together.",
    }


def _production_readiness_contracts_payload() -> dict:
    return {
        "schema_version": "1.0",
        "status": "valid",
        "conformant": True,
        "checks": [
            {
                "name": "infrastructure_decisions",
                "path": "docs/enterprise/real-world-infrastructure-decisions.json",
                "schema": "infrastructure-decisions.schema.json",
                "status": "valid",
                "findings": [],
            },
            {
                "name": "production_evidence",
                "path": "docs/enterprise/production-readiness-evidence.json",
                "schema": "production-evidence.schema.json",
                "status": "valid",
                "findings": [],
            },
        ],
        "findings": [],
        "next_action": "Run rtk make production-readiness for semantic validation.",
    }


def _production_readiness_payload() -> dict:
    return {
        "schema_version": "1.0",
        "status": "blocked",
        "production_allowed": False,
        "environment": "production",
        "reviewed_by": "release-owner",
        "evidence_file": "docs/enterprise/production-readiness-evidence.json",
        "choices": {},
        "checks": [
            {
                "name": "tls",
                "status": "blocked",
                "checked_at": None,
                "valid_until": None,
                "evidence": None,
                "findings": ["proof record is missing"],
            }
        ],
        "findings": ["tls: proof record is missing"],
        "next_action": "Complete every blocked proof and rerun make production-readiness.",
    }


def _production_evidence_plan_payload() -> dict:
    payload = {
        "schema_version": "1.0",
        "generated_at": "2026-08-06T00:00:00Z",
        "status": "blocked",
        "production_allowed": False,
        "evidence_file": "docs/enterprise/production-readiness-evidence.json",
        "choices_file": "docs/enterprise/real-world-infrastructure-decisions.json",
        "proof_requirements": [],
        "infrastructure_choice_requirements": [],
        "readiness_findings": ["tls: proof record is missing"],
        "validation_commands": ["rtk make production-readiness"],
        "next_action": "Assign blocked proof items to real owners.",
        "readiness_report": {
            "status": "blocked",
            "production_allowed": False,
            "choices_status": "invalid",
            "choices_conformant": False,
        },
    }
    return {
        **payload,
        "plan_hash": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
    }


def _production_evidence_status_payload() -> dict:
    return {
        "schema_version": "1.0",
        "status": "blocked",
        "production_allowed": False,
        "evidence_file": "docs/enterprise/production-readiness-evidence.json",
        "choices_file": "docs/enterprise/real-world-infrastructure-decisions.json",
        "blocked_proof_count": 1,
        "blocked_choice_count": 0,
        "blocked_proofs": [
            {
                "name": "tls",
                "owner_hint": "platform owner",
                "current_status": "missing",
                "findings": ["proof record is missing"],
                "action": "Run the TLS/certificate probe and archive the endpoint evidence.",
            }
        ],
        "blocked_choices": [],
        "readiness_finding_count": 1,
        "next_commands": ["rtk make production-readiness"],
        "next_action": "Assign blocked proof items to real owners.",
    }


def _alignment_report_payload() -> dict:
    packages = [
        {
            "r": f"R{number}",
            "p_phase": f"P{number + 10}",
            "title": f"R{number}",
            "spec_path": f"1/r{number}.txt",
            "spec_hash": "0" * 64,
            "package_path": f"implementation/r{number:02d}",
            "complete": True,
            "capabilities": [
                {"category": category, "status": "implemented", "evidence_count": 1}
                for category in (
                    "source_specification",
                    "domain_or_runtime",
                    "api_contract",
                    "api_route",
                    "persistence_or_migration",
                    "schema_or_registry",
                    "tests",
                    "status_documentation",
                )
            ],
        }
        for number in range(2, 23)
    ]
    payload = {
        "schema_version": "1.0",
        "schema_ref": "schemas/architecture-baseline/r-series-alignment-report.schema.json",
        "r_range": "R2-R22",
        "package_count": 21,
        "complete_count": 21,
        "incomplete": [],
        "capability_area_count": 168,
        "reconciled_capability_area_count": 168,
        "evidence_reference_count": 168,
        "reconciliation_verdict": "complete",
        "ir_specification_count": 21,
        "ir_specifications": [
            {
                "document_id": f"R{number:02d}-IR-01",
                "title": f"R{number} IR",
                "path": f"docs/ir/R{number:02d}-IR-01-test.md",
            }
            for number in range(2, 23)
        ],
        "packages": packages,
    }
    return {
        **payload,
        "alignment_hash": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
    }
