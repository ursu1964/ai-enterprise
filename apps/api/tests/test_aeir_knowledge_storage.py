import json
import uuid
from pathlib import Path

import pytest

from ai_enterprise.domain.aeir import compile_aepm
from ai_enterprise.domain.aepm import AepmManifest
from ai_enterprise.infrastructure.knowledge.aeir_repository import build_aeir_write_set
from ai_enterprise.infrastructure.knowledge.models import (
    AeirChangeEventModel,
    AeirModelVersionModel,
    AeirObjectModel,
    AeirRelationshipModel,
    AeirSourceObjectModel,
)
from ai_enterprise.infrastructure.knowledge.object_store import (
    LocalContentAddressedObjectStore,
    StoredObject,
)

ROOT = Path(__file__).resolve().parents[3]


def project_model():
    document = json.loads(
        (ROOT / "examples/sample-project/aepm-0.1.json").read_text(encoding="utf-8")
    )
    return compile_aepm(AepmManifest.model_validate(document))


def test_aeir_storage_schema_has_relational_and_jsonb_boundaries() -> None:
    assert AeirModelVersionModel.__table__.c.model_document.type.__class__.__name__ == "JSONB"
    assert AeirObjectModel.__table__.c.attributes.type.__class__.__name__ == "JSONB"
    assert AeirRelationshipModel.__table__.c.source_object_id.foreign_keys
    assert AeirRelationshipModel.__table__.c.target_object_id.foreign_keys
    assert AeirSourceObjectModel.__table__.c.object_key.type.length is None
    assert AeirChangeEventModel.__table__.c.event_hash.unique


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
    assert {row.object_id for row in first.objects} == {item.id for item in model.objects}
    assert second.event.previous_hash == first.event.event_hash
    assert second.event.event_hash != first.event.event_hash


def test_migration_is_linear_and_change_events_are_database_append_only() -> None:
    migration = (
        ROOT / "migrations/versions/f3a7c1d9e204_add_aeir_knowledge_storage.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: str | None = "f2c6a9e1b407"' in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert '"aeir_model_versions"' in migration
    assert "postgresql.JSONB" in migration


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
