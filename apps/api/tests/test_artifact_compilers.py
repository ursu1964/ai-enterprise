import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_enterprise.domain.aeir import compile_aepm
from ai_enterprise.domain.aepm import AepmManifest
from ai_enterprise.domain.artifact_compilers import (
    ArtifactBundle,
    ArtifactType,
    CompiledArtifact,
    compile_artifact_bundle,
    render_artifact_markdown,
)

ROOT = Path(__file__).resolve().parents[3]


def model():
    document = json.loads(
        (ROOT / "examples/sample-project/aepm-0.1.json").read_text(encoding="utf-8")
    )
    return compile_aepm(AepmManifest.model_validate(document))


def test_compiler_emits_exactly_five_stable_aeir_bound_outputs() -> None:
    source = model()
    first = compile_artifact_bundle(source)
    second = compile_artifact_bundle(source)

    assert tuple(item.artifact_type for item in first.artifacts) == tuple(ArtifactType)
    assert all(item.source_model_sha256 == source.model_sha256 for item in first.artifacts)
    assert first == second


def test_each_compiler_projects_relevant_canonical_information() -> None:
    artifacts = {item.artifact_type: item for item in compile_artifact_bundle(model()).artifacts}

    assert "Service Request Portal" in artifacts[ArtifactType.EXECUTIVE_BRIEF].title
    assert any(
        "QUAL-001" in entry
        for section in artifacts[ArtifactType.SOFTWARE_REQUIREMENTS].sections
        for entry in section.entries
    )
    assert any(
        "ENT-001" in entry
        for section in artifacts[ArtifactType.DOMAIN_DATA_MODEL].sections
        for entry in section.entries
    )
    assert any(
        "INT-001" in entry
        for section in artifacts[ArtifactType.SOLUTION_ARCHITECTURE].sections
        for entry in section.entries
    )
    assert any(
        "BLG-001" in entry
        for section in artifacts[ArtifactType.DELIVERY_BACKLOG].sections
        for entry in section.entries
    )


def test_markdown_rendering_is_deterministic_and_structured() -> None:
    artifact = compile_artifact_bundle(model()).artifacts[0]
    rendered = render_artifact_markdown(artifact)

    assert rendered == render_artifact_markdown(artifact)
    assert rendered.startswith("# Executive Project Brief")
    assert "## Project intent" in rendered
    assert rendered.endswith("\n")


def test_artifact_and_bundle_hash_tampering_fail_closed() -> None:
    bundle = compile_artifact_bundle(model())
    artifact = bundle.artifacts[0]
    with pytest.raises(ValidationError, match="content hash"):
        CompiledArtifact.model_validate(
            {**artifact.model_dump(mode="json"), "content_sha256": "0" * 64}
        )
    with pytest.raises(ValidationError, match="bundle hash"):
        ArtifactBundle.model_validate(
            {**bundle.model_dump(mode="json"), "bundle_sha256": "0" * 64}
        )


def test_bundle_rejects_missing_or_reordered_artifacts() -> None:
    bundle = compile_artifact_bundle(model())

    with pytest.raises(ValidationError, match="exact five outputs"):
        ArtifactBundle.model_validate(
            {
                **bundle.model_dump(mode="json"),
                "artifacts": [
                    item.model_dump(mode="json") for item in reversed(bundle.artifacts)
                ],
            }
        )
