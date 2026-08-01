from dataclasses import dataclass
from uuid import UUID

from ai_enterprise.domain.evolution.organizational import (
    EngineeringRecommendation,
    LearningHypothesis,
    LearningObservation,
    derive_hypothesis,
)


@dataclass(frozen=True)
class OrganizationalLearningService:
    """Produces hypotheses and recommendations; it has no mutation or authority port."""

    def analyze(
        self, observation: LearningObservation, *, hypothesis_id: UUID
    ) -> LearningHypothesis:
        return derive_hypothesis(observation, hypothesis_id=hypothesis_id)

    def recommend(
        self,
        observation: LearningObservation,
        *,
        recommendation_id: UUID,
        title: str,
        affected_systems: tuple[str, ...],
    ) -> EngineeringRecommendation:
        return EngineeringRecommendation.create(
            id=recommendation_id,
            category="organizational_learning",
            title=title,
            expected_benefits=("improve audited outcome",),
            risks=("hypothesis may not generalize",),
            estimated_effort="requires governed analysis",
            affected_systems=tuple(sorted(set(affected_systems))),
            evidence_hashes=observation.evidence_hashes,
        )
