import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_enterprise.domain.aepm import AepmManifest

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / "examples/sample-project/aepm-0.1.json"
SCHEMA = ROOT / "specifications/aepm/AEPM-0.1.schema.json"


def test_sample_manifest_is_a_complete_immutable_aepm_contract() -> None:
    manifest = AepmManifest.model_validate_json(EXAMPLE.read_text(encoding="utf-8"))

    assert manifest.schema_version == "aepm-0.1"
    assert manifest.project_intent.name == "Service Request Portal"
    assert manifest.business_outcomes[0].id == "OUT-001"
    assert manifest.capabilities[0].owner_stakeholder_id == "STK-001"
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
    expected = {
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

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert set(schema["required"]) == expected
    assert set(schema["properties"]) == expected
    assert schema["additionalProperties"] is False
