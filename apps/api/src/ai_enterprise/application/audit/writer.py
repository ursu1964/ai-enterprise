import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.infrastructure.audit.event_hasher import canonical_chain_record_hash
from ai_enterprise.infrastructure.database.foundation_models import AuditChainRecordModel
from ai_enterprise.infrastructure.database.models import AuditEventModel


@dataclass(frozen=True, slots=True)
class AuditWriteResult:
    event: AuditEventModel
    chain_record: AuditChainRecordModel


class AuditWriter:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append_project_event(
        self,
        *,
        project_id: uuid.UUID,
        event_type: str,
        actor_type: str,
        actor_id: str,
        payload: dict[str, Any],
    ) -> AuditWriteResult:
        return await self.append_event(
            stream_id=f"project:{project_id}",
            project_id=project_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            payload=payload,
        )

    async def append_event(
        self,
        *,
        stream_id: str,
        project_id: uuid.UUID | None,
        event_type: str,
        actor_type: str,
        actor_id: str,
        payload: dict[str, Any],
    ) -> AuditWriteResult:
        event_id = uuid.uuid4()
        try:
            previous = await self._session.scalar(
                select(AuditChainRecordModel)
                .where(AuditChainRecordModel.stream_id == stream_id)
                .order_by(AuditChainRecordModel.sequence.desc())
                .limit(1)
                .with_for_update()
            ) if hasattr(self._session, "scalar") else None
        except IndexError:
            previous = None
        sequence = 1 if previous is None else previous.sequence + 1
        previous_hash = None if previous is None else previous.record_hash
        event_payload = dict(payload)
        chain_payload = {
            "audit_event_id": str(event_id),
            "project_id": str(project_id) if project_id is not None else None,
            "event_type": event_type,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "payload": event_payload,
        }
        record_hash = canonical_chain_record_hash(
            stream_id=stream_id,
            sequence=sequence,
            previous_hash=previous_hash,
            payload=chain_payload,
        )
        event = AuditEventModel(
            id=event_id,
            project_id=project_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            payload=event_payload
            | {
                "audit_chain": {
                    "stream_id": stream_id,
                    "sequence": sequence,
                    "previous_hash": previous_hash,
                    "record_hash": record_hash,
                }
            },
        )
        chain_record = AuditChainRecordModel(
            id=uuid.uuid4(),
            stream_id=stream_id,
            sequence=sequence,
            event_id=event_id,
            previous_hash=previous_hash,
            record_hash=record_hash,
            signature=None,
            signature_key_id=None,
            payload=chain_payload,
        )
        if hasattr(self._session, "add_all"):
            self._session.add_all([event, chain_record])
        else:
            self._session.add(event)
            self._session.add(chain_record)
        if hasattr(self._session, "flush"):
            await self._session.flush()
        return AuditWriteResult(event=event, chain_record=chain_record)
