from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from .metrics import MetricKey, PerformanceMetric


class CapabilityLevel(StrEnum):
    CANDIDATE = "candidate"
    CERTIFIED = "certified"
    SENIOR = "senior"
    EXPERT = "expert"
    PRINCIPAL = "principal"
    SPECIALIST = "specialist"


@dataclass(frozen=True)
class CertificationPolicy:
    version: str
    capability: str
    recommended_level: CapabilityLevel
    minimum_evidence_count: int
    minimum_metrics: tuple[tuple[MetricKey, str], ...]
    maximum_metrics: tuple[tuple[MetricKey, str], ...]
    validity_days: int
    require_human_board: bool = True


@dataclass(frozen=True)
class CapabilityAssessment:
    agent_id: UUID
    capability: str
    evidence_count: int
    metrics: tuple[PerformanceMetric, ...]
    evidence_ids: tuple[UUID, ...]
    policy_version: str
    evidence_window_hash: str


@dataclass(frozen=True)
class CertificationRecommendation:
    id: UUID
    assessment: CapabilityAssessment
    recommended_level: CapabilityLevel
    eligible: bool
    findings: tuple[str, ...]
    created_at: datetime
    recommendation_only: bool = True


def recommend_certification(
    *,
    recommendation_id: UUID,
    assessment: CapabilityAssessment,
    policy: CertificationPolicy,
    now: datetime,
) -> CertificationRecommendation:
    findings: list[str] = []
    evidence_ids = set(assessment.evidence_ids)
    if (
        assessment.evidence_count != len(evidence_ids)
        or len(assessment.evidence_window_hash) != 64
        or any(set(metric.evidence_ids) != evidence_ids for metric in assessment.metrics)
        or any(
            metric.subject_type != "agent" or metric.subject_id != assessment.agent_id
            for metric in assessment.metrics
        )
    ):
        findings.append("CERT-EVIDENCE-MANIFEST-INVALID")
    if assessment.capability != policy.capability or assessment.policy_version != policy.version:
        findings.append("CERT-POLICY-BINDING-MISMATCH")
    if assessment.evidence_count < policy.minimum_evidence_count:
        findings.append("CERT-INSUFFICIENT-EVIDENCE")
    values = {metric.key: metric.value for metric in assessment.metrics}
    for key, threshold in policy.minimum_metrics:
        if values.get(key) is None or values[key] < Decimal(threshold):
            findings.append(f"CERT-MINIMUM-{key.value.upper()}")
    for key, threshold in policy.maximum_metrics:
        if values.get(key) is None or values[key] > Decimal(threshold):
            findings.append(f"CERT-MAXIMUM-{key.value.upper()}")
    return CertificationRecommendation(
        recommendation_id,
        assessment,
        policy.recommended_level,
        not findings,
        tuple(sorted(findings)),
        now,
    )


@dataclass(frozen=True)
class CertificationBoardDecision:
    id: UUID
    recommendation_id: UUID
    decision: str
    decided_by_human_id: UUID
    decided_at: datetime
    comments: str | None


@dataclass(frozen=True)
class CapabilityCertificate:
    id: UUID
    agent_id: UUID
    capability: str
    level: CapabilityLevel
    granted_by_human_id: UUID
    granted_at: datetime
    expires_at: datetime
    evidence_ids: tuple[UUID, ...]
    recommendation_id: UUID
    board_decision_id: UUID
    supersedes_certificate_id: UUID | None = None

    def is_active_at(self, now: datetime) -> bool:
        return self.granted_at <= now < self.expires_at


class CertificationGovernanceError(ValueError):
    pass


def issue_certificate(
    *,
    certificate_id: UUID,
    recommendation: CertificationRecommendation,
    decision: CertificationBoardDecision,
    expires_at: datetime,
    supersedes: UUID | None = None,
) -> CapabilityCertificate:
    if not recommendation.eligible or not recommendation.recommendation_only:
        raise CertificationGovernanceError("ineligible recommendation cannot be certified")
    if decision.recommendation_id != recommendation.id or decision.decision != "approve":
        raise CertificationGovernanceError("explicit bound human approval is required")
    if decision.decided_at < recommendation.created_at:
        raise CertificationGovernanceError("board decision cannot predate recommendation")
    if expires_at <= decision.decided_at:
        raise CertificationGovernanceError("certificates must expire and require recertification")
    assessment = recommendation.assessment
    return CapabilityCertificate(
        certificate_id,
        assessment.agent_id,
        assessment.capability,
        recommendation.recommended_level,
        decision.decided_by_human_id,
        decision.decided_at,
        expires_at,
        assessment.evidence_ids,
        recommendation.id,
        decision.id,
        supersedes,
    )
