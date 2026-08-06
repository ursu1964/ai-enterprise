from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from fastapi.testclient import TestClient

from ai_enterprise.application.bk_r11_evidence_audit_runtime import (
    ARCHIVE_BACKENDS,
    BK_R11_VERSION,
    EVIDENCE_TYPES,
    SIGNATURE_PROVIDERS,
    bk_r11_append_audit_record,
    bk_r11_build_evidence_package,
    bk_r11_create_evidence_artifact,
)
from ai_enterprise.main import app

ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = ROOT / "schemas" / "evidence-audit"
REGISTRY = ROOT / "registry" / "evidence-audit" / "bk-r11-default.json"
EXAMPLE = ROOT / "examples" / "evidence-audit" / "bk-r11-package.json"


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _actor(role: str) -> dict[str, str]:
    return {"actor_type": "human", "actor_id": f"{role}-1", "role": role}


def _subject() -> dict[str, str]:
    return {
        "subject_type": "verification_obligation",
        "subject_id": "obl-req-api-001",
        "relationship": "satisfies",
    }


def test_bk_r11_evidence_audit_schema_files_are_valid_json_schema_documents() -> None:
    for schema_path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        assert schema["$id"].startswith("https://ai-enterprise.local/schemas/evidence-audit/")


def test_bk_r11_registry_matches_runtime_contract() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    assert registry["package_version"] == BK_R11_VERSION
    assert tuple(registry["evidence_types"]) == EVIDENCE_TYPES
    assert tuple(registry["archive_backends"]) == ARCHIVE_BACKENDS
    assert tuple(registry["signature_providers"]) == SIGNATURE_PROVIDERS


def test_bk_r11_example_package_conforms_to_published_schema() -> None:
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    jsonschema.validate(example, _load_schema("evidence-package.schema.json"))
    assert example["acceptance_status"] == "accepted"
    assert example["artifacts"][0]["metadata"]["token"] == "<redacted>"


def test_bk_r11_generated_package_conforms_to_published_core_schema() -> None:
    artifact = bk_r11_create_evidence_artifact(
        evidence_id="ev-test-report-001",
        evidence_type="test-report",
        source_system="ci",
        uri="evidence://ci/run/123/report.json",
        content_hash="sha256-test-report",
        captured_by=_actor("verification-runner"),
        subjects=(_subject(),),
        metadata={"tool": "pytest", "api_key": "must-redact"},
    )
    audit_record = bk_r11_append_audit_record(
        (),
        stream_id="project:project-001",
        event_type="EvidenceCaptured",
        actor=_actor("auditor"),
        subject=_subject(),
        evidence_ids=(artifact.evidence_id,),
        payload={"result": "passed"},
    )
    package = bk_r11_build_evidence_package(
        evidence_package_id="pkg-r11-001",
        project_id="project-001",
        baseline_refs={"requirements": "req-baseline-001", "verification": "campaign-001"},
        artifacts=(artifact,),
        audit_records=(audit_record,),
        required_evidence_by_obligation={"obl-req-api-001": ("test-report",)},
    )

    jsonschema.validate(
        package.model_dump(mode="json"),
        _load_schema("evidence-package.schema.json"),
    )
    assert package.acceptance_status == "accepted"


def test_bk_r11_contract_api_matches_published_registry() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    response = TestClient(app).get(
        "/api/v1/bk/r11-evidence-audit/contract",
        headers={
            "X-Actor-ID": "local-dashboard-admin",
            "X-Actor-Type": "human",
            "X-Actor-Role": "platform-admin",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == registry["package_version"]
    assert tuple(payload["evidence_types"]) == tuple(registry["evidence_types"])
    assert tuple(payload["archive_backends"]) == tuple(registry["archive_backends"])
    assert tuple(payload["signature_providers"]) == tuple(registry["signature_providers"])
