from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgePromotionPolicy:
    version: str
    auto_promotable_types: tuple[str, ...]
    human_review_required_types: tuple[str, ...]
    minimum_evidence_sources: int
    require_authoritative_source: bool
    require_distinct_reviewer: bool
    maximum_classification: str


@dataclass(frozen=True)
class ScopePromotionPolicy:
    version: str
    minimum_distinct_projects: int = 2
    expert_approval_satisfies_diversity: bool = True
