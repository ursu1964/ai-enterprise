from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from ai_enterprise.application.evolution.learning_service import OrganizationalLearningService
from ai_enterprise.domain.evolution.organizational import (
    EngineeringPattern,
    EvolutionApproval,
    EvolutionError,
    EvolutionProposal,
    ExperimentPlan,
    Improvement,
    ImprovementStatus,
    LearningObservation,
    SimulationInput,
    approve_evolution,
    evaluate_experiment,
    simulate,
    transition_improvement,
)

NOW = datetime(2026, 8, 1, tzinfo=UTC)
EVIDENCE = ("a" * 64,)


def _improvement() -> Improvement:
    return Improvement.propose(
        id=uuid4(),
        category="workflow",
        origin="performance-trend",
        title="Reduce authentication review churn",
        expected_benefit="Fewer review iterations",
        risk="May miss unusual authentication cases",
        evidence_hashes=EVIDENCE,
        dependency_ids=(),
        proposed_by=uuid4(),
    )


def test_improvement_registry_is_hash_bound_versioned_and_sequential() -> None:
    improvement = _improvement()
    assert improvement.verify() and improvement.version == 1
    analyzed = transition_improvement(
        improvement, ImprovementStatus.ANALYZED, stage_evidence_hashes=("b" * 64,)
    )
    assert analyzed.version == 2 and analyzed.verify()
    with pytest.raises(EvolutionError, match="transition"):
        transition_improvement(
            improvement, ImprovementStatus.APPROVED, stage_evidence_hashes=("b" * 64,)
        )
    with pytest.raises(EvolutionError, match="tampered"):
        transition_improvement(
            replace(improvement, title="silently changed"),
            ImprovementStatus.ANALYZED,
            stage_evidence_hashes=("b" * 64,),
        )


def test_learning_produces_hypothesis_and_non_executing_recommendation_only() -> None:
    workflow = uuid4()
    observation = LearningObservation(
        uuid4(),
        "authentication-packages",
        "review_iterations",
        Decimal("4.8"),
        Decimal("1.6"),
        42,
        EVIDENCE,
        (workflow,),
        frozenset({workflow}),
    )
    service = OrganizationalLearningService()
    hypothesis = service.analyze(observation, hypothesis_id=uuid4())
    recommendation = service.recommend(
        observation,
        recommendation_id=uuid4(),
        title="Investigate authentication specs",
        affected_systems=("auth", "auth"),
    )
    assert hypothesis.recommendation_only
    assert "investigate" in hypothesis.statement
    assert recommendation.self_executing is False
    assert recommendation.affected_systems == ("auth",)
    with pytest.raises(FrozenInstanceError):
        recommendation.self_executing = True  # type: ignore[misc]


def test_pattern_and_antipattern_require_recurring_audited_evidence() -> None:
    with pytest.raises(EvolutionError, match="distinct workflows"):
        EngineeringPattern(
            uuid4(),
            "anti_pattern",
            "Detect oversized services",
            "service planning",
            "reduce review churn",
            ("may flag legitimate aggregation",),
            "v1",
            None,
            (uuid4(),),
            EVIDENCE,
            "candidate",
        )
    workflows = (uuid4(), uuid4())
    pattern = EngineeringPattern(
        uuid4(),
        "pattern",
        "Rollback plans",
        "database migrations",
        "safer releases",
        ("additional effort",),
        "v1",
        "migration-generator-v3",
        workflows,
        ("a" * 64, "b" * 64),
        "validated",
        uuid4(),
    )
    assert pattern.status == "validated"


def test_simulation_is_deterministic_bounded_and_hashes_all_inputs() -> None:
    value = SimulationInput(
        uuid4(),
        "a" * 64,
        "b" * 64,
        6,
        2,
        3,
        Decimal("0.10"),
        Decimal("1000"),
        Decimal("0.15"),
        "simulation-v1",
    )
    assert simulate(value) == simulate(value)
    assert simulate(value).predicted_risk == Decimal("0.2200")
    assert simulate(value).migration_complexity == "medium"
    assert (
        simulate(replace(value, policy_version="simulation-v2")).simulation_hash
        != simulate(value).simulation_hash
    )


def test_experiment_requires_human_approval_sufficient_design_and_guardrails() -> None:
    participants = (uuid4(), uuid4())
    unapproved = ExperimentPlan(
        uuid4(),
        1,
        "A validator reduces failures",
        "failure_rate",
        Decimal("0.05"),
        Decimal("0.01"),
        14,
        participants,
        "a" * 64,
        None,
    )
    with pytest.raises(EvolutionError, match="human approval"):
        evaluate_experiment(
            unapproved,
            control_value=Decimal("0.10"),
            treatment_value=Decimal("0.20"),
            guardrail_regression=Decimal("0"),
            participant_evidence=(
                (participants[0], "a" * 64),
                (participants[1], "b" * 64),
            ),
        )
    plan = replace(unapproved, approved_by_human_id=uuid4())
    stopped = evaluate_experiment(
        plan,
        control_value=Decimal("0.10"),
        treatment_value=Decimal("0.20"),
        guardrail_regression=Decimal("0.02"),
        participant_evidence=(
            (participants[0], "a" * 64),
            (participants[1], "b" * 64),
        ),
    )
    assert stopped.decision == "stop_guardrail"
    adopted = evaluate_experiment(
        plan,
        control_value=Decimal("0.10"),
        treatment_value=Decimal("0.20"),
        guardrail_regression=Decimal("0"),
        participant_evidence=(
            (participants[0], "a" * 64),
            (participants[1], "b" * 64),
        ),
    )
    assert adopted.decision == "recommend_adoption"


@pytest.mark.parametrize(
    "target", ["generator", "policy", "agent", "prompt", "crew", "certification"]
)
def test_every_enterprise_or_workforce_change_is_proposal_only_until_bound_human_approval(
    target: str,
) -> None:
    proposer = uuid4()
    proposal = EvolutionProposal(
        uuid4(),
        target,
        f"{target}.default",
        "1.0.0",
        "1.1.0",
        "c" * 64,
        EVIDENCE,
        ("b" * 64,),
        proposer,
    )
    assert proposal.status == "proposed"
    with pytest.raises(EvolutionError, match="bound"):
        approve_evolution(
            proposal,
            EvolutionApproval(uuid4(), "approve", uuid4(), proposal.candidate_hash, NOW),
        )
    approved = approve_evolution(
        proposal,
        EvolutionApproval(proposal.id, "approve", uuid4(), proposal.candidate_hash, NOW),
    )
    assert approved.status == "approved"


def test_no_evidence_no_learning_or_evolution() -> None:
    with pytest.raises(EvolutionError, match="evidence"):
        LearningObservation(
            uuid4(), "subject", "metric", Decimal("1"), Decimal("0"), 1, (), (), frozenset()
        )
    with pytest.raises(EvolutionError, match="evidence"):
        EvolutionProposal(
            uuid4(),
            "policy",
            "policy.default",
            "1",
            "2",
            "a" * 64,
            (),
            ("b" * 64,),
            uuid4(),
        )


def test_evidence_replay_and_learning_cherry_picking_are_rejected() -> None:
    workflow_a, workflow_b = uuid4(), uuid4()
    with pytest.raises(EvolutionError, match="duplicate evidence"):
        LearningObservation(
            uuid4(),
            "subject",
            "metric",
            Decimal("1"),
            Decimal("0"),
            2,
            ("a" * 64, "a" * 64),
            (workflow_a, workflow_b),
            frozenset({workflow_a, workflow_b}),
        )
    with pytest.raises(EvolutionError, match="complete workflow"):
        LearningObservation(
            uuid4(),
            "subject",
            "metric",
            Decimal("1"),
            Decimal("0"),
            1,
            EVIDENCE,
            (workflow_a,),
            frozenset({workflow_a, workflow_b}),
        )


def test_pattern_cannot_self_declare_validation_or_reuse_one_evidence() -> None:
    workflows = (uuid4(), uuid4())
    with pytest.raises(EvolutionError, match="distinct evidence"):
        EngineeringPattern(
            uuid4(),
            "pattern",
            "Purpose",
            "Scope",
            "Benefit",
            (),
            "v1",
            None,
            workflows,
            EVIDENCE,
            "candidate",
        )
    with pytest.raises(EvolutionError, match="human review"):
        EngineeringPattern(
            uuid4(),
            "anti_pattern",
            "Purpose",
            "Scope",
            "Benefit",
            (),
            "v1",
            None,
            workflows,
            ("a" * 64, "b" * 64),
            "validated",
        )


def test_simulation_rejects_hash_substitution_and_nonfinite_or_invalid_rates() -> None:
    base = dict(
        id=uuid4(),
        improvement_hash="a" * 64,
        architecture_hash="b" * 64,
        dependency_count=1,
        affected_team_count=1,
        affected_repository_count=1,
        historical_failure_rate=Decimal("0.1"),
        expected_cost_delta=Decimal("1"),
        expected_performance_delta=Decimal("0.1"),
        policy_version="v1",
    )
    with pytest.raises(EvolutionError, match="evidence"):
        SimulationInput(**{**base, "architecture_hash": "not-bound"})
    with pytest.raises(EvolutionError, match="invalid"):
        SimulationInput(**{**base, "historical_failure_rate": Decimal("1.1")})
    with pytest.raises(EvolutionError, match="invalid"):
        SimulationInput(**{**base, "expected_cost_delta": Decimal("NaN")})


def test_experiment_requires_complete_unique_participant_evidence_and_finite_metrics() -> None:
    participants = (uuid4(), uuid4())
    plan = ExperimentPlan(
        uuid4(),
        1,
        "hypothesis",
        "metric",
        Decimal("0.1"),
        Decimal("0.01"),
        7,
        participants,
        "a" * 64,
        uuid4(),
    )
    with pytest.raises(EvolutionError, match="every approved participant"):
        evaluate_experiment(
            plan,
            control_value=Decimal("1"),
            treatment_value=Decimal("2"),
            guardrail_regression=Decimal("0"),
            participant_evidence=((participants[0], "b" * 64),),
        )
    with pytest.raises(EvolutionError, match="finite"):
        evaluate_experiment(
            plan,
            control_value=Decimal("NaN"),
            treatment_value=Decimal("2"),
            guardrail_regression=Decimal("0"),
            participant_evidence=((participants[0], "b" * 64), (participants[1], "c" * 64)),
        )


def test_proposal_type_semver_and_independent_approval_are_fail_closed() -> None:
    proposer = uuid4()
    with pytest.raises(EvolutionError, match="versioned proposal"):
        EvolutionProposal(
            uuid4(),
            "policy",
            "agent.wrong-type",
            "1.0.0",
            "1.1.0",
            "a" * 64,
            ("b" * 64,),
            ("c" * 64,),
            proposer,
        )
    with pytest.raises(EvolutionError, match="versioned proposal"):
        EvolutionProposal(
            uuid4(),
            "policy",
            "policy.default",
            "2.0.0",
            "1.9.0",
            "a" * 64,
            ("b" * 64,),
            ("c" * 64,),
            proposer,
        )
    proposal = EvolutionProposal(
        uuid4(),
        "prompt",
        "prompt.default",
        "1.0.0",
        "1.1.0",
        "a" * 64,
        ("b" * 64,),
        ("c" * 64,),
        proposer,
    )
    with pytest.raises(EvolutionError, match="independent"):
        approve_evolution(
            proposal,
            EvolutionApproval(proposal.id, "approve", proposer, proposal.candidate_hash, NOW),
        )
