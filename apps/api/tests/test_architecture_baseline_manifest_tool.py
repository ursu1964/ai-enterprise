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


def _load_architecture_baseline_manifest():
    root = _repo_root()
    spec = importlib.util.spec_from_file_location(
        "architecture_baseline_manifest",
        root / "tools" / "architecture_baseline_manifest.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_architecture_baseline_manifest_freezes_current_artifact_set() -> None:
    module = _load_architecture_baseline_manifest()
    root = _repo_root()

    manifest = module.build_manifest(root, now=datetime(2026, 8, 7, tzinfo=UTC))
    repeated = module.build_manifest(root, now=datetime(2026, 8, 7, 1, tzinfo=UTC))
    schema = json.loads((root / module.SCHEMA_REF).read_text(encoding="utf-8"))

    assert manifest["status"] == "frozen"
    assert manifest["baseline_id"] == "AEB-1.0"
    assert manifest["baseline_version"] == "1.0.0"
    assert manifest["scope"]["requirements"] == {"first": "R1", "last": "R22", "count": 22}
    assert manifest["governance"]["direct_modification"] == "prohibited"
    assert manifest["implementation"]["first_slice"] == "P12"
    assert manifest["future_modules"]["R23"]["allowed"] is False
    assert manifest["artifact_count"] == 49
    assert manifest["findings"] == []
    assert len(manifest["root_hash"]["value"]) == 64
    assert manifest["root_hash"] == repeated["root_hash"]

    artifacts = {item["id"]: item for item in manifest["artifacts"]}
    assert artifacts["R1"]["source_path"] == "1/r1.txt"
    assert artifacts["R22"]["source_path"] == "1/r22.txt"
    assert artifacts["R-INDEX"]["type"] == "control_artifact"
    assert artifacts["AEB-1.0"]["source_path"] == "docs/ARCHITECTURE-BASELINE-v1.0.md"
    assert artifacts["ADR-0007"]["type"] == "governance_adr"
    assert artifacts["P12-R2-CLAUSE-VERIFICATION"]["source_path"] == (
        "implementation/r02/clause-verification.md"
    )
    assert artifacts["P32-R22-CLAUSE-VERIFICATION"]["source_path"] == (
        "implementation/r22/clause-verification.md"
    )
    assert all(item["content_hash"]["algorithm"] == "SHA-256" for item in artifacts.values())

    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(manifest, schema)


def test_architecture_baseline_manifest_fails_closed_when_artifact_missing(
    tmp_path: Path,
) -> None:
    module = _load_architecture_baseline_manifest()
    root = _repo_root()

    for spec in module._artifact_specs():
        source = root / spec.path
        target = tmp_path / spec.path
        if spec.artifact_id == "R2" or not source.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

    schema_source = root / module.SCHEMA_REF
    schema_target = tmp_path / module.SCHEMA_REF
    schema_target.parent.mkdir(parents=True, exist_ok=True)
    schema_target.write_text(schema_source.read_text(encoding="utf-8"), encoding="utf-8")

    manifest = module.build_manifest(tmp_path, now=datetime(2026, 8, 7, tzinfo=UTC))

    assert manifest["status"] == "incomplete"
    assert manifest["findings"] == [
        {
            "severity": "critical",
            "message": "Required baseline artifact is missing",
            "path": "1/r2.txt",
        }
    ]
    artifacts = {item["id"]: item for item in manifest["artifacts"]}
    assert artifacts["R2"]["status"] == "missing"
    assert "Restore every missing baseline artifact" in manifest["next_action"]
