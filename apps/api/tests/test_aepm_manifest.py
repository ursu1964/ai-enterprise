import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_enterprise.domain.aepm import AepmManifest

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / "examples/sample-project/aepm-0.1.json"
INVALID_EXAMPLE = ROOT / "examples/sample-project/aepm-0.1.invalid.json"
SCHEMA = ROOT / "specifications/aepm/AEPM-0.1.schema.json"


def test_sample_manifest_is_a_complete_immutable_aepm_contract() -> None:
    manifest = AepmManifest.model_validate_json(EXAMPLE.read_text(encoding="utf-8"))

    assert manifest.schema_version == "aepm-0.1"
    assert manifest.aepm_version == "0.1"
    assert manifest.project_intent.id == "PRJ-001"
    assert manifest.project_intent.name == "Service Request Portal"
    assert manifest.project_intent.source_refs == ()
    assert manifest.business_outcomes[0].id == "OUT-001"
    assert manifest.capabilities[0].owner_stakeholder_id == "STK-001"
    assert manifest.stakeholders[0].decision_authority is False
    assert manifest.extensions == {}
    with pytest.raises(ValidationError, match="frozen"):
        manifest.project_intent.name = "Changed"


def test_manifest_rejects_unknown_fields_and_invalid_identifiers() -> None:
    document = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    document["enterprise_ontology"] = {}
    document["capabilities"][0]["id"] = "capability-1"

    with pytest.raises(ValidationError) as raised:
        AepmManifest.model_validate(document)

    messages = str(raised.value)
    assert "Extra inputs are not permitted" in messages
    assert "String should match pattern" in messages


def test_normative_schema_declares_only_the_v01_manifest_surface() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "project_intent",
        "business_outcomes",
        "stakeholders",
        "capabilities",
        "core_processes",
        "business_rules",
        "data_entities",
        "integrations",
        "quality_requirements",
        "constraints",
        "preferred_technology_targets",
    }
    optional = {"aepm_version", "extensions"}

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert set(schema["required"]) == required
    assert set(schema["properties"]) == required | optional
    assert schema["additionalProperties"] is False
    assert schema["properties"]["aepm_version"]["const"] == "0.1"
    assert "compatibility" in schema["x-compatibility_policy"].lower()
    assert schema["$defs"]["project_intent"]["properties"]["id"]["pattern"] == "^PRJ-[0-9]{3}$"
    assert "source_refs" in schema["$defs"]["project_intent"]["properties"]
    assert "source_refs" in schema["$defs"]["business_outcome"]["properties"]
    assert schema["$defs"]["stakeholder"]["properties"]["decision_authority"] == {
        "type": "boolean",
        "default": False,
    }


def test_invalid_sample_manifest_exercises_deterministic_r2_findings() -> None:
    from ai_enterprise.domain.aepm_validation import AepmValidationEngine

    document = json.loads(INVALID_EXAMPLE.read_text(encoding="utf-8"))
    report = AepmValidationEngine().validate(document)

    assert report.valid is False
    assert {finding.category for finding in report.findings} >= {
        "ambiguity",
        "completeness",
        "consistency",
        "duplication",
        "governance",
        "quality",
        "security",
        "traceability",
    }
