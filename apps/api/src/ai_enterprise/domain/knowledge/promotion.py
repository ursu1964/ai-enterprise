from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ._hashing import stable_hash
from .candidate import CLASSIFICATION_RANK, KnowledgeCandidate
from .enums import CandidateStatus, ReviewDecision, TemporalStatus, TrustLevel
from .errors import PromotionDenied
from .item import KnowledgeItem
from .policies import KnowledgePromotionPolicy, ScopePromotionPolicy
from .source import KnowledgeSource


@dataclass(frozen=True)
class KnowledgePromotionReview:
    id: UUID
    candidate_id: UUID
    decision: ReviewDecision
    reviewer_id: UUID
    candidate_hash: str
    evidence_hash: str
    policy_version: str
    comments: str | None
    created_at: datetime


class PromotionService:
    _MACHINE_FACT_TYPES = frozenset({"fact"})

    def promote(
        self,
        candidate: KnowledgeCandidate,
        *,
        sources: tuple[KnowledgeSource, ...],
        policy: KnowledgePromotionPolicy,
        item_id: UUID,
        knowledge_key: str,
        version_number: int,
        now: datetime,
        review: KnowledgePromotionReview | None = None,
        policy_auto_promotion: bool = False,
    ) -> KnowledgeItem:
        if candidate.status is not CandidateStatus.AWAITING_REVIEW:
            raise PromotionDenied("candidate has not passed deterministic validation")
        distinct = {binding.knowledge_source_id for binding in candidate.evidence_bindings}
        if len(distinct) < policy.minimum_evidence_sources:
            raise PromotionDenied("insufficient distinct evidence sources")
        if policy.require_authoritative_source and not any(
            source.trust_level is TrustLevel.AUTHORITATIVE for source in sources
        ):
            raise PromotionDenied("authoritative evidence is required")
        if CLASSIFICATION_RANK.get(candidate.classification, 99) > CLASSIFICATION_RANK.get(
            policy.maximum_classification, -1
        ):
            raise PromotionDenied("candidate classification exceeds policy")
        if policy_auto_promotion:
            if (
                candidate.candidate_type not in self._MACHINE_FACT_TYPES
                or candidate.candidate_type not in policy.auto_promotable_types
            ):
                raise PromotionDenied("only allowlisted machine-verifiable facts may auto-promote")
            if candidate.proposed_by_actor_type == "agent" and not sources:
                raise PromotionDenied("agent output cannot self-certify")
        else:
            self._validate_review(candidate, policy, review)
        evidence_hash = stable_hash(
            sorted(binding.binding_hash for binding in candidate.evidence_bindings)
        )
        values = {
            "knowledge_key": knowledge_key,
            "version_number": version_number,
            "item_type": candidate.candidate_type,
            "title": candidate.title,
            "statement": candidate.statement,
            "scope_type": candidate.scope_type,
            "scope_id": candidate.scope_id,
            "classification": candidate.classification,
            "trust_level": TrustLevel.VERIFIED,
            "temporal_status": TemporalStatus.CURRENT,
            "valid_from": now,
            "valid_until": None,
            "evidence_manifest_hash": evidence_hash,
            "promoted_from_candidate_id": candidate.id,
            "promotion_review_id": review.id if review else None,
        }
        return KnowledgeItem(
            id=item_id,
            knowledge_key=knowledge_key,
            version_number=version_number,
            item_type=candidate.candidate_type,
            title=candidate.title,
            statement=candidate.statement,
            scope_type=candidate.scope_type,
            scope_id=candidate.scope_id,
            classification=candidate.classification,
            trust_level=TrustLevel.VERIFIED,
            temporal_status=TemporalStatus.CURRENT,
            valid_from=now,
            valid_until=None,
            evidence_manifest_hash=evidence_hash,
            knowledge_hash=KnowledgeItem.calculate_hash(**values),
            promoted_from_candidate_id=candidate.id,
            promotion_review_id=review.id if review else None,
        )

    @staticmethod
    def _validate_review(
        candidate: KnowledgeCandidate,
        policy: KnowledgePromotionPolicy,
        review: KnowledgePromotionReview | None,
    ) -> None:
        if review is None or review.decision is not ReviewDecision.PROMOTE:
            raise PromotionDenied("an approving promotion review is required")
        if (
            review.candidate_id != candidate.id
            or review.candidate_hash != candidate.candidate_hash
            or review.policy_version != policy.version
        ):
            raise PromotionDenied("review is not bound to this candidate and policy")
        if (
            policy.require_distinct_reviewer
            and review.reviewer_id == candidate.proposed_by_actor_id
        ):
            raise PromotionDenied("independent reviewer is required")


def authorize_scope_promotion(
    *, project_ids: frozenset[UUID], expert_approved: bool, policy: ScopePromotionPolicy
) -> bool:
    return len(project_ids) >= policy.minimum_distinct_projects or (
        expert_approved and policy.expert_approval_satisfies_diversity
    )
