import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_enterprise.domain.aeir import compile_aepm
from ai_enterprise.domain.aepm import AepmManifest
from ai_enterprise.domain.r5_umte import compile_umte_export_bundle, compile_umte_transformation
from ai_enterprise.domain.r6_uagf import (
    UagfArtifactRepositoryKind,
    UagfBuildStatus,
    UagfFileLifecycle,
    UagfGeneratedFile,
    UagfLifecycleEventType,
    UagfRegenerationAction,
    UagfValidationGateStatus,
    certified_uagf_generator_packs,
    current_uagf_lifecycle_status,
    generate_uagf_build,
    install_uagf_generator_pack,
    plan_parallel_uagf_generation,
    plan_uagf_regeneration,
    publish_uagf_artifacts_to_repository,
    transition_uagf_lifecycle,
    uagf_validation_gate_run,
    validate_uagf_files,
)
from ai_enterprise.domain.specification.kernel import specification_hash

ROOT = Path(__file__).resolve().parents[3]


def _r5():
    document = json.loads(
        (ROOT / "examples/sample-project/aepm-0.1.json").read_text(encoding="utf-8")
    )
    model = compile_aepm(AepmManifest.model_validate(document))
    result = compile_umte_transformation(model)
    return result, compile_umte_export_bundle(result)


def test_r6_uagf_generates_deterministic_verified_file_build_from_r5_bundle() -> None:
    r5, bundle = _r5()

    first = generate_uagf_build(bundle, r5.generated_artifacts)
    second = generate_uagf_build(bundle, r5.generated_artifacts)

    assert first == second
    assert first.validation_report.status is UagfBuildStatus.VERIFIED
    assert first.manifest.r5_export_bundle_hash == bundle.bundle_hash
    assert first.manifest.file_count == 77
    assert len(first.files) == 77
    assert tuple(file.relative_path for file in first.files) == tuple(
        sorted(file.relative_path for file in first.files)
    )
    assert all("AI-Enterprise-Generated" in file.content for file in first.files)
    assert any("<AI-ENTERPRISE-CUSTOM-REGION" in file.content for file in first.files)


def test_r6_uagf_typed_generators_emit_target_specific_contracts() -> None:
    r5, bundle = _r5()
    result = generate_uagf_build(bundle, r5.generated_artifacts)
    files = {file.relative_path: file.content for file in result.files}

    assert any(
        '"openapi":"3.1.0"' in content
        for path, content in files.items()
        if "/openapi/" in path
    )
    assert any(
        "CREATE TABLE IF NOT EXISTS generated_" in content
        for path, content in files.items()
        if path.endswith(".sql")
    )
    assert any(
        "@dataclass(frozen=True)" in content
        for path, content in files.items()
        if "/python/" in path
    )
    assert any(
        "def test_generated_" in content
        for path, content in files.items()
        if "/pytest/" in path
    )
    assert any('"component":' in content for path, content in files.items() if "/react/" in path)
    assert any(
        "GenerationDrift" in content
        for path, content in files.items()
        if "/prometheus/" in path
    )
    assert any(
        "kind: Deployment" in content
        for path, content in files.items()
        if path.endswith(".yaml")
    )
    assert any('"prompt_id":' in content for path, content in files.items() if "/prompt/" in path)


def test_r6_uagf_rejects_file_hash_tampering_and_unsafe_paths() -> None:
    r5, bundle = _r5()
    file = generate_uagf_build(bundle, r5.generated_artifacts).files[0]

    with pytest.raises(ValidationError, match="file hash"):
        UagfGeneratedFile.model_validate({**file.model_dump(mode="json"), "file_hash": "0" * 64})

    with pytest.raises(ValidationError, match="path"):
        UagfGeneratedFile.model_validate(
            {**file.model_dump(mode="json"), "relative_path": "../escape.py"}
        )


def test_r6_uagf_requires_artifacts_to_match_export_bundle() -> None:
    r5, bundle = _r5()

    with pytest.raises(ValueError, match="do not match"):
        generate_uagf_build(bundle, r5.generated_artifacts[:-1])


def test_r6_uagf_validation_enforces_cross_artifact_consistency() -> None:
    r5, bundle = _r5()
    result = generate_uagf_build(bundle, r5.generated_artifacts)

    report = validate_uagf_files(bundle, result.files, generated_artifacts=r5.generated_artifacts)

    assert report.status is UagfBuildStatus.VERIFIED
    assert report.findings == ()


def test_r6_uagf_validation_blocks_dependency_coverage_drift() -> None:
    r5, bundle = _r5()
    result = generate_uagf_build(bundle, r5.generated_artifacts)
    artifact = r5.generated_artifacts[0]
    drifted_document = {
        **artifact.content_document,
        "body": {
            **artifact.content_document["body"],
            "dependencies": ["UNKNOWN-OBJECT"],
        },
    }
    drifted_artifact = type(artifact).model_construct(
        **{
            **artifact.model_dump(mode="python"),
            "content_document": drifted_document,
        }
    )

    report = validate_uagf_files(
        bundle,
        result.files,
        generated_artifacts=(drifted_artifact, *r5.generated_artifacts[1:]),
    )

    assert report.status is UagfBuildStatus.FAILED
    assert any(
        finding.rule_id == "UAGF.VERIFY.CONSISTENCY.DEPENDENCY_COVERAGE"
        for finding in report.findings
    )


def test_r6_uagf_validation_blocks_target_path_drift() -> None:
    r5, bundle = _r5()
    file = generate_uagf_build(bundle, r5.generated_artifacts).files[0]
    drifted = UagfGeneratedFile.model_validate(
        {
            **file.model_dump(mode="json"),
            "relative_path": "generated/python/path-drift.py",
            "file_hash": specification_hash(
                {
                    **file.model_dump(mode="json", exclude={"file_hash"}),
                    "relative_path": "generated/python/path-drift.py",
                }
            ),
        }
    )

    report = validate_uagf_files(bundle, (drifted,))

    assert report.status is UagfBuildStatus.FAILED
    assert any(
        finding.rule_id == "UAGF.VERIFY.CONSISTENCY.TARGET_PATH"
        for finding in report.findings
    )


def test_r6_uagf_validation_blocks_invalid_json_target_syntax() -> None:
    r5, bundle = _r5()
    file = next(
        item
        for item in generate_uagf_build(bundle, r5.generated_artifacts).files
        if "/openapi/" in item.relative_path
    )
    broken_content = '{"openapi":'
    broken = UagfGeneratedFile.model_validate(
        {
            **file.model_dump(mode="json"),
            "content": broken_content,
            "content_hash": specification_hash({"content": broken_content}),
            "file_hash": specification_hash(
                {
                    **file.model_dump(
                        mode="json",
                        exclude={"file_hash", "content", "content_hash"},
                    ),
                    "content": broken_content,
                    "content_hash": specification_hash({"content": broken_content}),
                }
            ),
        }
    )

    report = validate_uagf_files(bundle, (broken,))

    assert report.status is UagfBuildStatus.FAILED
    assert any(finding.rule_id == "UAGF.VERIFY.SYNTAX.TARGET" for finding in report.findings)


def test_r6_uagf_validation_blocks_invalid_python_target_syntax() -> None:
    r5, bundle = _r5()
    file = next(
        item
        for item in generate_uagf_build(bundle, r5.generated_artifacts).files
        if "/python/" in item.relative_path
    )
    broken_content = file.content + "\ndef broken(:\n"
    broken = UagfGeneratedFile.model_validate(
        {
            **file.model_dump(mode="json"),
            "content": broken_content,
            "content_hash": specification_hash({"content": broken_content}),
            "file_hash": specification_hash(
                {
                    **file.model_dump(
                        mode="json",
                        exclude={"file_hash", "content", "content_hash"},
                    ),
                    "content": broken_content,
                    "content_hash": specification_hash({"content": broken_content}),
                }
            ),
        }
    )

    report = validate_uagf_files(bundle, (broken,))

    assert report.status is UagfBuildStatus.FAILED
    assert any(finding.rule_id == "UAGF.VERIFY.SYNTAX.TARGET" for finding in report.findings)


def test_r6_uagf_certified_generator_packs_support_multi_technology_factory() -> None:
    packs = {pack.pack_id: pack for pack in certified_uagf_generator_packs()}

    assert "uagf.react-nestjs-kubernetes" in packs
    assert "uagf.spring-terraform" in packs
    assert packs["uagf.react-nestjs-kubernetes"].status.value == "certified"
    assert "react" in packs["uagf.react-nestjs-kubernetes"].technology_stack
    assert "terraform.validate" in packs["uagf.spring-terraform"].validation_gates

    installation = install_uagf_generator_pack(
        index=1,
        project_id="project-1",
        pack_id="uagf.react-nestjs-kubernetes",
        version="1.0",
        installed_by="operator@example.com",
    )

    assert installation.installation_id == "UAGF-PACK-0001"
    assert installation.pack.pack_hash
    assert installation.installation_hash


def test_r6_uagf_parallel_gates_and_repository_publication_are_hashed() -> None:
    r5, bundle = _r5()
    build = generate_uagf_build(
        bundle,
        r5.generated_artifacts,
        generator_pack_id="uagf.react-nestjs-kubernetes",
        generator_pack_version="1.0",
    )
    plan = plan_parallel_uagf_generation(index=1, build=build, max_parallelism=8)
    gate = uagf_validation_gate_run(
        index=1,
        build_hash=build.build_hash,
        gate_id="npm.test",
        command=("npm", "test"),
        status=UagfValidationGateStatus.SKIPPED,
        output="npm is not installed",
    )
    publication = publish_uagf_artifacts_to_repository(
        index=1,
        build=build,
        repository_kind=UagfArtifactRepositoryKind.FILESYSTEM,
        repository_ref="artifact://local/r6/project-1",
        version_ref=build.build_hash,
    )

    assert plan.max_parallelism == 8
    assert plan.lanes
    assert gate.output_hash
    assert publication.file_count == len(build.files)
    assert publication.content_address == build.manifest.file_set_hash


def test_r6_uagf_incremental_regeneration_reuses_unchanged_files() -> None:
    r5, bundle = _r5()
    first = generate_uagf_build(bundle, r5.generated_artifacts)
    second = generate_uagf_build(bundle, r5.generated_artifacts, previous_files=first.files)
    plan = plan_uagf_regeneration(bundle, r5.generated_artifacts, first.files)

    assert second == first
    assert set(plan.actions_by_artifact_key.values()) == {UagfRegenerationAction.REUSE}
    assert plan.reused_file_ids == tuple(sorted(file.file_id for file in first.files))
    assert plan.regenerated_artifact_keys == ()
    assert plan.preserved_custom_region_count == 0


def test_r6_uagf_incremental_regeneration_preserves_custom_regions() -> None:
    r5, bundle = _r5()
    first = generate_uagf_build(bundle, r5.generated_artifacts)
    python_file = next(file for file in first.files if "/python/" in file.relative_path)
    custom_content = python_file.content.replace(
        "# Custom extension code may be added here by downstream tools.\n",
        "    def custom_extension(self) -> str:\n"
        "        return \"preserved downstream logic\"\n",
    )
    customized_previous = UagfGeneratedFile.model_validate(
        {
            **python_file.model_dump(mode="json"),
            "content": custom_content,
            "content_hash": specification_hash({"content": custom_content}),
            "file_hash": "0" * 64,
        }
        | {
            "file_hash": specification_hash(
                {
                    **python_file.model_dump(
                        mode="json",
                        exclude={"file_hash", "content", "content_hash"},
                    ),
                    "content": custom_content,
                    "content_hash": specification_hash({"content": custom_content}),
                }
            )
        }
    )
    changed_artifact = next(
        artifact
        for artifact in r5.generated_artifacts
        if artifact.artifact_key == python_file.artifact_key
    )
    changed_document = {
        **changed_artifact.content_document,
        "body": {
            **changed_artifact.content_document["body"],
            "operations": ["create", "read", "customized"],
        },
    }
    changed_hash = specification_hash(
        {
            **changed_artifact.model_dump(mode="json", exclude={"generated_hash"}),
            "content_document": changed_document,
        }
    )
    changed_artifacts = tuple(
        type(artifact).model_validate(
            {
                **artifact.model_dump(mode="json"),
                "content_document": changed_document,
                "generated_hash": changed_hash,
            }
        )
        if artifact.artifact_key == changed_artifact.artifact_key
        else artifact
        for artifact in r5.generated_artifacts
    )
    regenerated = generate_uagf_build(
        bundle,
        changed_artifacts,
        previous_files=(customized_previous,),
    )
    plan = plan_uagf_regeneration(bundle, changed_artifacts, (customized_previous,))
    regenerated_file = next(
        file for file in regenerated.files if file.artifact_key == python_file.artifact_key
    )

    assert "preserved downstream logic" in regenerated_file.content
    assert "'customized'" in regenerated_file.content
    assert (
        plan.actions_by_artifact_key[python_file.artifact_key]
        is UagfRegenerationAction.PRESERVE_CUSTOM
    )
    assert plan.preserved_custom_region_count == 1


def test_r6_uagf_lifecycle_requires_review_approval_before_publish() -> None:
    r5, bundle = _r5()
    result = generate_uagf_build(bundle, r5.generated_artifacts)

    review = transition_uagf_lifecycle(
        index=1,
        build_hash=result.build_hash,
        current_status=UagfFileLifecycle.VERIFIED,
        event_type=UagfLifecycleEventType.REQUEST_REVIEW,
        actor="operator@example.com",
        reason="ready for generated artifact review",
    )
    approval = transition_uagf_lifecycle(
        index=2,
        build_hash=result.build_hash,
        current_status=review.to_status,
        event_type=UagfLifecycleEventType.APPROVE,
        actor="operator@example.com",
        reason="review passed",
    )
    published = transition_uagf_lifecycle(
        index=3,
        build_hash=result.build_hash,
        current_status=approval.to_status,
        event_type=UagfLifecycleEventType.PUBLISH,
        actor="operator@example.com",
        reason="approved build can be published",
    )

    assert published.to_status is UagfFileLifecycle.PUBLISHED
    assert current_uagf_lifecycle_status((review, approval, published)) is (
        UagfFileLifecycle.PUBLISHED
    )
    with pytest.raises(ValueError, match="not allowed"):
        transition_uagf_lifecycle(
            index=4,
            build_hash=result.build_hash,
            current_status=UagfFileLifecycle.VERIFIED,
            event_type=UagfLifecycleEventType.PUBLISH,
            actor="operator@example.com",
            reason="publish without approval",
        )
