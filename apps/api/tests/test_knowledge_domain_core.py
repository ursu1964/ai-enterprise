from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from ai_enterprise.domain.knowledge.candidate import CandidateValidator, KnowledgeCandidate
from ai_enterprise.domain.knowledge.contradiction import (
    detect_exact_key_conflict,
    mark_disputed,
    resolve_by_supersession,
)
from ai_enterprise.domain.knowledge.enums import (
    CandidateStatus,
    ReviewDecision,
    TemporalStatus,
    TrustLevel,
)
from ai_enterprise.domain.knowledge.errors import InvalidEvidenceLocator, PromotionDenied
from ai_enterprise.domain.knowledge.evidence import EvidenceBinding
from ai_enterprise.domain.knowledge.item import KnowledgeSupersession
from ai_enterprise.domain.knowledge.policies import KnowledgePromotionPolicy, ScopePromotionPolicy
from ai_enterprise.domain.knowledge.promotion import (
    KnowledgePromotionReview,
    PromotionService,
    authorize_scope_promotion,
)
from ai_enterprise.domain.knowledge.source import KnowledgeSource, SourceRegistry

NOW = datetime(2026, 8, 1, tzinfo=UTC)


def _source(
    *, classification: str = "internal", trust: TrustLevel = TrustLevel.AUTHORITATIVE
) -> KnowledgeSource:
    return KnowledgeSource(
        uuid4(),
        "architecture-artifact",
        uuid4(),
        "a" * 64,
        uuid4(),
        uuid4(),
        classification,
        trust,
        NOW,
        NOW,
    )


def _candidate(
    source: KnowledgeSource,
    *,
    actor: UUID | None = None,
    statement: str = "Service A owns the customer records.",
) -> KnowledgeCandidate:
    return KnowledgeCandidate.create(
        id=uuid4(),
        candidate_type="fact",
        title="Customer record ownership",
        statement=statement,
        scope_type="project",
        scope_id=source.project_id,
        classification="internal",
        confidence_band="high",
        evidence_bindings=(
            EvidenceBinding(source.id, "supports", {"json_pointer": "/components/0"}),
        ),
        status=CandidateStatus.PROPOSED,
        proposed_by_actor_type="agent",
        proposed_by_actor_id=actor or uuid4(),
    )


def _validate(candidate: KnowledgeCandidate, source: KnowledgeSource, **kwargs: object):
    return CandidateValidator().validate(
        candidate,
        sources={source.id: source},
        expected_source_hashes={source.id: source.source_hash},
        eligible_source_types=frozenset({source.source_type}),
        scope_exists=lambda kind, value: kind == "project" and value == source.project_id,
        locator_resolves=lambda _source, locator: locator == {"json_pointer": "/components/0"},
        **kwargs,
    )


def _policy() -> KnowledgePromotionPolicy:
    return KnowledgePromotionPolicy(
        "knowledge-v1", ("fact",), ("lesson", "procedure"), 1, True, True, "confidential"
    )


def test_source_registration_is_idempotent_and_collision_safe() -> None:
    source = _source()
    registry = SourceRegistry()
    assert registry.register(source) is source
    assert registry.register(source) is source


@pytest.mark.parametrize(
    "locator",
    [
        {},
        {"citation": "some text"},
        {"file_path": "../../etc/passwd"},
        {"line_range": [4, 2], "file_path": "a.py"},
    ],
)
def test_evidence_locator_rejects_unstructured_or_unsafe_input(locator: dict[str, object]) -> None:
    with pytest.raises(InvalidEvidenceLocator):
        EvidenceBinding(uuid4(), "supports", locator)


def test_validation_is_deterministic_and_never_trusts_secret_bearing_agent_output() -> None:
    source = _source(classification="confidential")
    candidate = _candidate(
        source, statement="password=supersecretvalue belongs to the service account"
    )
    first = _validate(candidate, source, existing_hashes=frozenset({candidate.candidate_hash}))
    second = _validate(candidate, source, existing_hashes=frozenset({candidate.candidate_hash}))
    assert first == second
    assert first.candidate.status is CandidateStatus.VALIDATION_FAILED
    assert {finding.code for finding in first.findings} == {"KNOW-005", "KNOW-006", "KNOW-008"}


def test_candidate_passes_to_review_but_cannot_self_promote() -> None:
    source = _source()
    candidate = _validate(_candidate(source), source).candidate
    assert candidate.status is CandidateStatus.AWAITING_REVIEW
    with pytest.raises(PromotionDenied, match="independent"):
        PromotionService().promote(
            candidate,
            sources=(source,),
            policy=_policy(),
            item_id=uuid4(),
            knowledge_key="project.orders.service-ownership",
            version_number=1,
            now=NOW,
            review=KnowledgePromotionReview(
                uuid4(),
                candidate.id,
                ReviewDecision.PROMOTE,
                candidate.proposed_by_actor_id,
                candidate.candidate_hash,
                "b" * 64,
                "knowledge-v1",
                None,
                NOW,
            ),
        )


def test_independent_hash_bound_review_promotes_immutable_item() -> None:
    source = _source()
    candidate = _validate(_candidate(source), source).candidate
    review = KnowledgePromotionReview(
        uuid4(),
        candidate.id,
        ReviewDecision.PROMOTE,
        uuid4(),
        candidate.candidate_hash,
        "b" * 64,
        "knowledge-v1",
        None,
        NOW,
    )
    item = PromotionService().promote(
        candidate,
        sources=(source,),
        policy=_policy(),
        item_id=uuid4(),
        knowledge_key="project.orders.service-ownership",
        version_number=1,
        now=NOW,
        review=review,
    )
    assert item.promotion_review_id == review.id
    assert item.evidence_manifest_hash and item.knowledge_hash
    with pytest.raises(AttributeError):
        item.statement = "tampered"  # type: ignore[misc]


def test_contradictions_are_disputed_then_explicitly_resolved() -> None:
    source = _source()
    service = PromotionService()
    items = []
    for statement, version in (
        ("Service A owns customer records.", 1),
        ("Service B owns customer records.", 2),
    ):
        candidate = _validate(_candidate(source, statement=statement), source).candidate
        review = KnowledgePromotionReview(
            uuid4(),
            candidate.id,
            ReviewDecision.PROMOTE,
            uuid4(),
            candidate.candidate_hash,
            "b" * 64,
            "knowledge-v1",
            None,
            NOW,
        )
        items.append(
            service.promote(
                candidate,
                sources=(source,),
                policy=_policy(),
                item_id=uuid4(),
                knowledge_key="project.orders.service-ownership",
                version_number=version,
                now=NOW,
                review=review,
            )
        )
    contradiction = detect_exact_key_conflict(items[0], items[1], contradiction_id=uuid4())
    assert contradiction is not None
    assert mark_disputed(items[0]).temporal_status is TemporalStatus.DISPUTED
    edge = KnowledgeSupersession(items[0].id, items[1].id, "new approved ownership", NOW)
    resolved = resolve_by_supersession(
        contradiction, first=items[0], second=items[1], supersession=edge
    )
    assert resolved.first_item.temporal_status is TemporalStatus.SUPERSEDED


def test_organization_scope_promotion_requires_diverse_projects_or_expert() -> None:
    policy = ScopePromotionPolicy("scope-v1")
    assert not authorize_scope_promotion(
        project_ids=frozenset({uuid4()}), expert_approved=False, policy=policy
    )
    assert authorize_scope_promotion(
        project_ids=frozenset({uuid4(), uuid4()}), expert_approved=False, policy=policy
    )
    assert authorize_scope_promotion(
        project_ids=frozenset({uuid4()}), expert_approved=True, policy=policy
    )
