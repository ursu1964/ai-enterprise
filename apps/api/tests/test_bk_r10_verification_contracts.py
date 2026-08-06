from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml
from fastapi.testclient import TestClient

from ai_enterprise.application.bk_r10_verification_runtime import (
    VERIFICATION_METHODS,
    bk_r10_conformance_report,
    bk_r10_create_campaign,
    bk_r10_create_handoff,
)
from ai_enterprise.main import app
from tests.test_bk_r10_verification_runtime import _actor

ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = ROOT / "schemas" / "verification"
REGISTRY_DIR = ROOT / "registry"
EXAMPLE = ROOT / "examples" / "verification" / "bk-r10-campaign.yaml"


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def test_bk_r10_verification_schema_files_are_valid_json_schema_documents() -> None:
    for schema_path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        assert schema["$id"].startswith("https://ai-enterprise.local/schemas/verification/")


def test_bk_r10_registry_methods_match_runtime_contract() -> None:
    registry = json.loads(
        (REGISTRY_DIR / "verification-methods" / "bk-r10-default.json").read_text(encoding="utf-8")
    )

    assert tuple(registry["methods"]) == VERIFICATION_METHODS


def test_bk_r10_generated_campaign_conforms_to_published_core_schemas() -> None:
    handoff = bk_r10_create_handoff(
        implementation_result_id="impl-result-001",
        implementation_slice_id="slice-001",
        repository_revision="commit-abc",
        requirement_baseline_id="req-baseline-001",
        architecture_baseline_id="arch-baseline-001",
        planning_baseline_id="plan-baseline-001",
        produced_by=_actor("implementation-agent"),
    )
    campaign = bk_r10_create_campaign(
        organization_id="org-001",
        project_id="project-001",
        handoff=handoff,
        owner=_actor("verification-owner"),
        obligations=(
            {
                "verification_obligation_id": "obl-req-api-001",
                "requirement_id": "REQ-API-001",
                "method": "TEST",
                "criticality": "CRITICAL",
                "mandatory": True,
                "responsible_authority": _actor("verification-authority"),
            },
        ),
    )
    campaign_payload = campaign.model_dump(mode="json")
    handoff_payload = campaign.verification_handoff.model_dump(mode="json")
    obligation_payload = campaign.obligations[0].model_dump(mode="json")

    jsonschema.validate(handoff_payload, _load_schema("handoff.schema.json"))
    jsonschema.validate(obligation_payload, _load_schema("obligation.schema.json"))
    assert (
        campaign_payload["status"]
        in _load_schema("campaign.schema.json")["properties"]["status"]["enum"]
    )


def test_bk_r10_example_campaign_has_required_contract_sections() -> None:
    example = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))

    assert example["verification_campaign_id"] == "bk-r10-campaign-example"
    assert example["verification_handoff"]["repository_revision"] == "commit-example"
    assert example["obligations"][0]["required_evidence_types"] == ["test-report"]


def test_bk_r10_policy_registry_publishes_no_evidence_no_pass_rule() -> None:
    policy = json.loads(
        (REGISTRY_DIR / "verification-policies" / "bk-r10-default.json").read_text(encoding="utf-8")
    )
    backends = json.loads(
        (REGISTRY_DIR / "verification-backends" / "bk-r10-default.json").read_text(encoding="utf-8")
    )

    assert any("cannot pass without evidence" in rule for rule in policy["rules"])
    assert "ci_runner" in backends["required_backends"]
    assert (
        "credential_reference is required in production and staging"
        in backends["production_requirements"]
    )


def test_bk_r10_conformance_report_maps_acceptance_criteria_to_evidence() -> None:
    report = bk_r10_conformance_report(ROOT)

    assert report.status == "PASS"
    assert report.summary["total"] >= 16
    assert report.summary["failed"] == 0
    assert any(item.criterion_id == "BK-R10-AC-004" for item in report.criteria)
    assert all(item.evidence_paths for item in report.criteria)


def test_bk_r10_conformance_api_is_exposed() -> None:
    response = TestClient(app).get(
        "/api/v1/bk/r10-verification/conformance",
        headers={
            "X-Actor-ID": "local-dashboard-admin",
            "X-Actor-Type": "human",
            "X-Actor-Role": "platform-admin",
        },
    )

    assert response.status_code == 200
    record = response.json()["record"]
    assert record["status"] == "PASS"
    assert record["summary"]["failed"] == 0
