from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from uuid import UUID

from .evidence import EvidenceInvariantError, WorkflowEvidence, validate_evidence


class MetricKey(StrEnum):
    ACCEPTANCE_RATE = "acceptance_rate"
    FIRST_PASS_SUCCESS = "first_pass_success"
    REVIEW_PRECISION = "review_precision"
    FALSE_NEGATIVE_RATE = "false_negative_rate"
    TEST_SUCCESS_RATE = "test_success_rate"
    INTEGRATION_RELIABILITY = "integration_reliability"
    ROLLBACK_RATE = "rollback_rate"
    REQUIREMENT_COVERAGE = "requirement_coverage"
    SCOPE_COMPLIANCE = "scope_compliance"
    ARCHITECTURE_COMPLIANCE = "architecture_compliance"


@dataclass(frozen=True)
class PerformanceMetric:
    subject_type: str
    subject_id: UUID
    key: MetricKey
    numerator: int
    denominator: int
    value: Decimal
    evidence_ids: tuple[UUID, ...]
    policy_version: str


class MetricsEngine:
    def derive(
        self,
        *,
        subject_type: str,
        subject_id: UUID,
        evidence: tuple[WorkflowEvidence, ...],
        policy_version: str = "performance-metrics-v1",
    ) -> tuple[PerformanceMetric, ...]:
        if not evidence:
            return ()
        identities = [record.id for record in evidence]
        workflows = [record.workflow_id for record in evidence]
        if len(identities) != len(set(identities)) or len(workflows) != len(set(workflows)):
            raise EvidenceInvariantError("duplicate or replayed evidence is forbidden")
        for record in evidence:
            validate_evidence(record)
            actual_subject = getattr(record, f"{subject_type}_id", None)
            if subject_type in {"agent", "crew", "assignment"} and actual_subject != subject_id:
                raise EvidenceInvariantError("evidence does not belong to the metric subject")
        ids = tuple(sorted((record.id for record in evidence), key=str))
        total = len(evidence)
        pairs = {
            MetricKey.ACCEPTANCE_RATE: (sum(record.accepted for record in evidence), total),
            MetricKey.FIRST_PASS_SUCCESS: (
                sum(record.accepted and record.revision_count == 0 for record in evidence),
                total,
            ),
            MetricKey.REVIEW_PRECISION: (
                sum(record.correct_review_findings for record in evidence),
                sum(record.review_findings for record in evidence),
            ),
            MetricKey.FALSE_NEGATIVE_RATE: (
                sum(record.false_negative_findings for record in evidence),
                sum(record.review_findings + record.false_negative_findings for record in evidence),
            ),
            MetricKey.TEST_SUCCESS_RATE: (
                sum(record.tests_passed for record in evidence),
                sum(record.tests_passed + record.tests_failed for record in evidence),
            ),
            MetricKey.INTEGRATION_RELIABILITY: (
                sum(record.integration_success for record in evidence),
                total,
            ),
            MetricKey.ROLLBACK_RATE: (sum(record.rollback for record in evidence), total),
            MetricKey.REQUIREMENT_COVERAGE: (
                sum(record.requirements_verified for record in evidence),
                sum(record.requirements_total for record in evidence),
            ),
            MetricKey.SCOPE_COMPLIANCE: (
                sum(record.scope_violations == 0 for record in evidence),
                total,
            ),
            MetricKey.ARCHITECTURE_COMPLIANCE: (
                sum(record.architecture_violations == 0 for record in evidence),
                total,
            ),
        }
        return tuple(
            PerformanceMetric(
                subject_type,
                subject_id,
                key,
                numerator,
                denominator,
                self._ratio(numerator, denominator),
                ids,
                policy_version,
            )
            for key, (numerator, denominator) in sorted(
                pairs.items(), key=lambda pair: pair[0].value
            )
        )

    @staticmethod
    def _ratio(numerator: int, denominator: int) -> Decimal:
        if denominator == 0:
            return Decimal("0")
        return (Decimal(numerator) / Decimal(denominator)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )


@dataclass(frozen=True)
class AssignmentQuality:
    assignment_id: UUID
    band: str
    metrics: tuple[PerformanceMetric, ...]
    evidence_ids: tuple[UUID, ...]


def assess_assignment(
    assignment_id: UUID, evidence: tuple[WorkflowEvidence, ...]
) -> AssignmentQuality:
    metrics = MetricsEngine().derive(
        subject_type="assignment", subject_id=assignment_id, evidence=evidence
    )
    values = {metric.key: metric.value for metric in metrics}
    score = (
        sum(
            (
                values.get(MetricKey.ACCEPTANCE_RATE, Decimal(0)),
                values.get(MetricKey.FIRST_PASS_SUCCESS, Decimal(0)),
                values.get(MetricKey.INTEGRATION_RELIABILITY, Decimal(0)),
                values.get(MetricKey.SCOPE_COMPLIANCE, Decimal(0)),
            )
        )
        / 4
    )
    band = (
        "excellent"
        if score >= Decimal("0.90")
        else "good"
        if score >= Decimal("0.75")
        else "needs_review"
        if score >= Decimal("0.50")
        else "poor"
    )
    return AssignmentQuality(
        assignment_id, band, metrics, tuple(sorted((record.id for record in evidence), key=str))
    )
