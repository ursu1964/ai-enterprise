from dataclasses import dataclass
from uuid import UUID

from ai_enterprise.domain.performance.certification import CapabilityAssessment
from ai_enterprise.domain.performance.evidence import CompleteEvidenceWindow, WorkflowEvidence
from ai_enterprise.domain.performance.metrics import MetricsEngine, PerformanceMetric


@dataclass(frozen=True)
class PerformanceEvaluationService:
    metrics: MetricsEngine = MetricsEngine()

    def assess_agent(
        self,
        *,
        agent_id: UUID,
        capability: str,
        evidence: tuple[WorkflowEvidence, ...],
        expected_workflow_ids: frozenset[UUID],
        policy_version: str,
    ) -> CapabilityAssessment:
        bound = tuple(record for record in evidence if record.agent_id == agent_id)
        window = CompleteEvidenceWindow.build(bound, expected_workflow_ids=expected_workflow_ids)
        derived = self.metrics.derive(
            subject_type="agent", subject_id=agent_id, evidence=bound, policy_version=policy_version
        )
        evidence_ids = tuple(sorted((record.id for record in bound), key=str))
        return CapabilityAssessment(
            agent_id,
            capability,
            len(bound),
            derived,
            evidence_ids,
            policy_version,
            window.window_hash,
        )

    def assess_crew(
        self,
        *,
        crew_id: UUID,
        evidence: tuple[WorkflowEvidence, ...],
        policy_version: str = "performance-metrics-v1",
    ) -> tuple[PerformanceMetric, ...]:
        bound = tuple(record for record in evidence if record.crew_id == crew_id)
        return self.metrics.derive(
            subject_type="crew", subject_id=crew_id, evidence=bound, policy_version=policy_version
        )
