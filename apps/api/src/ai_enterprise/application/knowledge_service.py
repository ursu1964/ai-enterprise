import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.audit.writer import AuditWriter
from ai_enterprise.application.organization_persistence_service import canonical_hash
from ai_enterprise.infrastructure.agent_runtime.models import (
    AgentRuntimeSessionModel,
    SkillVersionModel,
)
from ai_enterprise.infrastructure.knowledge.models import (
    KnowledgeCandidateEvidenceModel,
    KnowledgeCandidateModel,
    KnowledgeItemModel,
    KnowledgeItemVersionModel,
    KnowledgePromotionReviewModel,
    KnowledgeSourceModel,
)
from ai_enterprise.observability import increment_metric

CLASSIFICATIONS = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
ELIGIBLE_SOURCES = {
    "requirements-artifact",
    "architecture-artifact",
    "repository-commit",
    "test-result",
    "patch-review",
    "integration-result",
    "incident-report",
    "runtime-escalation",
}
HUMAN_REVIEW_TYPES = {
    "lesson",
    "procedure",
    "constraint",
    "pattern",
    "anti_pattern",
    "risk",
    "decision_rationale",
}


class KnowledgeError(ValueError):
    def __init__(self, detail: str, status_code: int = 409) -> None:
        super().__init__(detail)
        self.status_code = status_code


class KnowledgeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _audit(
        self, event: str, project_id: uuid.UUID | None, payload: dict[str, Any]
    ) -> None:
        await AuditWriter(self.session).append_event(
            stream_id=f"project:{project_id}" if project_id else "knowledge:platform",
            project_id=project_id,
            event_type=event,
            actor_type="knowledge-system",
            actor_id="governed-knowledge",
            payload=payload,
        )

    async def register_source(
        self,
        *,
        source_type: str,
        source_id: uuid.UUID,
        source_hash: str,
        organization_id: uuid.UUID,
        project_id: uuid.UUID | None,
        classification: str,
        trust_level: str,
        occurred_at: datetime,
    ) -> KnowledgeSourceModel:
        existing = await self.session.scalar(
            select(KnowledgeSourceModel).where(
                KnowledgeSourceModel.source_type == source_type,
                KnowledgeSourceModel.source_id == source_id,
                KnowledgeSourceModel.source_hash == source_hash,
            )
        )
        if existing:
            return existing
        row = KnowledgeSourceModel(
            id=uuid.uuid4(),
            source_type=source_type,
            source_id=source_id,
            source_hash=source_hash,
            organization_id=organization_id,
            project_id=project_id,
            classification=classification,
            trust_level=trust_level,
            occurred_at=occurred_at,
        )
        self.session.add(row)
        await self._audit(
            "KnowledgeSourceRegistered",
            project_id,
            {"source_id": str(row.id), "source_hash": source_hash},
        )
        increment_metric(f"knowledge_sources_registered.{source_type}.{classification}")
        await self.session.commit()
        return row

    async def extract(
        self,
        source: KnowledgeSourceModel,
        source_hash: str,
        runtime_session_id: uuid.UUID,
        skill_version_id: uuid.UUID,
        candidates: list[dict[str, Any]],
    ) -> list[KnowledgeCandidateModel]:
        if source.source_type not in ELIGIBLE_SOURCES:
            raise KnowledgeError("KNOW-009 SOURCE_NOT_ELIGIBLE")
        if source.source_hash != source_hash:
            raise KnowledgeError("KNOW-002 SOURCE_HASH_MISMATCH")
        runtime = await self.session.get(AgentRuntimeSessionModel, runtime_session_id)
        skill = await self.session.get(SkillVersionModel, skill_version_id)
        if runtime is None or runtime.status != "completed":
            raise KnowledgeError("Governed completed runtime required", 403)
        if skill is None or skill.approval_status != "approved":
            raise KnowledgeError("Approved extraction skill required", 403)
        rows: list[KnowledgeCandidateModel] = []
        for document in candidates:
            findings = self._validate(source, document)
            candidate_document = {
                **document,
                "source_id": str(source.id),
                "source_hash": source.source_hash,
            }
            candidate_hash = canonical_hash(candidate_document)
            if await self.session.scalar(
                select(KnowledgeCandidateModel.id).where(
                    KnowledgeCandidateModel.candidate_hash == candidate_hash
                )
            ):
                raise KnowledgeError("KNOW-006 DUPLICATE_CANDIDATE")
            row = KnowledgeCandidateModel(
                id=uuid.uuid4(),
                candidate_type=document["candidate_type"],
                title=document["title"],
                statement=document["statement"],
                scope_type=document["scope_type"],
                scope_id=document["scope_id"],
                classification=document["classification"],
                confidence_band=document["confidence_band"],
                status="validation_failed" if findings else "awaiting_review",
                candidate_document=candidate_document,
                candidate_hash=candidate_hash,
                proposed_by_actor_type="agent",
                proposed_by_actor_id=runtime.agent_profile_id,
                runtime_session_id=runtime.id,
                extraction_skill_version_id=skill.id,
                validation_findings=findings,
            )
            self.session.add(row)
            for locator in document["evidence_locators"]:
                self.session.add(
                    KnowledgeCandidateEvidenceModel(
                        candidate_id=row.id,
                        knowledge_source_id=source.id,
                        relation="supports",
                        evidence_locator=locator,
                    )
                )
            rows.append(row)
        await self._audit(
            "KnowledgeCandidatesExtracted",
            source.project_id,
            {
                "source_id": str(source.id),
                "candidate_hashes": [r.candidate_hash for r in rows],
                "runtime_session_id": str(runtime.id),
                "skill_version_id": str(skill.id),
            },
        )
        increment_metric("knowledge_candidates_extracted", len(rows))
        await self.session.commit()
        return rows

    @staticmethod
    def _validate(source: KnowledgeSourceModel, document: dict[str, Any]) -> list[dict[str, str]]:
        findings: list[dict[str, str]] = []
        if not document.get("evidence_locators"):
            findings.append({"code": "KNOW-003", "message": "EVIDENCE_LOCATOR_INVALID"})
        if CLASSIFICATIONS.get(document["classification"], -1) < CLASSIFICATIONS.get(
            source.classification, 99
        ):
            findings.append({"code": "KNOW-005", "message": "CLASSIFICATION_DOWNGRADE"})
        if re.search(r"(?i)(password|secret|api[_ -]?key)\s*[:=]", document["statement"]):
            findings.append({"code": "KNOW-008", "message": "SECRET_DETECTED"})
        return findings

    async def review_and_promote(
        self, candidate: KnowledgeCandidateModel, values: dict[str, Any]
    ) -> KnowledgeItemModel | None:
        if candidate.candidate_hash != values["candidate_hash"]:
            raise KnowledgeError("Candidate hash mismatch")
        if candidate.status != "awaiting_review":
            raise KnowledgeError("Candidate is not awaiting review")
        if candidate.proposed_by_actor_id == values["reviewer_id"]:
            raise KnowledgeError("Independent reviewer required", 403)
        evidence = list(
            (
                await self.session.scalars(
                    select(KnowledgeCandidateEvidenceModel).where(
                        KnowledgeCandidateEvidenceModel.candidate_id == candidate.id
                    )
                )
            ).all()
        )
        evidence_document = [
            {
                "source_id": str(e.knowledge_source_id),
                "relation": e.relation,
                "locator": e.evidence_locator,
                "quotation_hash": e.quotation_hash,
            }
            for e in evidence
        ]
        review = KnowledgePromotionReviewModel(
            id=uuid.uuid4(),
            candidate_id=candidate.id,
            decision=values["decision"],
            reviewer_id=values["reviewer_id"],
            candidate_hash=candidate.candidate_hash,
            evidence_hash=canonical_hash(evidence_document),
            policy_version=values["policy_version"],
            comments=values.get("comments"),
            review_scope=values.get("review_scope", "project"),
        )
        self.session.add(review)
        if values["decision"] != "promote":
            candidate.status = "rejected" if values["decision"] == "reject" else "proposed"
            await self.session.commit()
            return None
        if candidate.scope_type == "organization" and review.review_scope != "organization":
            raise KnowledgeError("Separate organizational approval required", 403)
        knowledge_key = values.get("knowledge_key")
        if not knowledge_key:
            raise KnowledgeError("Policy-controlled knowledge key required")
        version = (
            await self.session.scalar(
                select(func.max(KnowledgeItemModel.version_number)).where(
                    KnowledgeItemModel.knowledge_key == knowledge_key
                )
            )
            or 0
        )
        document = {
            "knowledge_key": knowledge_key,
            "version_number": version + 1,
            "candidate_hash": candidate.candidate_hash,
            "statement": candidate.statement,
            "scope_type": candidate.scope_type,
            "scope_id": str(candidate.scope_id),
        }
        item = KnowledgeItemModel(
            id=uuid.uuid4(),
            knowledge_key=knowledge_key,
            version_number=version + 1,
            item_type=candidate.candidate_type,
            title=candidate.title,
            statement=candidate.statement,
            scope_type=candidate.scope_type,
            scope_id=candidate.scope_id,
            classification=candidate.classification,
            trust_level="reviewed",
            temporal_status="current",
            valid_from=datetime.now(UTC),
            evidence_manifest=evidence_document,
            evidence_manifest_hash=review.evidence_hash,
            knowledge_document=document,
            knowledge_hash=canonical_hash(document),
            promoted_from_candidate_id=candidate.id,
            promotion_review_id=review.id,
        )
        self.session.add_all(
            (
                item,
                KnowledgeItemVersionModel(
                    id=uuid.uuid4(),
                    knowledge_item_id=item.id,
                    version_number=item.version_number,
                    version_document=document,
                    version_hash=item.knowledge_hash,
                ),
            )
        )
        candidate.status = "promoted"
        await self._audit(
            "KnowledgeCandidatePromoted",
            candidate.scope_id if candidate.scope_type == "project" else None,
            {
                "candidate_id": str(candidate.id),
                "item_id": str(item.id),
                "candidate_hash": candidate.candidate_hash,
                "evidence_hash": review.evidence_hash,
            },
        )
        increment_metric(
            f"knowledge_promotions.{candidate.candidate_type}.{candidate.classification}"
        )
        await self.session.commit()
        return item
