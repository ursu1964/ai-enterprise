from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from ai_enterprise.domain.cognitive import (
    ExecutiveAnswer,
    ExecutiveQuestion,
    StrategicFinding,
    StrategicRecommendation,
    StrategicSignal,
    answer_question,
    reason,
)


@dataclass(frozen=True)
class StrategicIntelligenceService:
    """Evidence-to-advice only. This service exposes no command or authority port."""

    rule_version: str = "strategic-reasoning-v1"

    def evaluate(self, signals: tuple[StrategicSignal, ...]) -> tuple[StrategicFinding, ...]:
        return reason(signals, rule_version=self.rule_version)

    def answer(
        self, question: ExecutiveQuestion, findings: tuple[StrategicFinding, ...]
    ) -> ExecutiveAnswer:
        return answer_question(question, findings)

    def recommend(
        self,
        *,
        recommendation_id: UUID,
        generated_by_actor_id: UUID,
        statement: str,
        findings: tuple[StrategicFinding, ...],
        affected_system_ids: tuple[UUID, ...],
    ) -> StrategicRecommendation:
        if not findings:
            raise ValueError("strategic recommendations require findings")
        evidence = tuple(
            sorted({digest for finding in findings for digest in finding.evidence_hashes})
        )
        return StrategicRecommendation.generate(
            id=recommendation_id,
            recommendation_type="strategic",
            statement=statement,
            expected_benefit="requires governed validation",
            confidence_band="high" if len(evidence) >= 3 else "moderate",
            risks=("model assumptions may not hold",),
            affected_system_ids=tuple(sorted(set(affected_system_ids), key=str)),
            required_investment=Decimal("0"),
            evidence_hashes=evidence,
            generated_by_actor_id=generated_by_actor_id,
        )
