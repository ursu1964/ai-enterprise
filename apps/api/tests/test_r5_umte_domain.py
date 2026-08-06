import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_enterprise.domain.aeir import compile_aepm
from ai_enterprise.domain.aepm import AepmManifest
from ai_enterprise.domain.r5_umte import (
    UmteArtifactSpec,
    UmteExportBundle,
    UmteVerificationStatus,
    affected_umte_artifact_keys,
    compile_umte_export_bundle,
    compile_umte_transformation,
    default_registry_rules,
    require_approved_snapshot,
    verify_umte_transformation,
)

ROOT = Path(__file__).resolve().parents[3]


def model():
    document = json.loads(
        (ROOT / "examples/sample-project/aepm-0.1.json").read_text(encoding="utf-8")
    )
    return compile_aepm(AepmManifest.model_validate(document))


def test_r5_umte_emits_deterministic_registry_bound_artifact_specs() -> None:
    source = model()
    first = compile_umte_transformation(source)
    second = compile_umte_transformation(source)

    assert first == second
    assert first.verification_report.status is UmteVerificationStatus.PASSED
    assert len(first.artifact_specs) == 77
    assert len(first.generated_artifacts) == 77
    assert tuple(item.artifact_key for item in first.generated_artifacts) == tuple(
        item.artifact_key for item in first.artifact_specs
    )
    assert tuple(sorted(item.artifact_key for item in first.artifact_specs)) == tuple(
        item.artifact_key for item in first.artifact_specs
    )
    assert {rule.rule_id for rule in default_registry_rules()} == {
        item.provenance.registry_rule_id for item in first.artifact_specs
    }
    assert all(
        item.provenance.source_model_sha256 == source.model_sha256
        and item.provenance.source_manifest_sha256 == source.source_manifest_sha256
        and item.specification_document["ai_boundary"] == "transform_only_no_business_invention"
        for item in first.artifact_specs
    )
    assert all(
        item.content_document["source_artifact_spec_hash"] == item.source_artifact_spec_hash
        for item in first.generated_artifacts
    )


def test_r5_umte_expands_entity_into_data_api_ui_security_events_tests_and_docs() -> None:
    result = compile_umte_transformation(model())

    entity_kinds = {
        item.artifact_kind
        for item in result.artifact_specs
        if item.source_object_id == "ENT-001"
    }

    assert {kind.value for kind in entity_kinds} == {
        "database_model",
        "database_migration",
        "domain_model",
        "rest_api",
        "ui_specification",
        "security_permission_model",
        "event_contract",
        "test_suite",
        "documentation",
    }


def test_r5_umte_fails_closed_on_unregistered_artifact_specs() -> None:
    source = model()
    result = compile_umte_transformation(source)
    artifact = result.artifact_specs[0]
    tampered = UmteArtifactSpec.model_construct(
        **{
            **artifact.model_dump(mode="python"),
            "provenance": artifact.provenance.model_copy(
                update={"registry_rule_id": "UMTE.UNKNOWN.RULE.001"}
            ),
        }
    )

    report = verify_umte_transformation(source, result.plan, (tampered,))

    assert report.status is UmteVerificationStatus.FAILED
    assert any(
        finding.rule_id == "UMTE.VERIFY.REGISTRY.RULE_BOUND"
        for finding in report.findings
    )


def test_r5_umte_artifact_hash_tampering_fails_validation() -> None:
    artifact = compile_umte_transformation(model()).artifact_specs[0]

    with pytest.raises(ValidationError, match="artifact spec hash"):
        UmteArtifactSpec.model_validate(
            {**artifact.model_dump(mode="json"), "artifact_spec_hash": "0" * 64}
        )


def test_r5_umte_incremental_regeneration_marks_changed_object_dependencies() -> None:
    previous = model()
    raw_manifest = json.loads(
        (ROOT / "examples/sample-project/aepm-0.1.json").read_text(encoding="utf-8")
    )
    raw_manifest["data_entities"][0]["description"] += " Email verification is required."
    current = compile_aepm(AepmManifest.model_validate(raw_manifest))
    result = compile_umte_transformation(current)

    affected = affected_umte_artifact_keys(previous, current, result)

    assert any(key.startswith("entity.ent-001.") for key in affected)
    assert affected == tuple(sorted(set(affected)))


def test_r5_umte_production_generation_requires_approved_snapshot_gate() -> None:
    with pytest.raises(ValueError, match="approved AEIR snapshot"):
        require_approved_snapshot(None)


def test_r5_umte_export_bundle_is_deterministic_and_hash_bound() -> None:
    result = compile_umte_transformation(model())

    first = compile_umte_export_bundle(result)
    second = compile_umte_export_bundle(result)

    assert first == second
    assert first.transformation_result_hash == result.result_hash
    assert first.artifact_count == len(result.generated_artifacts)
    assert tuple(entry.artifact_key for entry in first.entries) == tuple(
        artifact.artifact_key for artifact in result.generated_artifacts
    )
    assert all(
        entry.content_address == f"sha256:{entry.generated_hash}"
        for entry in first.entries
    )

    with pytest.raises(ValidationError, match="export bundle hash"):
        UmteExportBundle.model_validate(
            {**first.model_dump(mode="json"), "bundle_hash": "0" * 64}
        )
