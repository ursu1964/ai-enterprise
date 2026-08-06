from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from ai_enterprise.application.r14_manifest_schema_runtime import (
    SCHEMA_VERSION,
    r14_manifest_schema,
    r14_manifest_schema_contract,
    r14_validate_manifest,
    r14_validate_manifest_evolution,
)
from ai_enterprise.main import app

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = ROOT / "schemas" / "Manifest.schema.json"
VALID = ROOT / "manifest" / "crm.r14.json"
INVALID = ROOT / "manifest" / "invalid-technical.r14.json"
REGISTRY = ROOT / "registry"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_r14_manifest_schema_is_executable_json_schema() -> None:
    schema = r14_manifest_schema(SCHEMA)

    Draft202012Validator.check_schema(schema)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["version"]["properties"]["schemaVersion"]["const"] == (
        SCHEMA_VERSION
    )
    assert {
        "metadata",
        "organization",
        "vision",
        "domain",
        "objectives",
        "users",
        "businessEntities",
        "capabilities",
        "workflows",
        "businessRules",
        "policies",
        "integrations",
        "reporting",
        "security",
        "quality",
        "constraints",
        "deploymentPreferences",
        "version",
    } == set(schema["required"])


def test_r14_manifest_contract_covers_intent_boundary_and_expansion() -> None:
    contract = r14_manifest_schema_contract()

    assert contract.schema_version == SCHEMA_VERSION
    assert contract.intake_mode == "strict_canonical"
    assert contract.minimal_intake_supported is False
    assert contract.normalization_layer == "deferred_to_intake_normalization_layer"
    assert "database" in contract.forbidden_implementation_fields
    assert "businessEntities" in contract.required_sections
    assert contract.lifecycle == (
        "client",
        "manifest",
        "validation",
        "registry_expansion",
        "knowledge_graph",
        "execution_plan",
        "generated_software",
    )
    assert contract.expansion_outputs == (
        "business_graph",
        "semantic_graph",
        "dependency_graph",
        "execution_graph",
        "implementation_graph",
    )
    assert len(contract.contract_hash) == 64


def test_r14_valid_manifest_passes_schema_and_semantic_validation() -> None:
    report = r14_validate_manifest(_json(VALID), SCHEMA, REGISTRY)

    assert report.valid is True
    assert report.finding_count == 0
    assert len(report.manifest_hash) == 64
    assert len(report.schema_hash) == 64
    assert len(report.report_hash) == 64


def test_r14_minimal_manifest_is_rejected_until_normalization_layer_exists() -> None:
    minimal_manifest = {
        "metadata": {"id": "crm-v1", "version": "1.0.0"},
        "organization": {"name": "Acme Ltd", "industry": "Retail"},
        "domain": "CRM",
        "users": ["Sales Manager", "Sales Representative"],
        "entities": ["Customer", "Lead", "Opportunity"],
        "capabilities": ["Manage Customers", "Track Opportunities"],
    }

    report = r14_validate_manifest(minimal_manifest, SCHEMA, REGISTRY)

    assert report.valid is False
    assert "R14-STRICT-CANONICAL" in {item.code for item in report.findings}


def test_r14_validation_rejects_missing_registry_objects() -> None:
    manifest = _json(VALID)
    manifest["capabilities"][0]["id"] = "unregistered-capability"

    report = r14_validate_manifest(manifest, SCHEMA, REGISTRY)

    assert report.valid is False
    assert "R14-REGISTRY-REFERENCE" in {item.code for item in report.findings}


def test_r14_validation_rejects_technical_design_and_bad_references() -> None:
    manifest = _json(INVALID)
    manifest["workflows"] = [
        {
            "id": "bad-workflow",
            "name": "Bad Workflow",
            "steps": [
                {
                    "name": "Missing capability",
                    "capabilityId": "missing-capability",
                    "entityIds": ["missing-entity"],
                }
            ],
        }
    ]
    report = r14_validate_manifest(manifest, SCHEMA, REGISTRY)
    codes = {item.code for item in report.findings}

    assert report.valid is False
    assert "R14-SCHEMA" in codes
    assert "R14-INTENT-ONLY" in codes
    assert "R14-UNKNOWN-CAPABILITY" in codes
    assert "R14-UNKNOWN-ENTITY" in codes


def test_r14_validation_rejects_circular_business_dependencies() -> None:
    manifest = _json(VALID)
    manifest["capabilities"][0]["dependsOn"] = ["track-opportunities"]
    manifest["capabilities"][1]["dependsOn"] = ["manage-customers"]

    report = r14_validate_manifest(manifest, SCHEMA, REGISTRY)

    assert report.valid is False
    assert "R14-CIRCULAR-DEPENDENCY" in {item.code for item in report.findings}


def test_r14_validation_rejects_inconsistent_constraints() -> None:
    manifest = _json(VALID)
    manifest["constraints"].append(
        {
            "id": "outside-eu",
            "description": "The system must deploy outside EU.",
            "mandatory": True,
        }
    )

    report = r14_validate_manifest(manifest, SCHEMA, REGISTRY)

    assert report.valid is False
    assert "R14-CONSTRAINT-CONFLICT" in {item.code for item in report.findings}


def test_r14_validation_rejects_incompatible_policies() -> None:
    manifest = _json(VALID)
    manifest["policies"].append(
        {
            "id": "global-transfer",
            "name": "Global Transfer Policy",
            "description": "Customer data may transfer globally for support.",
        }
    )

    report = r14_validate_manifest(manifest, SCHEMA, REGISTRY)

    assert report.valid is False
    assert "R14-POLICY-COMPATIBILITY" in {item.code for item in report.findings}


def test_r14_manifest_evolution_requires_new_version_for_changed_content() -> None:
    previous = _json(VALID)
    current = _json(VALID)
    current["vision"] = "Changed business vision."

    report = r14_validate_manifest_evolution(previous, current)

    assert report.valid is False
    assert report.changed is True
    assert report.previous_manifest_version == "1.0.0"
    assert report.current_manifest_version == "1.0.0"
    assert "R14-VERSION-IMMUTABILITY" in {item.code for item in report.findings}


def test_r14_manifest_evolution_accepts_changed_content_with_new_version() -> None:
    previous = _json(VALID)
    current = _json(VALID)
    current["vision"] = "Changed business vision."
    current["version"]["manifestVersion"] = "1.0.1"

    report = r14_validate_manifest_evolution(previous, current)

    assert report.valid is True
    assert report.changed is True
    assert report.current_manifest_version == "1.0.1"
    assert len(report.report_hash) == 64


def test_r14_routes_are_exposed_in_openapi() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert "/api/v1/r14/manifest-schema-contract" in paths
    assert "/api/v1/r14/manifest-schema" in paths
    assert "/api/v1/r14/manifest/validate" in paths
    assert "/api/v1/r14/manifest/evolution/validate" in paths
    assert paths["/api/v1/r14/manifest-schema-contract"]["get"]["tags"] == [
        "r14-manifest-schema"
    ]
