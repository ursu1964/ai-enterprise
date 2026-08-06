import importlib.util
import json
import sys
from pathlib import Path

import jsonschema


def _load_bk_roadmap_audit():
    root = Path(__file__).resolve().parents[3]
    path = root / "tools" / "bk_roadmap_audit.py"
    spec = importlib.util.spec_from_file_location("bk_roadmap_audit", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_bk_roadmap_audit_reports_bk_evidence_and_canonical_ir_specs() -> None:
    module = _load_bk_roadmap_audit()
    root = Path(__file__).resolve().parents[3]

    report = module.audit_bk_roadmap(root, Path("1/bk.txt"))

    assert report["status"] == "pass"
    assert report["schema_ref"] == (
        "schemas/architecture-baseline/bk-roadmap-audit-report.schema.json"
    )
    assert report["documents_detected"] == ["R10-IR-01"]
    canonical = {item["document_id"]: item for item in report["canonical_specifications"]}
    assert canonical["R10-IR-01"]["status"] == "canonical_ir_specification"
    assert canonical["R11-IR-01"]["status"] == "canonical_ir_specification"
    assert report["derived_specifications"][0]["document_id"] == "R11-IR-01"
    assert (
        report["derived_specifications"][0]["status"] == "superseded_by_canonical_ir_specification"
    )
    assert report["referenced_next_specification"] == {
        "document_id": "R11-IR-01",
        "title": "Evidence and Audit Engine",
        "resolution": "already_canonical_and_implemented",
    }
    assert report["next_required_specification"] is None
    assert report["gaps"] == []
    assert len(report["source_hash"]) == 64
    assert len(report["audit_hash"]) == 64
    modules = {item["module"]: item for item in report["implemented_modules"]}
    assert modules["BK-R10"]["complete"] is True
    assert modules["BK-R10"]["missing_paths"] == []
    assert modules["BK-R11"]["complete"] is True
    assert modules["BK-R11"]["missing_paths"] == []
    schema = json.loads(
        (
            root / "schemas" / "architecture-baseline" / "bk-roadmap-audit-report.schema.json"
        ).read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(report, schema)


def test_bk_roadmap_audit_blocks_when_required_evidence_is_missing(tmp_path: Path) -> None:
    module = _load_bk_roadmap_audit()
    source = tmp_path / "bk.txt"
    source.write_text(
        "\n".join(
            [
                "Document ID: R10-IR-01",
                "The next required specification is R11-IR-01 — Evidence and Audit Engine.",
            ]
        ),
        encoding="utf-8",
    )

    report = module.audit_bk_roadmap(tmp_path, source)

    assert report["status"] == "blocked"
    assert "BK-R10_IMPLEMENTATION_EVIDENCE_MISSING" in report["gaps"]
    assert "BK-R11_IMPLEMENTATION_EVIDENCE_MISSING" in report["gaps"]
    assert "BK_NEXT_CANONICAL_SPEC_BODY_MISSING" in report["gaps"]
    assert report["referenced_next_specification"] == {
        "document_id": "R11-IR-01",
        "title": "Evidence and Audit Engine",
        "resolution": "canonical_specification_missing",
    }
    assert report["next_required_specification"] == {
        "document_id": "R11-IR-01",
        "title": "Evidence and Audit Engine",
    }
    assert report["implemented_modules"][0]["complete"] is False


def test_bk_roadmap_audit_has_ci_friendly_json_output(capsys) -> None:
    module = _load_bk_roadmap_audit()
    root = Path(__file__).resolve().parents[3]

    assert module.main(["--root", str(root), "--source", "1/bk.txt", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == "1.0"
    assert output["status"] == "pass"


def test_bk_roadmap_audit_fails_closed_when_report_schema_validation_fails(monkeypatch) -> None:
    module = _load_bk_roadmap_audit()
    root = Path(__file__).resolve().parents[3]
    original_schema = module._schema

    def stricter_schema() -> dict:
        schema = original_schema()
        return {**schema, "required": [*schema["required"], "impossible_field"]}

    monkeypatch.setattr(module, "_schema", stricter_schema)

    try:
        module.audit_bk_roadmap(root, Path("1/bk.txt"))
    except RuntimeError as exc:
        assert module.SCHEMA_REF in str(exc)
        assert "generated BK roadmap audit report does not validate" in str(exc)
    else:
        raise AssertionError("invalid BK roadmap audit report was accepted")
