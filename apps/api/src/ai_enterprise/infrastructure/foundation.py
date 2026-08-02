import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.domain.foundation import EventEnvelope, SignatureProvider
from ai_enterprise.domain.hashing import hash_json
from ai_enterprise.infrastructure.audit.event_hasher import canonical_chain_record_hash
from ai_enterprise.infrastructure.database.foundation_models import (
    AuditChainRecordModel,
    ExternalEffectModel,
    OutboxEventModel,
)


class FoundationRepository:
    def __init__(self, session: AsyncSession, signer: SignatureProvider | None = None) -> None:
        self.session = session
        self.signer = signer

    async def append_event(self, event: EventEnvelope) -> AuditChainRecordModel:
        previous = await self.session.scalar(
            select(AuditChainRecordModel)
            .where(AuditChainRecordModel.stream_id == str(event.aggregate_id))
            .order_by(AuditChainRecordModel.sequence.desc())
            .limit(1)
            .with_for_update()
        )
        sequence = 1 if previous is None else previous.sequence + 1
        previous_hash = None if previous is None else previous.record_hash
        payload = event.model_dump(mode="json")
        record_hash = canonical_chain_record_hash(
            stream_id=str(event.aggregate_id),
            sequence=sequence,
            previous_hash=previous_hash,
            payload=payload,
        )
        signature = self.signer.sign(record_hash.encode()) if self.signer else None
        record = AuditChainRecordModel(
            id=uuid.uuid4(),
            stream_id=str(event.aggregate_id),
            sequence=sequence,
            event_id=event.event_id,
            previous_hash=previous_hash,
            record_hash=record_hash,
            signature=signature,
            signature_key_id=self.signer.key_id if self.signer else None,
            payload=payload,
        )
        outbox = OutboxEventModel(
            id=uuid.uuid4(),
            command_id=event.causation_id,
            event_type=event.event_type,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            payload=event.payload,
            attempts=0,
        )
        self.session.add_all([record, outbox])
        await self.session.flush()
        return record

    async def reserve_effect(
        self, *, key: str, effect_type: str, aggregate_id: uuid.UUID, request: dict[str, object]
    ) -> ExternalEffectModel:
        existing = await self.session.scalar(
            select(ExternalEffectModel).where(ExternalEffectModel.idempotency_key == key)
        )
        request_hash = hash_json(request)
        if existing is not None:
            if existing.request_hash != request_hash:
                raise ValueError("External-effect idempotency key is bound to another request")
            return existing
        effect = ExternalEffectModel(
            id=uuid.uuid4(),
            idempotency_key=key,
            effect_type=effect_type,
            aggregate_id=aggregate_id,
            request_hash=request_hash,
            status="pending",
        )
        self.session.add(effect)
        await self.session.flush()
        return effect
