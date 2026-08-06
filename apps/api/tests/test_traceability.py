import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_enterprise.domain.aeir import compile_aepm
from ai_enterprise.domain.aepm import AepmManifest
from ai_enterprise.domain.artifact_compilers import ArtifactType, compile_artifact_bundle
from ai_enterprise.domain.traceability import (
    ArtifactTraceabilityManifest,
    compile_traceability_manifest,
    render_traceable_artifact_markdown,
    verify_traceability_manifest,
)

ROOT = Path(__file__).resolve().parents[3]


def model():
    document = json.loads(
        (ROOT / "examples/sample-project/aepm-0.1.json").read_text(encoding="utf-8")
    )
    return compile_aepm(AepmManifest.model_validate(document))


def traceability():
    source = model()
    bundle = compile_artifact_bundle(source)
    return source, bundle, compile_traceability_manifest(source, bundle)


def test_traceability_manifest_is_stable_and_bound_to_model_and_bundle() -> None:
    source = model()
    first_bundle = compile_artifact_bundle(source)
    second_bundle = compile_artifact_bundle(source)

    first = compile_traceability_manifest(source, first_bundle)
    second = compile_traceability_manifest(source, second_bundle)

    assert first == second
    assert first.source_model_sha256 == source.model_sha256
    assert first.source_manifest_sha256 == source.source_manifest_sha256
    assert first.artifact_bundle_sha256 == first_bundle.bundle_sha256
    verify_traceability_manifest(first, source, first_bundle)


def test_every_artifact_section_and_entry_has_exactly_one_trace() -> None:
    _, bundle, manifest = traceability()

    expected_sections = {
        (artifact.artifact_type, artifact.artifact_sha256, section.key)
        for artifact in bundle.artifacts
        for section in artifact.sections
    }
    actual_sections = {
        (trace.artifact_type, trace.artifact_sha256, trace.section_key)
        for trace in manifest.section_traces
    }
    expected_entries = {
        (artifact.artifact_type, artifact.artifact_sha256, section.key, index)
        for artifact in bundle.artifacts
        for section in artifact.sections
        for index, _ in enumerate(section.entries)
    }
    actual_entries = {
        (trace.artifact_type, trace.artifact_sha256, trace.section_key, trace.entry_index)
        for trace in manifest.entry_traces
    }

    assert actual_sections == expected_sections
    assert actual_entries == expected_entries
    assert all(trace.source_object_ids for trace in manifest.section_traces)
    assert all(trace.source_object_ids for trace in manifest.entry_traces)


def test_requirements_and_backlog_entries_retain_direct_aeir_sources() -> None:
    _, _, manifest = traceability()

    functional_sources = [
        trace.source_object_ids
        for trace in manifest.entry_traces
        if trace.artifact_type is ArtifactType.SOFTWARE_REQUIREMENTS
        and trace.section_key == "functional_requirements"
    ]
    acceptance_sources = [
        trace.source_object_ids
        for trace in manifest.entry_traces
        if trace.artifact_type is ArtifactType.DELIVERY_BACKLOG
        and trace.section_key == "acceptance_criteria"
    ]

    assert functional_sources == [
        ("CAP-001",),
        ("PROC-001",),
        ("RULE-001",),
        ("INT-001",),
    ]
    assert acceptance_sources == [("QUAL-001",)]


def test_traceability_preserves_original_client_source_references() -> None:
    _, _, manifest = traceability()
    catalog = {item.object_id: item for item in manifest.source_objects}

    assert catalog["INTENT-001"].source_reference == "project_intent"
    assert catalog["CAP-001"].source_reference == "capabilities/CAP-001"
    assert catalog["QUAL-001"].source_reference == "quality_requirements/QUAL-001"
    assert catalog["CAP-001"].source_manifest_sha256 == manifest.source_manifest_sha256


def test_data_ownership_section_retains_relationship_and_endpoint_sources() -> None:
    _, _, manifest = traceability()

    ownership = next(
        trace
        for trace in manifest.entry_traces
        if trace.artifact_type is ArtifactType.DOMAIN_DATA_MODEL
        and trace.section_key == "data_ownership"
    )

    assert ownership.source_object_ids == ("ENT-001", "STK-001")
    assert ownership.relationship_ids == ("REL-009",)


def test_traceable_markdown_adds_section_source_lines() -> None:
    _, bundle, manifest = traceability()

    rendered = render_traceable_artifact_markdown(
        ArtifactType.SOFTWARE_REQUIREMENTS,
        bundle,
        manifest,
    )

    assert rendered == render_traceable_artifact_markdown(
        ArtifactType.SOFTWARE_REQUIREMENTS,
        bundle,
        manifest,
    )
    assert (
        "- CAP-001 [unverified]: Capture and classify a customer service request.\n"
        "  Trace: CAP-001 | Client references: capabilities/CAP-001"
    ) in rendered
    assert (
        "- INT-001 [unverified]: Authenticate customers and service operators.\n"
        "  Trace: INT-001 | Client references: integrations/INT-001"
    ) in rendered
    assert (
        "Sources: CAP-001, INT-001, PROC-001, RULE-001 | Client references: "
        "capabilities/CAP-001, integrations/INT-001, core_processes/PROC-001, "
        "business_rules/RULE-001"
    ) in rendered
    assert "Client references: capabilities/CAP-001" in rendered
    assert rendered.endswith("\n")


def test_architecture_decisions_render_entry_level_source_lines() -> None:
    _, bundle, manifest = traceability()

    rendered = render_traceable_artifact_markdown(
        ArtifactType.SOLUTION_ARCHITECTURE,
        bundle,
        manifest,
    )

    assert (
        "- DEC-001 [proposed] — frontend: React\n"
        "  Trace: DEC-001 | Client references: preferred_technology_targets/frontend"
    ) in rendered


def test_traceability_tampering_fails_closed() -> None:
    source, bundle, manifest = traceability()

    with pytest.raises(ValidationError, match="manifest hash"):
        ArtifactTraceabilityManifest.model_validate(
            {**manifest.model_dump(mode="json"), "manifest_sha256": "0" * 64}
        )

    changed = manifest.model_dump(mode="json")
    changed["section_traces"][0]["source_object_ids"] = ["UNKNOWN-001"]
    changed["manifest_sha256"] = manifest.manifest_sha256
    with pytest.raises(ValidationError, match="unknown source object"):
        ArtifactTraceabilityManifest.model_validate(changed)

    with pytest.raises(ValueError, match="does not match AEIR model"):
        verify_traceability_manifest(
            manifest.model_copy(update={"artifact_bundle_sha256": "0" * 64}),
            source,
            bundle,
        )
