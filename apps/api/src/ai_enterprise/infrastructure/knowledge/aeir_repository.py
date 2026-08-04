from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.domain.aeir import AeirProjectModel
from ai_enterprise.domain.specification.kernel import specification_hash
from ai_enterprise.infrastructure.database.models import ProjectModel
from ai_enterprise.infrastructure.knowledge.models import (
    AeirChangeEventModel,
    AeirModelVersionModel,
    AeirObjectModel,
    AeirRelationshipModel,
)


@dataclass(frozen=True)
class AeirWriteSet:
    version: AeirModelVersionModel
    objects: tuple[AeirObjectModel, ...]
    relationships: tuple[AeirRelationshipModel, ...]
    event: AeirChangeEventModel


def build_aeir_write_set(
    *,
    project_id: uuid.UUID,
    model: AeirProjectModel,
    version_number: int,
    actor_id: str,
    previous_event_hash: str | None,
) -> AeirWriteSet:
    version_id = uuid.uuid4()
    version = AeirModelVersionModel(
        id=version_id,
        project_id=project_id,
        version_number=version_number,
        schema_version=model.schema_version,
        source_manifest_sha256=model.source_manifest_sha256,
        model_sha256=model.model_sha256,
        model_document=model.model_dump(mode="json"),
        created_by=actor_id,
    )
    object_ids = {item.id: uuid.uuid4() for item in model.objects}
    objects = tuple(
        AeirObjectModel(
            id=object_ids[item.id],
            model_version_id=version_id,
            object_id=item.id,
            object_type=item.type,
            name=item.name,
            description=item.description,
            status=item.status,
            confidence=item.confidence,
            object_version=item.version,
            source_document=item.source.model_dump(mode="json"),
            attributes=item.attributes,
        )
        for item in model.objects
    )
    relationships = tuple(
        AeirRelationshipModel(
            id=uuid.uuid4(),
            model_version_id=version_id,
            relationship_id=item.id,
            relationship_type=item.relationship_type,
            source_object_id=object_ids[item.source_object_id],
            target_object_id=object_ids[item.target_object_id],
            relationship_document=item.model_dump(mode="json"),
        )
        for item in model.relationships
    )
    payload = {
        "schema_version": model.schema_version,
        "version_number": version_number,
        "model_sha256": model.model_sha256,
        "object_count": len(objects),
        "relationship_count": len(relationships),
    }
    event_hash = specification_hash(
        {
            "project_id": str(project_id),
            "sequence": version_number,
            "event_type": "aeir.model-version-created",
            "actor_id": actor_id,
            "previous_hash": previous_event_hash,
            "payload": payload,
        }
    )
    event = AeirChangeEventModel(
        id=uuid.uuid4(),
        project_id=project_id,
        model_version_id=version_id,
        sequence=version_number,
        event_type="aeir.model-version-created",
        actor_id=actor_id,
        previous_hash=previous_event_hash,
        event_hash=event_hash,
        payload=payload,
    )
    return AeirWriteSet(version, objects, relationships, event)


class SqlAlchemyAeirRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def append_model(
        self, *, project_id: uuid.UUID, model: AeirProjectModel, actor_id: str
    ) -> AeirWriteSet:
        project = await self.session.get(ProjectModel, project_id, with_for_update=True)
        if project is None:
            raise ValueError("AEIR-PROJECT-NOT-FOUND")
        version_number = (
            await self.session.scalar(
                select(func.max(AeirModelVersionModel.version_number)).where(
                    AeirModelVersionModel.project_id == project_id
                )
            )
            or 0
        ) + 1
        previous_event_hash = await self.session.scalar(
            select(AeirChangeEventModel.event_hash)
            .where(AeirChangeEventModel.project_id == project_id)
            .order_by(AeirChangeEventModel.sequence.desc())
            .limit(1)
        )
        write_set = build_aeir_write_set(
            project_id=project_id,
            model=model,
            version_number=version_number,
            actor_id=actor_id,
            previous_event_hash=previous_event_hash,
        )
        self.session.add(write_set.version)
        self.session.add_all(write_set.objects)
        self.session.add_all(write_set.relationships)
        self.session.add(write_set.event)
        await self.session.flush()
        return write_set
