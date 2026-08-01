from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from ai_enterprise.application.strategic_intelligence import StrategicIntelligenceService
from ai_enterprise.domain.cognitive import (
    CognitiveError,
    CognitiveMemoryItem,
    DigitalTwinSnapshot,
    ExecutiveQuestion,
    OntologyRelation,
    RecommendationDecision,
    RecommendationStatus,
    SemanticEdge,
    SemanticObject,
    StrategicScenario,
    StrategicSignal,
    answer_question,
    review_recommendation,
    simulate_scenario,
    synthesize,
    validate_edge,
    validate_ontology_acyclic,
)

NOW = datetime(2026, 8, 1, tzinfo=UTC)


def _object(kind: str) -> SemanticObject:
    return SemanticObject(
        uuid4(),
        kind,
        f"{kind.lower()}.one",
        f"{kind} One",
        "source",
        uuid4(),
        "a" * 64,
        "internal",
        NOW,
    )


def _signal(*, evidence=("a" * 64,)) -> StrategicSignal:
    return StrategicSignal(
        uuid4(),
        "delivery_slowdown",
        uuid4(),
        Decimal("4.8"),
        Decimal("1.6"),
        Decimal("0.4"),
        evidence,
    )


def test_semantic_objects_and_ontology_edges_are_provenance_bound() -> None:
    capability, service = _object("Capability"), _object("Service")
    relation = OntologyRelation.create(
        relation_key="implemented_by",
        source_type="Capability",
        target_type="Service",
        inverse_relation_key="implements",
        transitive=False,
        ontology_version="1.0.0",
        approved_by_human_id=uuid4(),
    )
    edge = SemanticEdge.create(
        id=uuid4(),
        source_id=capability.id,
        target_id=service.id,
        relation_key="implemented_by",
        evidence_hashes=("b" * 64,),
        valid_from=NOW,
        valid_until=None,
    )
    validate_edge(edge, source=capability, target=service, relation=relation)
    with pytest.raises(CognitiveError, match="ontology"):
        validate_edge(edge, source=service, target=capability, relation=relation)
    with pytest.raises(CognitiveError, match="provenance"):
        validate_edge(
            replace(edge, target_id=uuid4()), source=capability, target=service, relation=relation
        )


def test_reasoning_and_executive_answers_are_deterministic_explainable_and_evidenced() -> None:
    signals = (_signal(evidence=("a" * 64, "b" * 64, "c" * 64)),)
    service = StrategicIntelligenceService()
    findings = service.evaluate(signals)
    assert findings == service.evaluate(signals)
    assert findings[0].severity == "high" and findings[0].confidence_band == "high"
    question = ExecutiveQuestion(uuid4(), "Why is delivery slowing?", ("Project",), "confidential")
    answer = service.answer(question, findings)
    assert answer.explanation_steps and set(answer.evidence_hashes) == set(
        signals[0].evidence_hashes
    )
    assert answer.answer_hash == answer_question(question, findings).answer_hash
    with pytest.raises(CognitiveError, match="require evidence"):
        answer_question(question, ())


def test_scenario_simulation_is_pure_hash_bound_and_deterministic() -> None:
    systems = tuple(sorted((uuid4(), uuid4()), key=str))
    scenario = StrategicScenario.create(
        id=uuid4(),
        title="Double AI workforce",
        assumptions=("demand remains stable",),
        assumption_evidence_hashes=("a" * 64,),
        affected_system_ids=systems,
        risk_factors=(Decimal("0.2"), Decimal("0.4")),
        benefit_factors=(Decimal("0.7"), Decimal("0.9")),
        estimated_cost=Decimal("0.1"),
        estimated_duration_days=90,
        evidence_hashes=("a" * 64,),
    )
    first = simulate_scenario(scenario, model_version="strategy-v1")
    assert first == simulate_scenario(scenario, model_version="strategy-v1")
    assert first.risk_score == Decimal("0.3000")
    assert first.net_value == Decimal("0.4000")
    with pytest.raises(CognitiveError, match="tampered"):
        simulate_scenario(
            replace(scenario, estimated_cost=Decimal("0")), model_version="strategy-v1"
        )
    with pytest.raises(FrozenInstanceError):
        scenario.title = "Mutate production"  # type: ignore[misc]


def test_digital_twin_is_an_immutable_evidence_snapshot_not_an_execution_model() -> None:
    snapshot = DigitalTwinSnapshot.capture(
        id=uuid4(),
        version=1,
        captured_at=NOW,
        source_hashes=("a" * 64, "b" * 64),
        expected_source_hashes=frozenset({"a" * 64, "b" * 64}),
        semantic_object_ids=(uuid4(),),
        active_policy_hashes=("c" * 64,),
    )
    same = DigitalTwinSnapshot.capture(
        id=snapshot.id,
        version=1,
        captured_at=NOW,
        source_hashes=("a" * 64, "b" * 64),
        expected_source_hashes=frozenset({"a" * 64, "b" * 64}),
        semantic_object_ids=snapshot.semantic_object_ids,
        active_policy_hashes=("c" * 64,),
    )
    assert snapshot.snapshot_hash == same.snapshot_hash
    assert not hasattr(snapshot, "execute")


def test_cognitive_memory_requires_human_promotion_and_synthesis_preserves_evidence() -> None:
    memories = tuple(
        CognitiveMemoryItem(
            uuid4(),
            "initiative_outcome",
            f"Transformation {index}",
            "measured",
            (uuid4(),),
            (character * 64,),
            uuid4(),
            uuid4(),
            NOW,
            None,
        )
        for index, character in enumerate(("a", "b"))
    )
    expected = frozenset(memory.id for memory in memories)
    synthesis = synthesize(
        synthesis_id=uuid4(),
        claim="Coupling is increasing",
        memories=memories,
        expected_memory_ids=expected,
    )
    assert set(synthesis.evidence_hashes) == {"a" * 64, "b" * 64}
    assert len(synthesis.explanation) == 2
    with pytest.raises(CognitiveError, match="multiple"):
        synthesize(
            synthesis_id=uuid4(),
            claim="unsupported",
            memories=(memories[0],),
            expected_memory_ids=expected,
        )


def test_recommendations_are_managed_advice_and_require_bound_human_review() -> None:
    finding = StrategicIntelligenceService().evaluate((_signal(),))
    recommendation = StrategicIntelligenceService().recommend(
        recommendation_id=uuid4(),
        generated_by_actor_id=uuid4(),
        statement="Investigate delivery bottleneck",
        findings=finding,
        affected_system_ids=(uuid4(),),
    )
    assert recommendation.status is RecommendationStatus.GENERATED
    assert recommendation.self_executing is False
    with pytest.raises(CognitiveError, match="bound"):
        review_recommendation(
            recommendation,
            RecommendationDecision(
                uuid4(), recommendation.recommendation_hash, "review", uuid4(), NOW
            ),
        )
    reviewed = review_recommendation(
        recommendation,
        RecommendationDecision(
            recommendation.id, recommendation.recommendation_hash, "review", uuid4(), NOW
        ),
    )
    assert reviewed.status is RecommendationStatus.REVIEWED
    assert reviewed.version == 2


def test_no_evidence_nonfinite_values_and_raw_model_authority_fail_closed() -> None:
    with pytest.raises(CognitiveError, match="evidence"):
        _signal(evidence=())
    with pytest.raises(CognitiveError, match="finite"):
        replace(_signal(), value=Decimal("NaN"))
    recommendation = StrategicIntelligenceService().recommend(
        recommendation_id=uuid4(),
        generated_by_actor_id=uuid4(),
        statement="Advisory only",
        findings=StrategicIntelligenceService().evaluate((_signal(),)),
        affected_system_ids=(),
    )
    assert not hasattr(recommendation, "approve")
    assert not hasattr(StrategicIntelligenceService(), "execute")


def test_executive_answer_cannot_cross_classification_boundary() -> None:
    finding = StrategicIntelligenceService().evaluate(
        (replace(_signal(), classification="restricted"),)
    )
    question = ExecutiveQuestion(uuid4(), "Explain restricted risk", ("Risk",), "internal")
    with pytest.raises(CognitiveError, match="clearance"):
        answer_question(question, finding)


def test_recommendation_lifecycle_requires_a_new_bound_human_decision_each_step() -> None:
    finding = StrategicIntelligenceService().evaluate((_signal(),))
    value = StrategicIntelligenceService().recommend(
        recommendation_id=uuid4(),
        generated_by_actor_id=uuid4(),
        statement="Investigate",
        findings=finding,
        affected_system_ids=(),
    )
    for decision_name, status in (
        ("review", RecommendationStatus.REVIEWED),
        ("accept", RecommendationStatus.ACCEPTED),
        ("plan", RecommendationStatus.PLANNED),
        ("implement", RecommendationStatus.IMPLEMENTED),
        ("measure", RecommendationStatus.MEASURED),
    ):
        value = review_recommendation(
            value,
            RecommendationDecision(
                value.id, value.recommendation_hash, decision_name, uuid4(), NOW
            ),
        )
        assert value.status is status
    with pytest.raises(CognitiveError, match="invalid"):
        review_recommendation(
            value,
            RecommendationDecision(value.id, value.recommendation_hash, "implement", uuid4(), NOW),
        )


def test_hierarchical_ontology_cycles_and_relation_poisoning_are_rejected() -> None:
    first, second = _object("Organization"), _object("Organization")
    edges = (
        SemanticEdge.create(
            id=uuid4(),
            source_id=first.id,
            target_id=second.id,
            relation_key="parent_of",
            evidence_hashes=("a" * 64,),
            valid_from=NOW,
            valid_until=None,
        ),
        SemanticEdge.create(
            id=uuid4(),
            source_id=second.id,
            target_id=first.id,
            relation_key="parent_of",
            evidence_hashes=("b" * 64,),
            valid_from=NOW,
            valid_until=None,
        ),
    )
    with pytest.raises(CognitiveError, match="cycle"):
        validate_ontology_acyclic(edges, hierarchical_relations=frozenset({"parent_of"}))
    relation = OntologyRelation.create(
        relation_key="parent_of",
        source_type="Organization",
        target_type="Organization",
        inverse_relation_key="child_of",
        transitive=True,
        ontology_version="1.0.0",
        approved_by_human_id=uuid4(),
    )
    with pytest.raises(CognitiveError, match="ontology"):
        validate_edge(
            edges[0],
            source=first,
            target=second,
            relation=replace(relation, source_type="Agent"),
        )


def test_scenario_assumptions_and_factors_cannot_be_cherry_picked_or_unbounded() -> None:
    values = {
        "id": uuid4(),
        "title": "Migration",
        "assumptions": ("demand stable",),
        "assumption_evidence_hashes": ("a" * 64,),
        "affected_system_ids": (),
        "risk_factors": (Decimal("0.2"),),
        "benefit_factors": (Decimal("0.5"),),
        "estimated_cost": Decimal("0.1"),
        "estimated_duration_days": 30,
        "evidence_hashes": ("a" * 64,),
    }
    with pytest.raises(CognitiveError, match="assumptions"):
        StrategicScenario.create(**{**values, "assumptions": ("a", "b")})
    with pytest.raises(CognitiveError, match="bounded"):
        simulate_scenario(
            StrategicScenario.create(**{**values, "risk_factors": (Decimal("2"),)}),
            model_version="v1",
        )


def test_digital_twin_incompleteness_and_staleness_are_visible() -> None:
    with pytest.raises(CognitiveError, match="incomplete"):
        DigitalTwinSnapshot.capture(
            id=uuid4(),
            version=1,
            captured_at=NOW,
            source_hashes=("a" * 64,),
            expected_source_hashes=frozenset({"a" * 64, "b" * 64}),
            semantic_object_ids=(),
            active_policy_hashes=("c" * 64,),
        )
    snapshot = DigitalTwinSnapshot.capture(
        id=uuid4(),
        version=1,
        captured_at=NOW,
        source_hashes=("a" * 64,),
        expected_source_hashes=frozenset({"a" * 64}),
        semantic_object_ids=(),
        active_policy_hashes=("c" * 64,),
    )
    assert not snapshot.current_at(NOW.replace(day=2), maximum_age_seconds=3600)


def test_memory_self_promotion_synthesis_omission_and_reviewer_reuse_fail_closed() -> None:
    actor = uuid4()
    with pytest.raises(CognitiveError, match="independent"):
        CognitiveMemoryItem(
            uuid4(),
            "outcome",
            "Claim",
            "measured",
            (),
            ("a" * 64,),
            actor,
            actor,
            NOW,
            None,
        )
    memories = tuple(
        CognitiveMemoryItem(
            uuid4(),
            "outcome",
            f"Claim {index}",
            "measured",
            (),
            (character * 64,),
            uuid4(),
            uuid4(),
            NOW,
            None,
        )
        for index, character in enumerate(("a", "b"))
    )
    with pytest.raises(CognitiveError, match="multiple"):
        synthesize(
            synthesis_id=uuid4(),
            claim="Cherry-picked",
            memories=(memories[0],),
            expected_memory_ids=frozenset(memory.id for memory in memories),
        )
    generator = uuid4()
    recommendation = StrategicIntelligenceService().recommend(
        recommendation_id=uuid4(),
        generated_by_actor_id=generator,
        statement="Advice",
        findings=StrategicIntelligenceService().evaluate((_signal(),)),
        affected_system_ids=(),
    )
    with pytest.raises(CognitiveError, match="independent"):
        review_recommendation(
            recommendation,
            RecommendationDecision(
                recommendation.id, recommendation.recommendation_hash, "review", generator, NOW
            ),
        )
    reviewer = uuid4()
    reviewed = review_recommendation(
        recommendation,
        RecommendationDecision(
            recommendation.id, recommendation.recommendation_hash, "review", reviewer, NOW
        ),
    )
    with pytest.raises(CognitiveError, match="independent"):
        review_recommendation(
            reviewed,
            RecommendationDecision(
                reviewed.id, reviewed.recommendation_hash, "accept", reviewer, NOW
            ),
        )
