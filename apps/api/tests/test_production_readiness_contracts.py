import importlib.util
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = ROOT / "schemas" / "production-readiness"
ENTERPRISE_DIR = ROOT / "docs" / "enterprise"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


production_readiness_contracts = _load("production_readiness_contracts")
infrastructure_choices = _load("infrastructure_choices")
production_readiness = _load("production_readiness")


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def test_production_readiness_schema_files_are_valid_json_schema_documents() -> None:
    for schema_path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        assert schema["$id"].startswith("https://ai-enterprise.local/schemas/production-readiness/")


def test_infrastructure_decisions_template_and_draft_match_schema() -> None:
    schema = _load_schema("infrastructure-decisions.schema.json")
    paths = [
        ENTERPRISE_DIR / "real-world-infrastructure-decisions.template.json",
        ENTERPRISE_DIR / "real-world-infrastructure-decisions.json",
    ]

    for path in paths:
        if path.exists():
            jsonschema.validate(json.loads(path.read_text(encoding="utf-8")), schema)


def test_production_evidence_template_and_draft_match_schema() -> None:
    schema = _load_schema("production-evidence.schema.json")
    paths = [
        ENTERPRISE_DIR / "production-readiness-evidence.template.json",
        ENTERPRISE_DIR / "production-readiness-evidence.json",
    ]

    for path in paths:
        if path.exists():
            jsonschema.validate(json.loads(path.read_text(encoding="utf-8")), schema)


def test_runtime_contract_validator_reports_schema_findings() -> None:
    findings = production_readiness_contracts.validate_infrastructure_decisions(
        {"domain_tls": {"domain": "example"}}
    )

    assert findings
    assert any("required property" in item for item in findings)


def test_contract_cli_report_is_valid_for_current_templates() -> None:
    report = production_readiness_contracts.verify_files(
        choices_file=ENTERPRISE_DIR / "real-world-infrastructure-decisions.template.json",
        evidence_file=ENTERPRISE_DIR / "production-readiness-evidence.template.json",
    )

    assert report["conformant"] is True
    assert report["status"] == "valid"
    assert report["next_action"] == "Run rtk make production-readiness for semantic validation."


def test_infrastructure_choices_fail_before_semantics_when_shape_is_invalid(tmp_path: Path) -> None:
    path = tmp_path / "choices.json"
    path.write_text(json.dumps({"domain_tls": {"domain": "example"}}), encoding="utf-8")

    report = infrastructure_choices.verify(path)

    assert report["conformant"] is False
    assert report["summary"] == "Infrastructure choices file does not match the published schema."
    assert any(item.startswith("schema:") for item in report["findings"])


def test_production_readiness_reports_evidence_schema_findings(tmp_path: Path) -> None:
    choices = json.loads(
        (ENTERPRISE_DIR / "real-world-infrastructure-decisions.template.json").read_text(
            encoding="utf-8"
        )
    )
    (tmp_path / "choices.json").write_text(json.dumps(choices), encoding="utf-8")
    (tmp_path / "evidence.json").write_text(
        json.dumps({"environment": "production", "reviewed_by": "owner", "proof": {}}),
        encoding="utf-8",
    )

    report = production_readiness.verify(
        tmp_path,
        Path("evidence.json"),
        Path("choices.json"),
    )

    assert report["production_allowed"] is False
    assert any(item.startswith("evidence_schema:") for item in report["findings"])


def test_contract_cli_report_blocks_invalid_input_files(tmp_path: Path) -> None:
    choices = tmp_path / "choices.json"
    evidence = tmp_path / "evidence.json"
    choices.write_text(json.dumps({"domain_tls": {"domain": "example"}}), encoding="utf-8")
    evidence.write_text("[]", encoding="utf-8")

    report = production_readiness_contracts.verify_files(
        choices_file=choices,
        evidence_file=evidence,
    )

    assert report["conformant"] is False
    assert report["status"] == "invalid"
    assert any("infrastructure_decisions:" in item for item in report["findings"])
    assert any("production_evidence:" in item for item in report["findings"])
