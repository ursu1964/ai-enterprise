from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.organization_persistence_service import canonical_hash
from ai_enterprise.infrastructure.database.models import AuditEventModel
from ai_enterprise.infrastructure.performance.models import (
    CapabilityCertificationModel,
    CapabilityRecommendationModel,
    CertificationDecisionModel,
    LearningProposalModel,
    PerformanceEvidenceModel,
    PerformanceMetricModel,
    PerformanceTrendModel,
)
from ai_enterprise.observability import increment_metric

COMPLETION_EVENTS = {
    "requirements": {"RequirementsApproved", "RequirementsRevisionApproved"},
    "architecture": {"ArchitectureApproved", "ArchitectureArtifactApproved"},
    "planning": {"DecompositionApproved", "WorkPackagesMaterialized"},
    "implementation": {"ExecutionCompleted", "ExecutionSucceeded"},
    "review": {"PatchReviewApproved", "PatchReviewRejected"},
    "integration": {"IntegrationSucceeded", "IntegrationFailed"},
    "recovery": {"RecoveryCompleted", "RecoveryFailed"},
}
LEVELS = {"candidate", "certified", "senior", "expert", "principal", "specialist"}
MAX_EVIDENCE_BYTES = 262_144


class PerformanceGovernanceError(ValueError):
    def __init__(self, detail: str, status_code: int = 409) -> None:
        super().__init__(detail)
        self.status_code = status_code


class PerformanceIntegrationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _audit(
        self,
        event_type: str,
        actor_id: str,
        project_id: uuid.UUID | None,
        payload: dict[str, Any],
    ) -> None:
        self.session.add(
            AuditEventModel(
                project_id=project_id,
                event_type=event_type,
                actor_type="performance-governance",
                actor_id=actor_id,
                payload=payload,
            )
        )

    async def collect_evidence(
        self,
        *,
        organization_id: uuid.UUID,
        project_id: uuid.UUID | None,
        workflow_type: str,
        workflow_id: uuid.UUID,
        evidence_type: str,
        evidence_document: dict[str, Any],
        source_audit_event_id: uuid.UUID,
        observed_at: datetime,
        agent_profile_id: uuid.UUID | None = None,
        crew_id: uuid.UUID | None = None,
        assignment_id: uuid.UUID | None = None,
        task_id: uuid.UUID | None = None,
        prompt_version: str | None = None,
    ) -> PerformanceEvidenceModel:
        audit = await self.session.get(AuditEventModel, source_audit_event_id)
        if audit is None:
            raise PerformanceGovernanceError("PERF-001 SOURCE-AUDIT-EVENT-REQUIRED", 422)
        if workflow_type not in COMPLETION_EVENTS:
            raise PerformanceGovernanceError("PERF-002 UNSUPPORTED-WORKFLOW", 422)
        if audit.event_type not in COMPLETION_EVENTS[workflow_type]:
            raise PerformanceGovernanceError("PERF-003 WORKFLOW-NOT-COMPLETED", 422)
        if audit.project_id is not None and audit.project_id != project_id:
            raise PerformanceGovernanceError("PERF-007 AUDIT-PROJECT-MISMATCH", 422)
        forbidden = {"opinion", "model_confidence", "reputation"} & evidence_document.keys()
        if forbidden:
            raise PerformanceGovernanceError("PERF-004 NON-OBSERVABLE-EVIDENCE", 422)
        if len(json.dumps(evidence_document, sort_keys=True).encode()) > MAX_EVIDENCE_BYTES:
            raise PerformanceGovernanceError("PERF-008 EVIDENCE-DOCUMENT-TOO-LARGE", 413)
        document = {
            "organization_id": str(organization_id),
            "project_id": str(project_id) if project_id else None,
            "workflow_type": workflow_type,
            "workflow_id": str(workflow_id),
            "evidence_type": evidence_type,
            "agent_profile_id": str(agent_profile_id) if agent_profile_id else None,
            "crew_id": str(crew_id) if crew_id else None,
            "assignment_id": str(assignment_id) if assignment_id else None,
            "task_id": str(task_id) if task_id else None,
            "observed_at": observed_at.isoformat(),
            "facts": evidence_document,
            "source_audit_event_id": str(source_audit_event_id),
            "prompt_version": prompt_version,
        }
        evidence_hash = canonical_hash(document)
        existing = await self.session.scalar(
            select(PerformanceEvidenceModel).where(
                PerformanceEvidenceModel.evidence_hash == evidence_hash
            )
        )
        if existing is not None:
            return existing
        row = PerformanceEvidenceModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            project_id=project_id,
            workflow_type=workflow_type,
            workflow_id=workflow_id,
            evidence_type=evidence_type,
            agent_profile_id=agent_profile_id,
            crew_id=crew_id,
            assignment_id=assignment_id,
            task_id=task_id,
            prompt_version=prompt_version,
            observed_at=observed_at,
            evidence_document=document,
            evidence_hash=evidence_hash,
            source_audit_event_id=source_audit_event_id,
        )
        self.session.add(row)
        self._audit(
            "PerformanceEvidenceCollected",
            "evidence-collector",
            project_id,
            {"evidence_id": str(row.id), "evidence_hash": evidence_hash},
        )
        increment_metric(f"performance.evidence.{workflow_type}.{evidence_type}")
        await self.session.commit()
        return row

    async def derive_metric(
        self,
        *,
        organization_id: uuid.UUID,
        scope_type: str,
        scope_id: uuid.UUID,
        metric_key: str,
        numerator: int,
        denominator: int,
        evidence_ids: list[uuid.UUID],
        window_days: int,
        policy_version: str,
        actor_id: str,
        now: datetime,
    ) -> PerformanceMetricModel:
        evidence = await self._evidence_set(organization_id, evidence_ids)
        if denominator < 1 or numerator < 0 or numerator > denominator:
            raise PerformanceGovernanceError("PERF-010 INVALID-METRIC-RATIO", 422)
        evidence_set_hash = canonical_hash(
            {"evidence": sorted((str(row.id), row.evidence_hash) for row in evidence)}
        )
        existing = await self.session.scalar(
            select(PerformanceMetricModel).where(
                PerformanceMetricModel.scope_type == scope_type,
                PerformanceMetricModel.scope_id == scope_id,
                PerformanceMetricModel.metric_key == metric_key,
                PerformanceMetricModel.evidence_set_hash == evidence_set_hash,
            )
        )
        if existing is not None:
            if (
                existing.numerator != numerator
                or existing.denominator != denominator
                or existing.window_days != window_days
                or existing.policy_version != policy_version
            ):
                raise PerformanceGovernanceError("PERF-011 METRIC-REPLAY-MISMATCH")
            return existing
        row = PerformanceMetricModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            scope_type=scope_type,
            scope_id=scope_id,
            metric_key=metric_key,
            numerator=numerator,
            denominator=denominator,
            metric_value=Decimal(numerator) / Decimal(denominator),
            window_days=window_days,
            evidence_ids=[str(item.id) for item in evidence],
            evidence_set_hash=evidence_set_hash,
            policy_version=policy_version,
            calculated_at=now,
        )
        self.session.add(row)
        self._audit(
            "PerformanceMetricDerived",
            actor_id,
            None,
            {"metric_id": str(row.id), "evidence_set_hash": evidence_set_hash},
        )
        increment_metric(f"performance.metric.{scope_type}.{metric_key}")
        await self.session.commit()
        return row

    async def create_recommendation(
        self,
        *,
        organization_id: uuid.UUID,
        agent_profile_id: uuid.UUID,
        capability_key: str,
        recommended_level: str,
        evidence_ids: list[uuid.UUID],
        policy_version: str,
        assessment: dict[str, Any],
        actor_id: str,
        now: datetime,
    ) -> CapabilityRecommendationModel:
        if recommended_level not in LEVELS:
            raise PerformanceGovernanceError("PERF-020 INVALID-CAPABILITY-LEVEL", 422)
        evidence = await self._evidence_set(organization_id, evidence_ids)
        evidence_set_hash = canonical_hash(
            {"evidence": sorted((str(row.id), row.evidence_hash) for row in evidence)}
        )
        document = {
            "agent_profile_id": str(agent_profile_id),
            "capability_key": capability_key,
            "recommended_level": recommended_level,
            "assessment": assessment,
            "evidence_set_hash": evidence_set_hash,
            "policy_version": policy_version,
        }
        recommendation_hash = canonical_hash(document)
        existing = await self.session.scalar(
            select(CapabilityRecommendationModel).where(
                CapabilityRecommendationModel.recommendation_hash == recommendation_hash
            )
        )
        if existing is not None:
            return existing
        row = CapabilityRecommendationModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            agent_profile_id=agent_profile_id,
            capability_key=capability_key,
            recommended_level=recommended_level,
            status="pending_human_review",
            recommendation_document=document,
            recommendation_hash=recommendation_hash,
            evidence_ids=[str(item.id) for item in evidence],
            evidence_set_hash=evidence_set_hash,
            policy_version=policy_version,
            created_at=now,
        )
        self.session.add(row)
        self._audit(
            "CapabilityCertificationRecommended",
            actor_id,
            None,
            {"recommendation_id": str(row.id), "recommendation_hash": row.recommendation_hash},
        )
        increment_metric("performance.certification.recommended")
        await self.session.commit()
        return row

    async def decide_certification(
        self,
        recommendation: CapabilityRecommendationModel,
        *,
        recommendation_hash: str,
        decision: str,
        decided_by: str,
        board_role: str,
        rationale: str,
        validity_days: int,
        now: datetime,
    ) -> tuple[CertificationDecisionModel, CapabilityCertificationModel | None]:
        if recommendation.status != "pending_human_review":
            raise PerformanceGovernanceError("PERF-021 RECOMMENDATION-NOT-PENDING")
        if recommendation.recommendation_hash != recommendation_hash:
            raise PerformanceGovernanceError("PERF-022 RECOMMENDATION-HASH-MISMATCH")
        if decision not in {"approve", "reject"} or not rationale.strip():
            raise PerformanceGovernanceError("PERF-023 INVALID-BOARD-DECISION", 422)
        if validity_days < 1 or validity_days > 1825:
            raise PerformanceGovernanceError("PERF-024 INVALID-CERTIFICATE-VALIDITY", 422)
        decision_row = CertificationDecisionModel(
            id=uuid.uuid4(),
            recommendation_id=recommendation.id,
            decision=decision,
            decided_by=decided_by,
            board_role=board_role,
            recommendation_hash=recommendation_hash,
            rationale=rationale,
            decided_at=now,
        )
        self.session.add(decision_row)
        recommendation.status = "approved" if decision == "approve" else "rejected"
        certificate: CapabilityCertificationModel | None = None
        if decision == "approve":
            previous = await self.session.scalar(
                select(CapabilityCertificationModel)
                .where(
                    CapabilityCertificationModel.agent_profile_id
                    == recommendation.agent_profile_id,
                    CapabilityCertificationModel.capability_key == recommendation.capability_key,
                )
                .order_by(CapabilityCertificationModel.version.desc())
                .limit(1)
            )
            certificate = CapabilityCertificationModel(
                id=uuid.uuid4(),
                organization_id=recommendation.organization_id,
                agent_profile_id=recommendation.agent_profile_id,
                capability_key=recommendation.capability_key,
                level=recommendation.recommended_level,
                version=(previous.version + 1) if previous else 1,
                status="active",
                recommendation_id=recommendation.id,
                decision_id=decision_row.id,
                evidence_set_hash=recommendation.evidence_set_hash,
                granted_by=decided_by,
                granted_at=now,
                expires_at=now + timedelta(days=validity_days),
                supersedes_id=previous.id if previous else None,
            )
            self.session.add(certificate)
        self._audit(
            "CapabilityCertificationBoardDecision",
            decided_by,
            None,
            {
                "recommendation_id": str(recommendation.id),
                "decision_id": str(decision_row.id),
                "decision": decision,
                "certificate_id": str(certificate.id) if certificate else None,
            },
        )
        increment_metric(f"performance.certification.{decision}")
        await self.session.commit()
        return decision_row, certificate

    async def create_learning_proposal(
        self,
        *,
        organization_id: uuid.UUID,
        project_id: uuid.UUID | None,
        proposal_type: str,
        observation: str,
        recommendation: str,
        target_reference: str,
        evidence_ids: list[uuid.UUID],
        proposed_by: str,
        now: datetime,
    ) -> LearningProposalModel:
        evidence = await self._evidence_set(organization_id, evidence_ids)
        evidence_set_hash = canonical_hash(
            {"evidence": sorted((str(row.id), row.evidence_hash) for row in evidence)}
        )
        document = {
            "proposal_type": proposal_type,
            "observation": observation,
            "recommendation": recommendation,
            "target_reference": target_reference,
            "evidence_set_hash": evidence_set_hash,
        }
        proposal_hash = canonical_hash(document)
        existing = await self.session.scalar(
            select(LearningProposalModel).where(
                LearningProposalModel.proposal_hash == proposal_hash
            )
        )
        if existing is not None:
            return existing
        row = LearningProposalModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            project_id=project_id,
            proposal_type=proposal_type,
            observation=observation,
            recommendation=recommendation,
            target_reference=target_reference,
            status="pending_human_review",
            proposal_document=document,
            proposal_hash=proposal_hash,
            evidence_ids=[str(item.id) for item in evidence],
            evidence_set_hash=evidence_set_hash,
            proposed_by=proposed_by,
            created_at=now,
        )
        self.session.add(row)
        self._audit(
            "OrganizationalLearningProposed",
            proposed_by,
            project_id,
            {"proposal_id": str(row.id), "proposal_hash": row.proposal_hash},
        )
        await self.session.commit()
        return row

    async def review_learning_proposal(
        self,
        proposal: LearningProposalModel,
        *,
        decision: str,
        reviewer: str,
        rationale: str,
        now: datetime,
    ) -> LearningProposalModel:
        if proposal.status != "pending_human_review" or decision not in {"approve", "reject"}:
            raise PerformanceGovernanceError("PERF-030 INVALID-LEARNING-REVIEW")
        if not rationale.strip():
            raise PerformanceGovernanceError("PERF-031 LEARNING-RATIONALE-REQUIRED", 422)
        proposal.status = (
            "approved_for_separate_change_workflow" if decision == "approve" else "rejected"
        )
        proposal.reviewed_by = reviewer
        proposal.review_rationale = rationale
        proposal.reviewed_at = now
        self._audit(
            "OrganizationalLearningReviewed",
            reviewer,
            proposal.project_id,
            {
                "proposal_id": str(proposal.id),
                "decision": decision,
                "prompt_changed": False,
                "authority_changed": False,
            },
        )
        await self.session.commit()
        return proposal

    async def _evidence_set(
        self, organization_id: uuid.UUID, evidence_ids: list[uuid.UUID]
    ) -> list[PerformanceEvidenceModel]:
        if not evidence_ids:
            raise PerformanceGovernanceError("PERF-005 EVIDENCE-REQUIRED", 422)
        rows = list(
            (
                await self.session.scalars(
                    select(PerformanceEvidenceModel).where(
                        PerformanceEvidenceModel.id.in_(evidence_ids),
                        PerformanceEvidenceModel.organization_id == organization_id,
                    )
                )
            ).all()
        )
        if len(rows) != len(set(evidence_ids)):
            raise PerformanceGovernanceError("PERF-006 EVIDENCE-LINEAGE-MISMATCH", 422)
        return rows


async def build_trend(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    scope_type: str,
    scope_id: uuid.UUID,
    metric_key: str,
    window_days: int,
    now: datetime,
) -> PerformanceTrendModel:
    metrics = list(
        (
            await session.scalars(
                select(PerformanceMetricModel)
                .where(
                    PerformanceMetricModel.organization_id == organization_id,
                    PerformanceMetricModel.scope_type == scope_type,
                    PerformanceMetricModel.scope_id == scope_id,
                    PerformanceMetricModel.metric_key == metric_key,
                    PerformanceMetricModel.calculated_at >= now - timedelta(days=window_days),
                )
                .order_by(PerformanceMetricModel.calculated_at)
            )
        ).all()
    )
    if not metrics:
        raise PerformanceGovernanceError("PERF-040 METRICS-REQUIRED", 422)
    delta = metrics[-1].metric_value - metrics[0].metric_value
    direction = "improving" if delta > 0 else "declining" if delta < 0 else "stable"
    document = {
        "metric_ids": [str(row.id) for row in metrics],
        "values": [str(row.metric_value) for row in metrics],
        "direction": direction,
    }
    row = PerformanceTrendModel(
        id=uuid.uuid4(),
        organization_id=organization_id,
        scope_type=scope_type,
        scope_id=scope_id,
        metric_key=metric_key,
        window_days=window_days,
        trend_direction=direction,
        trend_document=document,
        trend_hash=canonical_hash(document),
        metric_ids=document["metric_ids"],
        calculated_at=now,
    )
    session.add(row)
    increment_metric(f"performance.trend.{metric_key}.{direction}")
    await session.commit()
    return row
