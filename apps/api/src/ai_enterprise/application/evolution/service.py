from datetime import datetime
from uuid import UUID

from ai_enterprise.domain.evolution.entities import (
    ConstitutionalAmendment,
    ControlState,
    ControlTest,
    Experiment,
    ExperimentAssignment,
    FitnessResult,
    PolicyException,
    PolicyVersion,
    PromotionEvidence,
    Rollout,
    SchemaVersion,
    ShadowCommand,
    WorkflowMigrationPlan,
)
from ai_enterprise.domain.evolution.policies import (
    AgentPromotionPolicy,
    ConstitutionalPolicy,
    ControlValidationPolicy,
    EvolutionPrerequisitePolicy,
    ExceptionPolicy,
    ExperimentPolicy,
    PolicyLifecyclePolicy,
    RolloutPolicy,
    SchemaEvolutionPolicy,
    ShadowSafetyPolicy,
    WorkflowEvolutionPolicy,
)


class EvolutionGovernanceService:
    """Pure governance assessments; never mutates active platform components."""

    def require_platform_prerequisites(self, available: set[str]) -> None:
        EvolutionPrerequisitePolicy().require(available)

    def assess_architecture(
        self, *, transition_plan_hash: str, results: tuple[FitnessResult, ...]
    ) -> bool:
        if not transition_plan_hash or not results:
            return False
        return not any(item.blocking and not item.passed for item in results)

    def assess_policy_activation(self, version: PolicyVersion) -> bool:
        PolicyLifecyclePolicy().require_activation(version)
        return True

    def assess_workflow_migration(self, plan: WorkflowMigrationPlan, current_state: str) -> str:
        return WorkflowEvolutionPolicy().require_migration(plan, current_state)

    def assess_schema_activation(self, version: SchemaVersion) -> bool:
        SchemaEvolutionPolicy().require_activation(version)
        return True

    def assess_agent_promotion(
        self, *, proposer_id: str, agent_owner_id: str, evidence: PromotionEvidence
    ) -> bool:
        AgentPromotionPolicy().require_promotion(
            proposer_id=proposer_id,
            agent_owner_id=agent_owner_id,
            evidence=evidence,
        )
        return True

    def assign_experiment(self, experiment: Experiment, subject_id: UUID) -> ExperimentAssignment:
        return ExperimentPolicy().assign(experiment, subject_id)

    def assess_experiment_guardrails(self, experiment: Experiment, violations: set[str]) -> bool:
        ExperimentPolicy().require_continue(experiment, violations)
        return True

    def assess_shadow_command(self, command: ShadowCommand) -> bool:
        ShadowSafetyPolicy().require_safe(command)
        return True

    def assess_rollout(self, rollout: Rollout, passing_gates: set[str]) -> Rollout:
        return RolloutPolicy().advance(rollout, passing_gates)

    def record_control_test(self, state: ControlState, test: ControlTest) -> ControlState:
        return ControlValidationPolicy().apply(state, test)

    def assess_exception(self, value: PolicyException, now: datetime) -> bool:
        ExceptionPolicy().require_active(value, now)
        return True

    def assess_constitutional_activation(
        self, amendment: ConstitutionalAmendment, now: datetime
    ) -> bool:
        ConstitutionalPolicy().require_activation(amendment, now)
        return True
