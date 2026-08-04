import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_enterprise.domain.aeir import (
    AeirObjectType,
    AeirProjectModel,
    AeirStatus,
    compile_aepm,
)
from ai_enterprise.domain.aepm import AepmManifest

ROOT = Path(__file__).resolve().parents[3]


def manifest() -> AepmManifest:
    return AepmManifest.model_validate_json(
        (ROOT / "examples/sample-project/aepm-0.1.json").read_text(encoding="utf-8")
    )


def test_aepm_compiles_to_deterministic_canonical_aeir() -> None:
    first = compile_aepm(manifest())
    second = compile_aepm(manifest())

    assert first == second
    assert first.model_sha256 == second.model_sha256
    assert first.objects[0].id == "PROJ-001"
    assert all(
        item.source.manifest_sha256 == first.source_manifest_sha256 for item in first.objects
    )
    assert all(
        item.status is AeirStatus.UNVERIFIED
        for item in first.objects
        if item.type != "decision"
    )
    assert all(
        item.status is AeirStatus.PROPOSED
        for item in first.objects
        if item.type == "decision"
    )


def test_aeir_supports_every_r1_object_type_without_inventing_absent_facts() -> None:
    model = compile_aepm(manifest())
    supported = {item.value for item in AeirObjectType}
    present = {item.type.value for item in model.objects}

    assert supported == {
        "project",
        "intent",
        "outcome",
        "stakeholder",
        "capability",
        "process",
        "requirement",
        "rule",
        "entity",
        "integration",
        "constraint",
        "risk",
        "decision",
        "artifact",
        "relationship",
    }
    assert "risk" not in present
    assert "artifact" not in present
    assert {item.type.value for item in model.relationships} == {"relationship"}


def test_ownership_and_source_traceability_are_explicit() -> None:
    model = compile_aepm(manifest())
    capability = next(item for item in model.objects if item.id == "CAP-001")
    ownership = next(
        item
        for item in model.relationships
        if item.source_object_id == "CAP-001" and item.relationship_type == "owned_by"
    )

    assert ownership.target_object_id == "STK-001"
    assert ownership.id in capability.relationships
    assert capability.source.reference == "capabilities/CAP-001"


def test_aeir_rejects_hash_tamper_and_unknown_fields() -> None:
    document = compile_aepm(manifest()).model_dump(mode="json")
    document["objects"][0]["description"] = "tampered"

    with pytest.raises(ValidationError) as raised:
        AeirProjectModel.model_validate(json.loads(json.dumps(document)))

    assert "AEIR model hash does not match canonical content" in str(raised.value)

    unknown = compile_aepm(manifest()).model_dump(mode="json")
    unknown["silent_approval"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AeirProjectModel.model_validate(unknown)
