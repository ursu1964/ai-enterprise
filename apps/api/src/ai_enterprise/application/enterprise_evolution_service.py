from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.organization_persistence_service import canonical_hash
from ai_enterprise.domain.specification.kernel import semantic_version
from ai_enterprise.infrastructure.database.models import AuditEventModel
from ai_enterprise.infrastructure.enterprise_evolution.models import (
    EnterpriseEvolutionArtifactModel,
    EnterpriseEvolutionDecisionModel,
    EnterpriseImprovementModel,
    EnterpriseImprovementTransitionModel,
)
from ai_enterprise.infrastructure.performance.models import PerformanceEvidenceModel
from ai_enterprise.infrastructure.specification.models import EngineeringEvidenceNodeModel
from ai_enterprise.observability import increment_metric

CATEGORIES = {
    "architecture",
    "generator",
    "workflow",
    "policy",
    "agent",
    "infrastructure",
    "security",
    "performance",
    "developer_experience",
    "operations",
    "governance",
}
ARTIFACT_TYPES = {
    "learning_hypothesis",
    "pattern",
    "anti_pattern",
    "recommendation",
    "simulation",
    "experiment",
    "generator_evolution",
    "policy_evolution",
    "ai_workforce_evolution",
    "capability_evolution",
    "maturity_assessment",
    "benchmark",
    "roadmap",
    "refactoring_plan",
    "self_reflection",
}
ARTIFACT_CATEGORIES = {
    "generator_evolution": {"generator"},
    "policy_evolution": {"policy", "governance"},
    "ai_workforce_evolution": {"agent"},
    "capability_evolution": {"agent", "governance"},
    "maturity_assessment": {"governance"},
    "benchmark": {"performance"},
    "roadmap": {"governance"},
    "refactoring_plan": {"architecture", "infrastructure", "workflow"},
    "self_reflection": {"governance"},
}
LIFECYCLE = (
    "proposed",
    "analyzed",
    "simulated",
    "reviewed",
    "approved",
    "implemented",
    "measured",
    "accepted",
    "archived",
)
MAX_DOCUMENT_BYTES = 1_048_576


class EnterpriseEvolutionError(ValueError):
    def __init__(self, detail: str, status_code: int = 409) -> None:
        super().__init__(detail)
        self.status_code = status_code


class EnterpriseEvolutionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _audit(self, event: str, actor: str, payload: dict[str, Any]) -> None:
        self.session.add(
            AuditEventModel(
                project_id=None,
                event_type=event,
                actor_type="enterprise-evolution",
                actor_id=actor,
                payload=payload,
            )
        )

    async def _evidence(
        self, organization_id: uuid.UUID, references: list[dict[str, str]]
    ) -> tuple[list[str], str]:
        if not references:
            raise EnterpriseEvolutionError("EVO-001 EVIDENCE-REQUIRED", 422)
        verified: list[tuple[str, str, str]] = []
        for reference in references:
            kind, identity, expected_hash = (
                reference.get("type"),
                reference.get("id"),
                reference.get("hash"),
            )
            try:
                item_id = uuid.UUID(str(identity))
            except ValueError as exc:
                raise EnterpriseEvolutionError("EVO-002 INVALID-EVIDENCE-REFERENCE", 422) from exc
            if kind == "performance":
                performance_row = await self.session.get(PerformanceEvidenceModel, item_id)
                actual_hash = (
                    performance_row.evidence_hash
                    if performance_row and performance_row.organization_id == organization_id
                    else None
                )
            elif kind == "engineering":
                engineering_row = await self.session.get(EngineeringEvidenceNodeModel, item_id)
                actual_hash = (
                    engineering_row.node_hash
                    if engineering_row and engineering_row.organization_id == organization_id
                    else None
                )
            elif kind == "evolution":
                evolution_row = await self.session.get(EnterpriseEvolutionArtifactModel, item_id)
                actual_hash = (
                    evolution_row.artifact_hash
                    if evolution_row and evolution_row.organization_id == organization_id
                    else None
                )
            else:
                raise EnterpriseEvolutionError("EVO-003 EVIDENCE-TYPE-DENIED", 422)
            if actual_hash != expected_hash:
                raise EnterpriseEvolutionError("EVO-004 EVIDENCE-HASH-OR-SCOPE-MISMATCH", 422)
            verified.append((str(kind), str(item_id), str(actual_hash)))
        verified.sort()
        return [identity for _, identity, _ in verified], canonical_hash({"evidence": verified})

    async def propose(
        self,
        *,
        organization_id: uuid.UUID,
        improvement_key: str,
        category: str,
        origin: str,
        title: str,
        expected_benefit: str,
        risk_document: dict[str, Any],
        dependencies: list[str],
        evidence: list[dict[str, str]],
        proposed_by: str,
    ) -> EnterpriseImprovementModel:
        if category not in CATEGORIES:
            raise EnterpriseEvolutionError("EVO-005 CATEGORY-DENIED", 422)
        if improvement_key in dependencies:
            raise EnterpriseEvolutionError("EVO-007 SELF-DEPENDENCY-DENIED", 422)
        if dependencies:
            dependency_rows = list(
                (
                    await self.session.scalars(
                        select(EnterpriseImprovementModel).where(
                            EnterpriseImprovementModel.organization_id == organization_id,
                            EnterpriseImprovementModel.improvement_key.in_(dependencies),
                        )
                    )
                ).all()
            )
            if {row.improvement_key for row in dependency_rows} != set(dependencies):
                raise EnterpriseEvolutionError("EVO-009 DEPENDENCY-SCOPE-OR-LINEAGE-MISMATCH", 422)
        if len(json.dumps(risk_document, sort_keys=True).encode()) > MAX_DOCUMENT_BYTES:
            raise EnterpriseEvolutionError("EVO-006 DOCUMENT-TOO-LARGE", 413)
        evidence_ids, evidence_hash = await self._evidence(organization_id, evidence)
        document = {
            "organization_id": str(organization_id),
            "improvement_key": improvement_key,
            "category": category,
            "origin": origin,
            "title": title,
            "expected_benefit": expected_benefit,
            "risk": risk_document,
            "dependencies": sorted(dependencies),
            "evidence_set_hash": evidence_hash,
        }
        proposal_hash = canonical_hash(document)
        existing = await self.session.scalar(
            select(EnterpriseImprovementModel).where(
                EnterpriseImprovementModel.proposal_hash == proposal_hash
            )
        )
        if existing is not None:
            return existing
        key_conflict = await self.session.scalar(
            select(EnterpriseImprovementModel).where(
                EnterpriseImprovementModel.improvement_key == improvement_key
            )
        )
        if key_conflict is not None:
            raise EnterpriseEvolutionError("EVO-008 IMPROVEMENT-KEY-CONFLICT")
        now = datetime.now(UTC)
        row = EnterpriseImprovementModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            improvement_key=improvement_key,
            category=category,
            origin=origin,
            title=title,
            expected_benefit=expected_benefit,
            risk_document=risk_document,
            dependencies=sorted(set(dependencies)),
            evidence_ids=evidence_ids,
            evidence_set_hash=evidence_hash,
            proposal_document=document,
            proposal_hash=proposal_hash,
            proposed_by=proposed_by,
            proposed_at=now,
        )
        transition = EnterpriseImprovementTransitionModel(
            id=uuid.uuid4(),
            improvement_id=row.id,
            sequence=1,
            from_state=None,
            to_state="proposed",
            evidence_artifact_ids=evidence_ids,
            evidence_set_hash=evidence_hash,
            decision_id=None,
            transitioned_by=proposed_by,
            transitioned_at=now,
        )
        self.session.add(row)
        self.session.add(transition)
        self._audit(
            "EnterpriseImprovementProposed",
            proposed_by,
            {"improvement_id": str(row.id), "proposal_hash": proposal_hash},
        )
        increment_metric(f"enterprise_evolution.improvements.{category}")
        await self.session.commit()
        return row

    async def record_artifact(
        self,
        *,
        organization_id: uuid.UUID,
        improvement_id: uuid.UUID | None,
        artifact_type: str,
        artifact_key: str,
        version: str,
        document: dict[str, Any],
        evidence: list[dict[str, str]],
        created_by: str,
        parent_artifact_id: uuid.UUID | None = None,
    ) -> EnterpriseEvolutionArtifactModel:
        if artifact_type not in ARTIFACT_TYPES:
            raise EnterpriseEvolutionError("EVO-010 ARTIFACT-TYPE-DENIED", 422)
        if len(json.dumps(document, sort_keys=True).encode()) > MAX_DOCUMENT_BYTES:
            raise EnterpriseEvolutionError("EVO-006 DOCUMENT-TOO-LARGE", 413)
        if improvement_id is not None:
            improvement = await self.session.get(EnterpriseImprovementModel, improvement_id)
            if improvement is None or improvement.organization_id != organization_id:
                raise EnterpriseEvolutionError("EVO-011 IMPROVEMENT-SCOPE-MISMATCH", 403)
            allowed_categories = ARTIFACT_CATEGORIES.get(artifact_type)
            if allowed_categories is not None and improvement.category not in allowed_categories:
                raise EnterpriseEvolutionError("EVO-014 ARTIFACT-CATEGORY-MISMATCH", 422)
        if parent_artifact_id is not None:
            parent = await self.session.get(EnterpriseEvolutionArtifactModel, parent_artifact_id)
            if parent is None or parent.organization_id != organization_id:
                raise EnterpriseEvolutionError("EVO-012 PARENT-SCOPE-MISMATCH", 403)
            if (
                parent.artifact_type != artifact_type
                or parent.artifact_key != artifact_key
                or semantic_version(version) <= semantic_version(parent.version)
            ):
                raise EnterpriseEvolutionError("EVO-013 INVALID-ARTIFACT-REVISION", 422)
        evidence_ids, evidence_hash = await self._evidence(organization_id, evidence)
        bound = {
            "organization_id": str(organization_id),
            "improvement_id": str(improvement_id) if improvement_id else None,
            "artifact_type": artifact_type,
            "artifact_key": artifact_key,
            "version": version,
            "document": document,
            "evidence_set_hash": evidence_hash,
            "parent_artifact_id": str(parent_artifact_id) if parent_artifact_id else None,
        }
        artifact_hash = canonical_hash(bound)
        existing = await self.session.scalar(
            select(EnterpriseEvolutionArtifactModel).where(
                EnterpriseEvolutionArtifactModel.artifact_hash == artifact_hash
            )
        )
        if existing is not None:
            return existing
        row = EnterpriseEvolutionArtifactModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            improvement_id=improvement_id,
            artifact_type=artifact_type,
            artifact_key=artifact_key,
            version=version,
            artifact_document=document,
            artifact_hash=artifact_hash,
            evidence_ids=evidence_ids,
            evidence_set_hash=evidence_hash,
            parent_artifact_id=parent_artifact_id,
            created_by=created_by,
            created_at=datetime.now(UTC),
        )
        self.session.add(row)
        self._audit(
            "EnterpriseEvolutionArtifactRecorded",
            created_by,
            {
                "artifact_id": str(row.id),
                "artifact_type": artifact_type,
                "artifact_hash": artifact_hash,
            },
        )
        increment_metric(f"enterprise_evolution.artifacts.{artifact_type}")
        await self.session.commit()
        return row

    async def decide(
        self,
        *,
        organization_id: uuid.UUID,
        target_type: str,
        target_id: uuid.UUID,
        target_hash: str,
        decision: str,
        decided_by: str,
        board_role: str,
        rationale: str,
        expires_at: datetime | None = None,
    ) -> EnterpriseEvolutionDecisionModel:
        if decision not in {"approve", "reject"} or not rationale.strip():
            raise EnterpriseEvolutionError("EVO-020 INVALID-DECISION", 422)
        if target_type == "improvement":
            improvement_target = await self.session.get(EnterpriseImprovementModel, target_id)
            actual = (
                improvement_target.proposal_hash
                if improvement_target and improvement_target.organization_id == organization_id
                else None
            )
            creator = improvement_target.proposed_by if improvement_target else None
        elif target_type == "artifact":
            artifact_target = await self.session.get(EnterpriseEvolutionArtifactModel, target_id)
            actual = (
                artifact_target.artifact_hash
                if artifact_target and artifact_target.organization_id == organization_id
                else None
            )
            creator = artifact_target.created_by if artifact_target else None
        else:
            raise EnterpriseEvolutionError("EVO-021 TARGET-TYPE-DENIED", 422)
        if actual != target_hash:
            raise EnterpriseEvolutionError("EVO-022 TARGET-HASH-OR-SCOPE-MISMATCH", 422)
        if creator == decided_by:
            raise EnterpriseEvolutionError("EVO-023 INDEPENDENT-DECISION-REQUIRED", 403)
        existing = await self.session.scalar(
            select(EnterpriseEvolutionDecisionModel).where(
                EnterpriseEvolutionDecisionModel.target_type == target_type,
                EnterpriseEvolutionDecisionModel.target_id == target_id,
                EnterpriseEvolutionDecisionModel.target_hash == target_hash,
                EnterpriseEvolutionDecisionModel.decision == decision,
            )
        )
        if existing is not None:
            return existing
        row = EnterpriseEvolutionDecisionModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            target_type=target_type,
            target_id=target_id,
            target_hash=target_hash,
            decision=decision,
            decided_by=decided_by,
            board_role=board_role,
            rationale=rationale,
            expires_at=expires_at,
            decided_at=datetime.now(UTC),
        )
        self.session.add(row)
        self._audit(
            "EnterpriseEvolutionHumanDecision",
            decided_by,
            {"decision_id": str(row.id), "target_hash": target_hash, "decision": decision},
        )
        await self.session.commit()
        return row

    async def transition(
        self,
        improvement: EnterpriseImprovementModel,
        *,
        to_state: str,
        evidence_artifact_ids: list[uuid.UUID],
        transitioned_by: str,
        decision_id: uuid.UUID | None = None,
    ) -> EnterpriseImprovementTransitionModel:
        current = await self.session.scalar(
            select(EnterpriseImprovementTransitionModel)
            .where(EnterpriseImprovementTransitionModel.improvement_id == improvement.id)
            .order_by(EnterpriseImprovementTransitionModel.sequence.desc())
            .limit(1)
            .with_for_update()
        )
        if current is None or to_state not in LIFECYCLE:
            raise EnterpriseEvolutionError("EVO-030 INVALID-TRANSITION")
        expected = (
            LIFECYCLE[LIFECYCLE.index(current.to_state) + 1]
            if current.to_state != "archived"
            else None
        )
        if to_state != expected:
            raise EnterpriseEvolutionError("EVO-031 NON-SEQUENTIAL-TRANSITION")
        artifacts = list(
            (
                await self.session.scalars(
                    select(EnterpriseEvolutionArtifactModel).where(
                        EnterpriseEvolutionArtifactModel.id.in_(evidence_artifact_ids),
                        EnterpriseEvolutionArtifactModel.organization_id
                        == improvement.organization_id,
                        EnterpriseEvolutionArtifactModel.improvement_id == improvement.id,
                    )
                )
            ).all()
        )
        if len(artifacts) != len(set(evidence_artifact_ids)):
            raise EnterpriseEvolutionError("EVO-032 ARTIFACT-EVIDENCE-MISMATCH", 422)
        if not artifacts:
            raise EnterpriseEvolutionError("EVO-035 TRANSITION-EVIDENCE-REQUIRED", 422)
        required_type = {
            "analyzed": "learning_hypothesis",
            "simulated": "simulation",
            "implemented": "refactoring_plan",
            "measured": "benchmark",
            "accepted": "self_reflection",
        }.get(to_state)
        if required_type and not any(row.artifact_type == required_type for row in artifacts):
            raise EnterpriseEvolutionError(f"EVO-033 {required_type.upper()}-REQUIRED", 422)
        decision = None
        if to_state == "approved":
            decision = await self.session.get(EnterpriseEvolutionDecisionModel, decision_id)
            if (
                decision is None
                or decision.target_type != "improvement"
                or decision.target_id != improvement.id
                or decision.target_hash != improvement.proposal_hash
                or decision.decision != "approve"
                or (decision.expires_at is not None and decision.expires_at <= datetime.now(UTC))
            ):
                raise EnterpriseEvolutionError("EVO-034 HUMAN-APPROVAL-REQUIRED", 403)
        evidence_hash = canonical_hash(
            {"artifacts": sorted((str(row.id), row.artifact_hash) for row in artifacts)}
        )
        row = EnterpriseImprovementTransitionModel(
            id=uuid.uuid4(),
            improvement_id=improvement.id,
            sequence=current.sequence + 1,
            from_state=current.to_state,
            to_state=to_state,
            evidence_artifact_ids=[str(item.id) for item in artifacts],
            evidence_set_hash=evidence_hash,
            decision_id=decision.id if decision else None,
            transitioned_by=transitioned_by,
            transitioned_at=datetime.now(UTC),
        )
        self.session.add(row)
        self._audit(
            "EnterpriseImprovementTransitioned",
            transitioned_by,
            {
                "improvement_id": str(improvement.id),
                "from": current.to_state,
                "to": to_state,
                "evidence_set_hash": evidence_hash,
            },
        )
        increment_metric(f"enterprise_evolution.transitions.{to_state}")
        await self.session.commit()
        return row


class EnterpriseEvolutionWorker:
    """Workers may record evidence-backed analysis; they cannot approve or transition adoption."""

    def __init__(self, session: AsyncSession, worker_id: str) -> None:
        self.service = EnterpriseEvolutionService(session)
        self.worker_id = worker_id

    async def record_analysis(self, **values: Any) -> EnterpriseEvolutionArtifactModel:
        if values.get("artifact_type") not in ARTIFACT_TYPES:
            raise EnterpriseEvolutionError("EVO-010 ARTIFACT-TYPE-DENIED", 422)
        values.pop("created_by", None)
        return await self.service.record_artifact(**values, created_by=self.worker_id)
