from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.audit.writer import AuditWriter
from ai_enterprise.application.organization_persistence_service import canonical_hash
from ai_enterprise.domain.specification.kernel import semantic_version
from ai_enterprise.infrastructure.cognitive.models import (
    CognitiveDecisionModel,
    CognitiveLinkModel,
    CognitiveRecordModel,
)
from ai_enterprise.observability import increment_metric

RECORD_TYPES = {
    "semantic_object",
    "ontology",
    "reasoning",
    "executive_question",
    "scenario",
    "simulation",
    "digital_twin",
    "cognitive_memory",
    "synthesis",
    "recommendation",
    "strategic_objective",
    "dashboard_snapshot",
    "cross_domain_reasoning",
    "strategic_memory",
    "cognitive_policy",
    "strategic_intelligence",
}
WORKER_TYPES = {
    "reasoning",
    "simulation",
    "digital_twin",
    "synthesis",
    "dashboard_snapshot",
    "cross_domain_reasoning",
    "strategic_intelligence",
}
RELATIONSHIPS = {"supports", "derived_from", "measures", "affects", "contradicts", "depends_on"}
MAX_DOCUMENT_BYTES = 1_048_576
SENSITIVE_FIELDS = {"password", "secret", "token", "api_key", "private_key", "credential"}


class CognitiveError(ValueError):
    def __init__(self, detail: str, status_code: int = 409) -> None:
        super().__init__(detail)
        self.status_code = status_code


class CognitiveService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _audit(
        self, event: str, organization_id: uuid.UUID, actor: str, payload: dict[str, Any]
    ) -> None:
        await AuditWriter(self.session).append_event(
            stream_id=f"cognitive:{organization_id}",
            project_id=None,
            event_type=event,
            actor_type="cognitive-governance",
            actor_id=actor,
            payload=payload,
        )

    @staticmethod
    def _validate_document(document: dict[str, Any]) -> None:
        if len(json.dumps(document, sort_keys=True).encode()) > MAX_DOCUMENT_BYTES:
            raise CognitiveError("COG-001 DOCUMENT-TOO-LARGE", 413)

        def sensitive(value: Any) -> bool:
            if isinstance(value, dict):
                return any(
                    str(key).lower().replace("-", "_") in SENSITIVE_FIELDS or sensitive(item)
                    for key, item in value.items()
                )
            return isinstance(value, list) and any(sensitive(item) for item in value)

        if sensitive(document):
            raise CognitiveError("COG-002 SECRET-MATERIAL-DENIED", 422)

    async def register(
        self,
        *,
        organization_id: uuid.UUID,
        record_type: str,
        record_key: str,
        version: str,
        document: dict[str, Any],
        evidence: list[dict[str, str]],
        classification: str,
        confidence: float | None,
        parent_record_id: uuid.UUID | None,
        created_by: str,
    ) -> CognitiveRecordModel:
        if record_type not in RECORD_TYPES:
            raise CognitiveError("COG-010 RECORD-TYPE-DENIED", 422)
        if classification not in {"public", "internal", "confidential", "restricted"}:
            raise CognitiveError("COG-013 CLASSIFICATION-DENIED", 422)
        self._validate_document(document)
        if not evidence or any(
            set(item) != {"type", "id", "hash"}
            or not (1 <= len(item["type"]) <= 80 and 1 <= len(item["id"]) <= 240)
            or len(item["hash"]) != 64
            or any(char not in "0123456789abcdef" for char in item["hash"])
            for item in evidence
        ):
            raise CognitiveError("COG-011 EVIDENCE-PROVENANCE-INVALID", 422)
        manifest = sorted(evidence, key=lambda item: (item["type"], item["id"], item["hash"]))
        evidence_hash = canonical_hash({"evidence": manifest})
        if parent_record_id:
            parent = await self.session.get(CognitiveRecordModel, parent_record_id)
            if (
                parent is None
                or parent.organization_id != organization_id
                or parent.record_type != record_type
                or parent.record_key != record_key
                or semantic_version(version) <= semantic_version(parent.version)
            ):
                raise CognitiveError("COG-012 INVALID-LINEAGE", 422)
        bound = {
            "organization_id": str(organization_id),
            "record_type": record_type,
            "record_key": record_key,
            "version": version,
            "document": document,
            "evidence_hash": evidence_hash,
            "classification": classification,
            "parent_record_id": str(parent_record_id) if parent_record_id else None,
            "confidence": confidence,
        }
        digest = canonical_hash(bound)
        existing = await self.session.scalar(
            select(CognitiveRecordModel).where(CognitiveRecordModel.record_hash == digest)
        )
        if existing is not None:
            return existing
        row = CognitiveRecordModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            record_type=record_type,
            record_key=record_key,
            version=version,
            record_document=document,
            record_hash=digest,
            evidence_manifest=manifest,
            evidence_hash=evidence_hash,
            classification=classification,
            confidence=confidence,
            parent_record_id=parent_record_id,
            created_by=created_by,
            created_at=datetime.now(UTC),
        )
        self.session.add(row)
        await self._audit(
            "CognitiveRecordRegistered",
            organization_id,
            created_by,
            {"record_id": str(row.id), "record_type": record_type, "record_hash": digest},
        )
        increment_metric(f"cognitive.records.{record_type}")
        await self.session.commit()
        return row

    async def decide(
        self,
        record: CognitiveRecordModel,
        *,
        record_hash: str,
        decision: str,
        rationale: str,
        decided_by: str,
        decision_nonce: uuid.UUID,
    ) -> CognitiveDecisionModel:
        if record.record_hash != record_hash:
            raise CognitiveError("COG-020 RECORD-HASH-MISMATCH")
        if record.created_by == decided_by:
            raise CognitiveError("COG-021 INDEPENDENT-HUMAN-DECISION-REQUIRED", 403)
        if decision not in {"accept", "reject", "defer"} or not rationale.strip():
            raise CognitiveError("COG-022 INVALID-DECISION", 422)
        replay = await self.session.scalar(
            select(CognitiveDecisionModel).where(
                CognitiveDecisionModel.organization_id == record.organization_id,
                CognitiveDecisionModel.record_id == record.id,
                CognitiveDecisionModel.decision_nonce == decision_nonce,
            )
        )
        if replay is not None:
            if replay.record_hash != record_hash or replay.decision != decision:
                raise CognitiveError("COG-023 DECISION-NONCE-CONFLICT", 409)
            return replay
        row = CognitiveDecisionModel(
            id=uuid.uuid4(),
            organization_id=record.organization_id,
            record_id=record.id,
            record_hash=record_hash,
            decision_nonce=decision_nonce,
            decision=decision,
            rationale=rationale,
            decided_by=decided_by,
            decided_at=datetime.now(UTC),
        )
        self.session.add(row)
        await self._audit(
            "CognitiveRecordHumanDecision",
            record.organization_id,
            decided_by,
            {"record_id": str(record.id), "record_hash": record_hash, "decision": decision},
        )
        await self.session.commit()
        return row

    async def link(
        self,
        source: CognitiveRecordModel,
        target: CognitiveRecordModel,
        *,
        relationship: str,
        actor: str,
    ) -> CognitiveLinkModel:
        if source.id == target.id or source.organization_id != target.organization_id:
            raise CognitiveError("COG-030 CROSS-SCOPE-OR-SELF-LINK", 403)
        if relationship not in RELATIONSHIPS:
            raise CognitiveError("COG-031 RELATIONSHIP-TYPE-DENIED", 422)
        digest = canonical_hash(
            {
                "source": source.record_hash,
                "target": target.record_hash,
                "relationship": relationship,
            }
        )
        existing = await self.session.scalar(
            select(CognitiveLinkModel).where(CognitiveLinkModel.link_hash == digest)
        )
        if existing is not None:
            return existing
        row = CognitiveLinkModel(
            id=uuid.uuid4(),
            organization_id=source.organization_id,
            source_record_id=source.id,
            target_record_id=target.id,
            relationship=relationship,
            link_hash=digest,
            created_at=datetime.now(UTC),
        )
        self.session.add(row)
        await self._audit(
            "CognitiveLinkRegistered",
            source.organization_id,
            actor,
            {"link_id": str(row.id), "link_hash": digest},
        )
        await self.session.commit()
        return row


class CognitiveWorker:
    def __init__(self, session: AsyncSession, worker_id: str) -> None:
        self.service, self.worker_id = CognitiveService(session), worker_id

    async def produce(self, **values: Any) -> CognitiveRecordModel:
        if values.get("record_type") not in WORKER_TYPES:
            raise CognitiveError("COG-040 WORKER-HAS-NO-AUTHORITY", 403)
        values.pop("created_by", None)
        return await self.service.register(**values, created_by=self.worker_id)
