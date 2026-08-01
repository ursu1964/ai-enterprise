import hashlib
from dataclasses import replace
from datetime import datetime
from uuid import UUID

from .entities import (
    ConstitutionalAmendment,
    ControlState,
    ControlTest,
    Experiment,
    ExperimentAssignment,
    PolicyException,
    PolicyVersion,
    PromotionEvidence,
    Rollout,
    SchemaVersion,
    ShadowCommand,
    WorkflowMigrationPlan,
)
from .enums import (
    Compatibility,
    ControlEffectiveness,
    LifecycleStatus,
    PolicyLevel,
    RolloutStatus,
)
from .exceptions import (
    ConstitutionalQuorumMissing,
    EvolutionAuthorityViolation,
    EvolutionCompatibilityViolation,
    EvolutionPrerequisiteMissing,
    EvolutionSafetyViolation,
)

_PRECEDENCE = {level: index for index, level in enumerate(PolicyLevel)}


class EvolutionPrerequisitePolicy:
    REQUIRED = frozenset(
        {"p4_workflow_versioning", "p4_authority", "p9_criticality", "p9_audit_continuity"}
    )

    def require(self, available: set[str]) -> None:
        missing = self.REQUIRED - available
        if missing:
            raise EvolutionPrerequisiteMissing(
                f"Missing evolution prerequisites: {sorted(missing)}"
            )


class PolicyLifecyclePolicy:
    def may_override(self, candidate: PolicyLevel, existing: PolicyLevel) -> bool:
        return _PRECEDENCE[candidate] >= _PRECEDENCE[existing]

    def require_activation(self, version: PolicyVersion) -> None:
        if version.status is not LifecycleStatus.APPROVED:
            raise EvolutionPrerequisiteMissing("Policy version is not approved")
        if not version.test_results or any(
            item.blocking and not item.passed for item in version.test_results
        ):
            raise EvolutionSafetyViolation("Required policy tests are not passing")


class WorkflowEvolutionPolicy:
    def require_migration(self, plan: WorkflowMigrationPlan, current_state: str) -> str:
        if current_state in plan.prohibited_states or current_state not in plan.eligible_states:
            raise EvolutionCompatibilityViolation("Workflow state is not migration-eligible")
        if not plan.validation_hashes:
            raise EvolutionPrerequisiteMissing("Workflow migration validation is missing")
        target = plan.state_mapping.get(current_state)
        if not target:
            raise EvolutionCompatibilityViolation("Workflow state mapping is missing")
        return target


class SchemaEvolutionPolicy:
    def require_activation(self, version: SchemaVersion) -> None:
        if (
            version.compatibility
            in {
                Compatibility.BREAKING,
                Compatibility.SEMANTICALLY_BREAKING,
            }
            and version.migration_plan_id is None
        ):
            raise EvolutionCompatibilityViolation(
                "Breaking schema requires an approved migration plan"
            )


class AgentPromotionPolicy:
    def require_promotion(
        self, *, proposer_id: str, agent_owner_id: str, evidence: PromotionEvidence
    ) -> None:
        if proposer_id == agent_owner_id:
            raise EvolutionAuthorityViolation("Agent version cannot promote itself")
        if not all(
            (
                evidence.offline_passed,
                evidence.replay_passed,
                evidence.shadow_passed,
                evidence.pilot_passed,
                bool(evidence.evidence_hashes),
            )
        ):
            raise EvolutionSafetyViolation("Agent promotion evidence is incomplete")


class ExperimentPolicy:
    def assign(self, experiment: Experiment, subject_id: UUID) -> ExperimentAssignment:
        material = f"{experiment.id}:{experiment.version}:{experiment.assignment_salt}:{subject_id}"
        digest = hashlib.sha256(material.encode()).hexdigest()
        return ExperimentAssignment(
            experiment_id=experiment.id,
            subject_id=subject_id,
            arm="control" if int(digest[:8], 16) % 2 == 0 else "treatment",
            assignment_hash=digest,
        )

    def require_continue(self, experiment: Experiment, violated: set[str]) -> None:
        if set(experiment.guardrail_codes) & violated:
            raise EvolutionSafetyViolation("Experiment guardrail requires immediate pause")


class ShadowSafetyPolicy:
    FORBIDDEN = frozenset(
        {"git_push", "integration", "recovery", "external_command", "approval", "notification"}
    )

    def require_safe(self, command: ShadowCommand) -> None:
        if command.side_effecting or command.command_type in self.FORBIDDEN:
            raise EvolutionSafetyViolation("Shadow operation cannot produce side effects")
        if command.credential_scope:
            raise EvolutionSafetyViolation("Shadow operation cannot receive credentials")


class RolloutPolicy:
    def advance(self, rollout: Rollout, passing_gates: set[str]) -> Rollout:
        if rollout.status not in {RolloutStatus.DRAFT, RolloutStatus.ACTIVE}:
            raise EvolutionSafetyViolation("Rollout cannot advance from its current state")
        if not set(rollout.required_gate_codes).issubset(passing_gates):
            return replace(rollout, status=RolloutStatus.PAUSED)
        if rollout.current_stage + 1 >= len(rollout.stages):
            return replace(rollout, status=RolloutStatus.COMPLETED)
        return replace(
            rollout, current_stage=rollout.current_stage + 1, status=RolloutStatus.ACTIVE
        )


class ControlValidationPolicy:
    def apply(self, state: ControlState, test: ControlTest) -> ControlState:
        if not test.evidence_hashes:
            effectiveness = ControlEffectiveness.UNKNOWN
        else:
            effectiveness = (
                ControlEffectiveness.EFFECTIVE if test.passed else ControlEffectiveness.INEFFECTIVE
            )
        return replace(state, effectiveness=effectiveness, last_test=test)


class ExceptionPolicy:
    def require_active(self, value: PolicyException, now: datetime) -> None:
        if value.expires_at <= now:
            raise EvolutionAuthorityViolation("Policy exception has expired")
        if not value.compensating_control_ids or not value.removal_plan_hash:
            raise EvolutionSafetyViolation("Exception controls and removal plan are required")


class ConstitutionalPolicy:
    def require_activation(self, amendment: ConstitutionalAmendment, now: datetime) -> None:
        distinct = {item.actor_id for item in amendment.approvals}
        roles = {item.role for item in amendment.approvals}
        if amendment.proposed_by in distinct:
            raise EvolutionAuthorityViolation("Proposer cannot approve constitutional amendment")
        if len(distinct) < amendment.minimum_approval_count:
            raise ConstitutionalQuorumMissing("Constitutional approval quorum is missing")
        if not set(amendment.required_roles).issubset(roles):
            raise ConstitutionalQuorumMissing("Required constitutional roles are missing")
        if any(not item.signature_reference for item in amendment.approvals):
            raise EvolutionSafetyViolation("Signed approvals are required")
        if now < amendment.cooling_off_until:
            raise EvolutionSafetyViolation("Constitutional cooling-off period is active")
