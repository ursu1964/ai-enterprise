from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from ai_enterprise.api.dependencies import Actor
from ai_enterprise.api.routes.evolution import _require_governor, router
from ai_enterprise.application.evolution.service import EvolutionGovernanceService
from ai_enterprise.domain.evolution.entities import (
    ConstitutionalAmendment,
    ConstitutionalApproval,
    ControlState,
    ControlTest,
    DebtItem,
    Experiment,
    FitnessResult,
    ImprovementItem,
    PolicyException,
    PolicyVersion,
    PromotionEvidence,
    Rollout,
    SchemaVersion,
    ShadowCommand,
    VersionedCandidate,
    WorkflowMigrationPlan,
)
from ai_enterprise.domain.evolution.enums import (
    Compatibility,
    ControlEffectiveness,
    LifecycleStatus,
    PolicyLevel,
    RolloutStatus,
)
from ai_enterprise.domain.evolution.exceptions import (
    ConstitutionalQuorumMissing,
    EvolutionAuthorityViolation,
    EvolutionCompatibilityViolation,
    EvolutionPrerequisiteMissing,
    EvolutionSafetyViolation,
)
from ai_enterprise.domain.evolution.policies import PolicyLifecyclePolicy
from ai_enterprise.infrastructure.evolution.models import (
    AgentCrewEvolutionRecordModel,
    ArchitectureGovernanceRecordModel,
    ConstitutionalGovernanceRecordModel,
    ControlValidationRecordModel,
    ExperimentRecordModel,
    ImprovementDebtRecordModel,
    PolicyEvolutionRecordModel,
    RolloutRecordModel,
    SchemaEvolutionRecordModel,
    SimulationRecordModel,
    WorkflowEvolutionRecordModel,
)

HASH = "a" * 64


def test_prerequisites_fail_closed() -> None:
    with pytest.raises(EvolutionPrerequisiteMissing, match="p9_criticality"):
        EvolutionGovernanceService().require_platform_prerequisites(
            {"p4_workflow_versioning", "p4_authority", "p9_audit_continuity"}
        )


def test_architecture_requires_transition_and_passing_fitness() -> None:
    service = EvolutionGovernanceService()
    assert service.assess_architecture(
        transition_plan_hash=HASH,
        results=(FitnessResult("NO_AGENT_GIT", True, True, HASH),),
    )
    assert not service.assess_architecture(
        transition_plan_hash=HASH,
        results=(FitnessResult("NO_AGENT_GIT", False, True, HASH),),
    )


def test_policy_precedence_and_activation_tests() -> None:
    policy = PolicyLifecyclePolicy()
    assert policy.may_override(PolicyLevel.CONSTITUTIONAL, PolicyLevel.PROJECT)
    assert not policy.may_override(PolicyLevel.PROJECT, PolicyLevel.SECURITY)
    version = PolicyVersion(
        uuid4(),
        uuid4(),
        2,
        PolicyLevel.SECURITY,
        HASH,
        LifecycleStatus.APPROVED,
        (FitnessResult("separation", False, True, HASH),),
        None,
    )
    with pytest.raises(EvolutionSafetyViolation):
        EvolutionGovernanceService().assess_policy_activation(version)


def test_workflow_migration_is_state_bound() -> None:
    plan = WorkflowMigrationPlan(
        uuid4(),
        uuid4(),
        1,
        uuid4(),
        2,
        ("waiting",),
        ("integrating",),
        {"waiting": "awaiting_approval"},
        (HASH,),
        True,
    )
    assert (
        EvolutionGovernanceService().assess_workflow_migration(plan, "waiting")
        == "awaiting_approval"
    )
    with pytest.raises(EvolutionCompatibilityViolation):
        EvolutionGovernanceService().assess_workflow_migration(plan, "integrating")


def test_breaking_schema_requires_migration_plan() -> None:
    schema = SchemaVersion(uuid4(), uuid4(), "2", Compatibility.BREAKING, HASH, HASH, None)
    with pytest.raises(EvolutionCompatibilityViolation):
        EvolutionGovernanceService().assess_schema_activation(schema)


def test_agent_or_crew_cannot_self_promote_and_requires_all_stages() -> None:
    evidence = PromotionEvidence(True, True, True, True, (HASH,))
    with pytest.raises(EvolutionAuthorityViolation):
        EvolutionGovernanceService().assess_agent_promotion(
            proposer_id="agent-owner", agent_owner_id="agent-owner", evidence=evidence
        )
    incomplete = PromotionEvidence(True, True, False, True, (HASH,))
    with pytest.raises(EvolutionSafetyViolation):
        EvolutionGovernanceService().assess_agent_promotion(
            proposer_id="governor", agent_owner_id="agent-owner", evidence=incomplete
        )


def test_experiment_assignment_is_deterministic_and_guardrails_stop() -> None:
    experiment = Experiment(
        uuid4(), uuid4(), 3, "salt", HASH, "b" * 64, ("security",), LifecycleStatus.ACTIVE
    )
    subject = uuid4()
    service = EvolutionGovernanceService()
    assert service.assign_experiment(experiment, subject) == service.assign_experiment(
        experiment, subject
    )
    with pytest.raises(EvolutionSafetyViolation):
        service.assess_experiment_guardrails(experiment, {"security"})


@pytest.mark.parametrize(
    "command",
    [
        ShadowCommand("git_push", HASH, False, None),
        ShadowCommand("analysis", HASH, True, None),
        ShadowCommand("analysis", HASH, False, "production-git"),
    ],
)
def test_shadow_operation_cannot_have_side_effects_or_credentials(command) -> None:
    with pytest.raises(EvolutionSafetyViolation):
        EvolutionGovernanceService().assess_shadow_command(command)


def test_rollout_pauses_when_health_gate_fails() -> None:
    rollout = Rollout(
        uuid4(),
        uuid4(),
        ("shadow", "pilot", "production"),
        0,
        RolloutStatus.ACTIVE,
        ("quality", "security"),
        HASH,
    )
    result = EvolutionGovernanceService().assess_rollout(rollout, {"quality"})
    assert result.status is RolloutStatus.PAUSED
    assert result.current_stage == 0


def test_failed_control_is_never_effective() -> None:
    control_id = uuid4()
    state = ControlState(control_id, ControlEffectiveness.EFFECTIVE, None)
    result = EvolutionGovernanceService().record_control_test(
        state, ControlTest(control_id, False, (HASH,), datetime.now(UTC))
    )
    assert result.effectiveness is ControlEffectiveness.INEFFECTIVE


def test_expired_or_uncontrolled_exception_fails_closed() -> None:
    now = datetime.now(UTC)
    expired = PolicyException(
        uuid4(),
        uuid4(),
        "owner",
        "temporary",
        HASH,
        (uuid4(),),
        HASH,
        now - timedelta(seconds=1),
    )
    with pytest.raises(EvolutionAuthorityViolation):
        EvolutionGovernanceService().assess_exception(expired, now)


def test_constitutional_quorum_roles_signatures_and_cooling_are_required() -> None:
    now = datetime.now(UTC)
    amendment = ConstitutionalAmendment(
        uuid4(),
        uuid4(),
        uuid4(),
        "proposer",
        HASH,
        ("security", "legal"),
        2,
        now - timedelta(seconds=1),
        (ConstitutionalApproval("a", "security", "sig:a", now),),
    )
    with pytest.raises(ConstitutionalQuorumMissing):
        EvolutionGovernanceService().assess_constitutional_activation(amendment, now)


def test_constitutional_proposer_cannot_join_approval_quorum() -> None:
    now = datetime.now(UTC)
    amendment = ConstitutionalAmendment(
        uuid4(),
        uuid4(),
        uuid4(),
        "proposer",
        HASH,
        ("security", "legal"),
        2,
        now - timedelta(seconds=1),
        (
            ConstitutionalApproval("proposer", "security", "sig:p", now),
            ConstitutionalApproval("legal", "legal", "sig:l", now),
        ),
    )
    with pytest.raises(EvolutionAuthorityViolation):
        EvolutionGovernanceService().assess_constitutional_activation(amendment, now)


def test_improvement_debt_and_versioned_candidates_are_evidence_bearing() -> None:
    candidate = VersionedCandidate(
        uuid4(), uuid4(), 1, HASH, LifecycleStatus.DRAFT, "governor", datetime.now(UTC), {}
    )
    improvement = ImprovementItem(uuid4(), "incident", uuid4(), "owner", 9.5, (HASH,))
    debt = DebtItem(uuid4(), "architecture", "high", "owner", None, uuid4())
    assert candidate.version == 1 and improvement.evidence_hashes and debt.origin_change_id


def test_all_workstreams_have_bounded_persistence_models() -> None:
    tables = {
        model.__tablename__
        for model in (
            ArchitectureGovernanceRecordModel,
            PolicyEvolutionRecordModel,
            WorkflowEvolutionRecordModel,
            AgentCrewEvolutionRecordModel,
            SchemaEvolutionRecordModel,
            ExperimentRecordModel,
            SimulationRecordModel,
            RolloutRecordModel,
            ControlValidationRecordModel,
            ImprovementDebtRecordModel,
            ConstitutionalGovernanceRecordModel,
        )
    }
    assert len(tables) == 11


def test_api_is_assessment_only_and_has_no_activation_endpoint() -> None:
    paths = {route.path for route in router.routes if isinstance(route, APIRoute)}
    assert "/evolution-assessments/constitutional-amendments" in paths
    assert all("/activate" not in path and "/rollout" not in path for path in paths)


def test_evolution_assessment_requires_human_global_capability() -> None:
    with pytest.raises(HTTPException, match="Evolution assessment capability"):
        _require_governor(Actor("governor", "human", "evolution_governor"))

    with pytest.raises(HTTPException, match="Evolution assessment capability"):
        _require_governor(
            Actor(
                "governor",
                "human",
                "evolution_governor",
                frozenset({"evolution.assess"}),
                scopes=frozenset({"project:wrong"}),
            )
        )

    with pytest.raises(HTTPException, match="Human evolution governor"):
        _require_governor(
            Actor(
                "governor-service",
                "service",
                "evolution_governor",
                frozenset({"evolution.assess"}),
                scopes=frozenset({"global"}),
            )
        )

    _require_governor(
        Actor(
            "governor",
            "human",
            "evolution_governor",
            frozenset({"evolution.assess"}),
            scopes=frozenset({"global"}),
        )
    )
