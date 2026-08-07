import importlib.util
import json
import sys
from pathlib import Path

import jsonschema


def _load_roadmap_sequence_gate():
    root = Path(__file__).resolve().parents[3]
    tools = root / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    path = tools / "roadmap_sequence_gate.py"
    spec = importlib.util.spec_from_file_location("roadmap_sequence_gate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_roadmap_sequence_gate_passes_for_current_baseline() -> None:
    module = _load_roadmap_sequence_gate()
    root = Path(__file__).resolve().parents[3]

    report = module.verify_roadmap_sequence(root)
    schema = json.loads((root / module.SCHEMA_REF).read_text(encoding="utf-8"))

    assert report["status"] == "passed"
    assert report["r_range"] == "R2-R22"
    assert report["implementation_phase_range"] == "P12-P32"
    assert report["findings"] == []
    assert len(report["alignment_report_hash"]) == 64
    checks = {item["name"]: item for item in report["checks"]}
    assert checks["baseline-documents"]["status"] == "passed"
    assert checks["implementation-packages"]["status"] == "passed"
    assert checks["no-premature-r23"]["status"] == "passed"
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.validate(report, schema)


def test_roadmap_sequence_gate_fails_closed_for_premature_r23(tmp_path: Path) -> None:
    module = _load_roadmap_sequence_gate()
    root = Path(__file__).resolve().parents[3]
    report = module.verify_roadmap_sequence(root)

    # Minimal isolated tree for the explicit R23 policy check.
    forbidden = tmp_path / "1" / "r23.txt"
    forbidden.parent.mkdir(parents=True)
    forbidden.write_text("R23 premature module", encoding="utf-8")
    findings: list = []
    check = module._check_no_premature_r23(tmp_path, findings)

    assert report["status"] == "passed"
    assert check["status"] == "failed"
    assert findings[0].check == "no-premature-r23"
    assert "R23 artifact exists before an ADR-backed post-R22 module decision" in (
        findings[0].message
    )


def test_roadmap_sequence_gate_fails_closed_when_report_schema_validation_fails(
    monkeypatch,
) -> None:
    module = _load_roadmap_sequence_gate()
    root = Path(__file__).resolve().parents[3]
    original_schema = module._schema

    def stricter_schema(path: Path) -> dict:
        schema = original_schema(path)
        return {**schema, "required": [*schema["required"], "impossible_field"]}

    monkeypatch.setattr(module, "_schema", stricter_schema)

    try:
        module.verify_roadmap_sequence(root)
    except RuntimeError as exc:
        assert module.SCHEMA_REF in str(exc)
        assert "generated roadmap sequence gate report does not validate" in str(exc)
    else:
        raise AssertionError("invalid roadmap sequence gate report was accepted")
