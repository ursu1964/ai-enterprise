import json
import uuid
from pathlib import Path

import pytest

from ai_enterprise.domain.aeir import compile_aepm
from ai_enterprise.domain.aepm import AepmManifest
from ai_enterprise.infrastructure.knowledge.aeir_repository import build_aeir_write_set
from ai_enterprise.infrastructure.knowledge.models import (
    AeirAiOperationModel,
    AeirArtifactTraceLinkModel,
    AeirArtifactVersionModel,
    AeirChangeEventModel,
    AeirClarificationAnswerModel,
    AeirClarificationQuestionModel,
    AeirDecisionModel,
    AeirEvidenceModel,
    AeirModelVersionModel,
    AeirObjectModel,
    AeirObjectSourceLinkModel,
    AeirObjectVersionModel,
    AeirProjectSnapshotModel,
    AeirRelationshipModel,
    AeirRelationshipSourceLinkModel,
    AeirRelationshipVersionModel,
    AeirSourceObjectModel,
    AeirValidationFindingModel,
    AeirValidationRuleModel,
)
from ai_enterprise.infrastructure.knowledge.object_store import (
    LocalContentAddressedObjectStore,
    StoredObject,
)

ROOT = Path(__file__).resolve().parents[3]


def has_unique_constraint(model: type, *columns: str) -> bool:
    expected = set(columns)
    return any(
        getattr(constraint, "columns", None) is not None
        and {column.name for column in constraint.columns} == expected
        for constraint in model.__table__.constraints
    )


def project_model():
    document = json.loads(
        (ROOT / "examples/sample-project/aepm-0.1.json").read_text(encoding="utf-8")
    )
    return compile_aepm(AepmManifest.model_validate(document))


def test_aeir_storage_schema_has_relational_and_jsonb_boundaries() -> None:
    assert AeirModelVersionModel.__table__.c.model_document.type.__class__.__name__ == "JSONB"
    assert has_unique_constraint(AeirModelVersionModel, "project_id", "model_sha256")
    assert AeirObjectModel.__table__.c.attributes.type.__class__.__name__ == "JSONB"
    assert AeirRelationshipModel.__table__.c.source_object_id.foreign_keys
    assert AeirRelationshipModel.__table__.c.target_object_id.foreign_keys
    assert AeirSourceObjectModel.__table__.c.object_key.type.length is None
    assert AeirChangeEventModel.__table__.c.event_hash.unique


def test_r2_project_formation_storage_tables_cover_snapshot_review_and_artifacts() -> None:
    assert AeirProjectSnapshotModel.__table__.c.snapshot_document.type.__class__.__name__ == "JSONB"
    assert has_unique_constraint(AeirProjectSnapshotModel, "project_id", "snapshot_sha256")
    assert AeirProjectSnapshotModel.__table__.c.model_version_id.foreign_keys
    assert AeirObjectVersionModel.__table__.c.object_row_id.foreign_keys
    assert AeirRelationshipVersionModel.__table__.c.relationship_row_id.foreign_keys
    assert AeirValidationRuleModel.__table__.c.rule_document.type.__class__.__name__ == "JSONB"
    assert AeirValidationFindingModel.__table__.c.blocking.type.__class__.__name__ == "Boolean"
    assert has_unique_constraint(AeirValidationFindingModel, "finding_hash")
    assert has_unique_constraint(AeirEvidenceModel, "project_id", "evidence_hash")
    assert AeirEvidenceModel.__table__.c.object_row_id.foreign_keys
    assert AeirEvidenceModel.__table__.c.relationship_row_id.foreign_keys
    assert has_unique_constraint(AeirObjectSourceLinkModel, "project_id", "link_hash")
    assert AeirObjectSourceLinkModel.__table__.c.object_row_id.foreign_keys
    assert has_unique_constraint(AeirRelationshipSourceLinkModel, "project_id", "link_hash")
    assert AeirRelationshipSourceLinkModel.__table__.c.relationship_row_id.foreign_keys
    assert has_unique_constraint(AeirClarificationQuestionModel, "question_hash")
    assert has_unique_constraint(AeirClarificationAnswerModel, "answer_hash")
    assert has_unique_constraint(AeirDecisionModel, "decision_hash")
    assert not has_unique_constraint(AeirAiOperationModel, "project_id", "operation_sha256")
    assert AeirAiOperationModel.__table__.c.operation_sha256.index
    assert AeirArtifactVersionModel.__table__.c.snapshot_row_id.foreign_keys
    assert has_unique_constraint(AeirArtifactVersionModel, "project_id", "artifact_hash")
    assert AeirArtifactTraceLinkModel.__table__.c.artifact_version_id.foreign_keys


def test_write_set_preserves_objects_relationships_versions_and_event_chain() -> None:
    model = project_model()
    project_id = uuid.uuid4()
    first = build_aeir_write_set(
        project_id=project_id,
        model=model,
        version_number=1,
        actor_id="client-reviewer",
        previous_event_hash=None,
    )
    second = build_aeir_write_set(
        project_id=project_id,
        model=model,
        version_number=2,
        actor_id="client-reviewer",
        previous_event_hash=first.event.event_hash,
    )

    assert first.version.model_sha256 == model.model_sha256
    assert len(first.objects) == len(model.objects)
    assert len(first.relationships) == len(model.relationships)
    assert {row.relationship_type for row in first.relationships} == {
        item.relationship_type for item in model.relationships
    }
    assert len(first.object_source_links) == sum(len(item.source_refs) for item in first.objects)
    assert len(first.relationship_source_links) == sum(
        len(item.relationship_document["source_refs"]) for item in first.relationships
    )
    assert len(first.evidence) == (
        sum(len(item.source_refs) + len(item.evidence_refs) for item in first.objects)
        + sum(
            len(item.relationship_document["source_refs"])
            + len(item.relationship_document["evidence_refs"])
            for item in first.relationships
        )
    )
    assert {row.object_id for row in first.objects} == {item.id for item in model.objects}
    assert second.event.previous_hash == first.event.event_hash
    assert second.event.event_hash != first.event.event_hash


def test_write_set_preserves_source_metadata_for_uploaded_manifest() -> None:
    model = project_model()
    project_id = uuid.uuid4()
    source = StoredObject(
        provider="local",
        bucket="aepm-sources",
        object_key=f"{project_id}/{model.source_manifest_sha256}",
        content_sha256=model.source_manifest_sha256,
        size_bytes=4096,
    )

    write_set = build_aeir_write_set(
        project_id=project_id,
        model=model,
        version_number=1,
        actor_id="client-reviewer",
        previous_event_hash=None,
        stored_source=source,
        original_filename="client-manifest.json",
        media_type="application/json",
        source_metadata={"stage": "client_blueprint_import"},
    )

    assert len(write_set.sources) == 1
    row = write_set.sources[0]
    assert row.storage_provider == "local"
    assert row.bucket == "aepm-sources"
    assert row.object_key == source.object_key
    assert row.content_sha256 == model.source_manifest_sha256
    assert row.original_filename == "client-manifest.json"
    assert row.source_metadata == {"stage": "client_blueprint_import"}
    assert write_set.event.payload["source_object_count"] == 1


def test_migration_is_linear_and_change_events_are_database_append_only() -> None:
    migration = (
        ROOT / "migrations/versions/f3a7c1d9e204_add_aeir_knowledge_storage.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: str | None = "f2c6a9e1b407"' in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert '"aeir_model_versions"' in migration
    assert "postgresql.JSONB" in migration


def test_r2_persistence_migration_is_linear_and_append_only() -> None:
    migration = (
        ROOT / "migrations/versions/0d4c2f9a7b81_add_r2_project_formation_records.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: str | None = "f3a7c1d9e204"' in migration
    for table in (
        "aeir_project_snapshots",
        "aeir_object_versions",
        "aeir_relationship_versions",
        "aeir_validation_findings",
        "aeir_clarification_answers",
        "aeir_decisions",
        "aeir_ai_operations",
        "aeir_artifact_versions",
        "aeir_artifact_trace_links",
    ):
        assert f'"{table}"' in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "approved', 'archived" in migration


def test_aeir_source_evidence_link_migration_is_linear_and_append_only() -> None:
    migration = (
        ROOT / "migrations/versions/5b8e1f7c3a29_add_aeir_source_evidence_links.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: str | None = "2a6d8f1e0c42"' in migration
    for table in (
        "aeir_evidence",
        "aeir_object_source_links",
        "aeir_relationship_source_links",
    ):
        assert f'"{table}"' in migration
    assert "object_row_id IS NOT NULL OR relationship_row_id IS NOT NULL" in migration
    assert '"project_id", "evidence_hash"' in migration
    assert "BEFORE UPDATE OR DELETE" in migration


def test_r2_hash_uniqueness_followup_migration_is_project_scoped() -> None:
    migration = (
        ROOT / "migrations/versions/7f4a1d2c9e35_scope_r2_hash_uniqueness_to_project.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: str | None = "0d4c2f9a7b81"' in migration
    assert "aeir_project_snapshots_snapshot_sha256_key" in migration
    assert "aeir_ai_operations_operation_sha256_key" in migration
    assert "aeir_artifact_versions_artifact_hash_key" in migration
    assert '["project_id", "snapshot_sha256"]' in migration
    assert '["project_id", "operation_sha256"]' in migration
    assert '["project_id", "artifact_hash"]' in migration


def test_aeir_model_hash_followup_migration_is_project_scoped() -> None:
    migration = (
        ROOT / "migrations/versions/9b2e7c4f6a10_scope_aeir_model_hash_to_project.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: str | None = "7f4a1d2c9e35"' in migration
    assert "aeir_model_versions_model_sha256_key" in migration
    assert "uq_aeir_model_versions_project_model_sha" in migration
    assert '["project_id", "model_sha256"]' in migration


def test_ai_operation_evidence_followup_migration_allows_repeated_operations() -> None:
    migration = (
        ROOT / "migrations/versions/2a6d8f1e0c42_allow_repeated_ai_operation_evidence.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: str | None = "9b2e7c4f6a10"' in migration
    assert "uq_aeir_ai_operations_project_operation_sha" in migration
    assert "ix_aeir_ai_operations_operation_sha256" in migration
    assert "unique=False" in migration


@pytest.mark.asyncio
async def test_local_object_store_is_content_addressed_and_hash_verified(tmp_path: Path) -> None:
    store = LocalContentAddressedObjectStore(tmp_path)
    project_id = uuid.uuid4()
    first = await store.put(project_id=project_id, content=b"client source")
    second = await store.put(project_id=project_id, content=b"client source")

    assert first == second
    assert await store.get(first) == b"client source"
    with pytest.raises(ValueError, match="LOCATOR-MISMATCH"):
        await store.get(
            StoredObject("s3", first.bucket, first.object_key, first.content_sha256, 13)
        )


@pytest.mark.asyncio
async def test_local_object_store_rejects_path_escape(tmp_path: Path) -> None:
    store = LocalContentAddressedObjectStore(tmp_path)
    invalid = StoredObject("local", "aepm-sources", "../../escape", "0" * 64, 0)

    with pytest.raises(ValueError, match="OUTSIDE-BUCKET"):
        await store.get(invalid)
