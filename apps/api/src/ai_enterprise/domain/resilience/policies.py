from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from .entities import (
    BackupManifest,
    CapabilityDecision,
    ContinuityActivation,
    DisasterRecoveryRun,
    GovernanceAvailabilityBudget,
    GovernanceAvailabilityBudgetUsage,
    GovernanceAvailabilityContract,
    GovernanceCachedAuthority,
    GovernanceContinuityDecision,
    GovernanceContinuityLease,
    GovernanceDeadline,
    GovernanceDependencyAvailability,
    GovernanceLatencyBudget,
    GovernancePerformanceEvidence,
    GovernanceStalenessEnvelope,
    ReadinessResult,
    RecoveryObjective,
    RestoreVerification,
)
from .enums import (
    BackupStatus,
    Capability,
    ContinuityMode,
    CriticalityTier,
    DisasterRecoveryStatus,
    GovernanceContinuityEffect,
    GovernanceDeadlineClass,
    GovernanceDependencyCriticality,
    GovernanceDependencyState,
    RestoreStatus,
)


class ResiliencePolicyError(ValueError):
    pass


class RecoveryObjectivePolicy:
    def validate(self, objective: RecoveryObjective) -> None:
        values = (
            objective.rto_seconds,
            objective.mtpd_seconds,
            objective.policy_version,
        )
        if any(value <= 0 for value in values):
            raise ResiliencePolicyError("Positive objectives and policy version are required")
        if objective.rpo_seconds < 0 or objective.work_recovery_time_seconds < 0:
            raise ResiliencePolicyError("RPO and work recovery time cannot be negative")
        if objective.rpo_seconds > objective.mtpd_seconds:
            raise ResiliencePolicyError("RPO cannot exceed MTPD")
        if objective.rto_seconds + objective.work_recovery_time_seconds > objective.mtpd_seconds:
            raise ResiliencePolicyError("RTO plus work recovery time cannot exceed MTPD")
        if objective.primary_owner == objective.deputy_owner:
            raise ResiliencePolicyError("Primary and deputy must be distinct")
        if objective.tier in {CriticalityTier.TIER_0, CriticalityTier.TIER_1} and not (
            objective.approved_by and objective.approved_at
        ):
            raise ResiliencePolicyError("Tier 0 and Tier 1 objectives require approval")


class CapabilityGate:
    """Prohibitions dominate; uncertainty and expired activations fail closed."""

    _READ_ONLY = frozenset({Capability.READ_GOVERNANCE})

    def decide(
        self,
        capability: Capability,
        activations: tuple[ContinuityActivation, ...] | None,
        *,
        now: datetime,
    ) -> CapabilityDecision:
        if activations is None:
            return CapabilityDecision(capability, False, "POLICY_STATE_UNAVAILABLE", (), ())
        active = tuple(item for item in activations if item.closed_at is None)
        if any(
            item.expires_at <= item.activated_at
            or (item.expires_at - item.activated_at).total_seconds()
            > item.policy.maximum_duration_seconds
            or item.policy.allowed & item.policy.prohibited
            for item in active
        ):
            return CapabilityDecision(
                capability,
                False,
                "INVALID_CONTINUITY_POLICY_STATE",
                tuple(item.policy.policy_version for item in active),
                tuple(item.id for item in active),
            )
        if any(item.expires_at <= now for item in active):
            return CapabilityDecision(
                capability,
                capability in self._READ_ONLY,
                "ACTIVATION_EXPIRED_REVIEW_REQUIRED",
                tuple(item.policy.policy_version for item in active),
                tuple(item.id for item in active),
            )
        prohibited = {item for activation in active for item in activation.policy.prohibited}
        if capability in prohibited:
            allowed = False
            reason = "EXPLICITLY_PROHIBITED"
        elif not active:
            allowed = True
            reason = "NORMAL_OPERATION"
        else:
            allowed_set = {item for activation in active for item in activation.policy.allowed}
            allowed = capability in allowed_set
            reason = "ALLOWED_BY_CONTINUITY_POLICY" if allowed else "NOT_ALLOWED_IN_MODE"
        return CapabilityDecision(
            capability,
            allowed,
            reason,
            tuple(item.policy.policy_version for item in active),
            tuple(item.id for item in active),
        )


class GovernanceAvailabilityPolicy:
    _NORMAL_STATES = {
        GovernanceDependencyState.AVAILABLE,
        GovernanceDependencyState.DEGRADED,
    }
    _FAILING_STATES = {
        GovernanceDependencyState.STALE,
        GovernanceDependencyState.PARTITIONED,
        GovernanceDependencyState.RATE_LIMITED,
        GovernanceDependencyState.OVERLOADED,
        GovernanceDependencyState.UNAVAILABLE,
        GovernanceDependencyState.UNKNOWN,
    }

    def decide(
        self,
        contract: GovernanceAvailabilityContract,
        dependencies: tuple[GovernanceDependencyAvailability, ...],
        *,
        lease: GovernanceContinuityLease | None,
        budget: GovernanceAvailabilityBudget | None,
        usage: GovernanceAvailabilityBudgetUsage | None,
        now: datetime,
    ) -> GovernanceContinuityDecision:
        self._validate_contract(contract)
        states = {item.dependency_id: item.state for item in dependencies}
        failing = tuple(item for item in dependencies if item.state in self._FAILING_STATES)
        hard_failure = next(
            (
                item
                for item in failing
                if item.criticality
                in {
                    GovernanceDependencyCriticality.HARD_REQUIRED,
                    GovernanceDependencyCriticality.AUTHORITY_REQUIRED,
                    GovernanceDependencyCriticality.SAFETY_REQUIRED,
                }
            ),
            None,
        )
        if not failing:
            return GovernanceContinuityDecision(
                contract.capability,
                GovernanceContinuityEffect.CONTINUE_NORMAL,
                contract.dependency_behaviors.get("normal", ContinuityMode.NORMAL),
                "DEPENDENCIES_AVAILABLE",
                contract.policy_version,
                states,
            )
        if hard_failure:
            mode = contract.dependency_behaviors.get(hard_failure.dependency_id)
            if mode is None:
                return GovernanceContinuityDecision(
                    contract.capability,
                    GovernanceContinuityEffect.BLOCK,
                    contract.dependency_behaviors.get("default", ContinuityMode.FAIL_CLOSED),
                    "HARD_REQUIRED_DEPENDENCY_UNAVAILABLE",
                    contract.policy_version,
                    states,
                )
        mode = next(
            (
                contract.dependency_behaviors[item.dependency_id]
                for item in failing
                if item.dependency_id in contract.dependency_behaviors
            ),
            contract.dependency_behaviors.get("default", ContinuityMode.FAIL_CLOSED),
        )
        if mode == ContinuityMode.FAIL_CLOSED:
            effect = GovernanceContinuityEffect.BLOCK
            reason = "CONTINUITY_MODE_FAIL_CLOSED"
        elif mode == ContinuityMode.QUEUE_ONLY and contract.queue_allowed:
            effect = GovernanceContinuityEffect.QUEUE
            reason = "QUEUED_BY_CONTINUITY_CONTRACT"
        elif mode == ContinuityMode.EMERGENCY_OPERATION and (
            contract.capability in contract.emergency_capabilities
        ):
            effect = GovernanceContinuityEffect.EMERGENCY_MODE
            reason = "EMERGENCY_OPERATION_AUTHORIZED"
        else:
            if not self._lease_valid(contract.capability, mode, lease, now=now):
                return GovernanceContinuityDecision(
                    contract.capability,
                    GovernanceContinuityEffect.BLOCK,
                    ContinuityMode.FAIL_CLOSED,
                    "CONTINUITY_LEASE_INVALID",
                    contract.policy_version,
                    states,
                )
            if not self._budget_available(budget, usage, now=now):
                return GovernanceContinuityDecision(
                    contract.capability,
                    GovernanceContinuityEffect.BLOCK,
                    ContinuityMode.FAIL_CLOSED,
                    "CONTINUITY_BUDGET_EXHAUSTED",
                    contract.policy_version,
                    states,
                    lease.id if lease else None,
                )
            effect = GovernanceContinuityEffect.CONTINUE_DEGRADED
            reason = "CONTINUE_DEGRADED_WITH_BOUNDED_AUTHORITY"
        return GovernanceContinuityDecision(
            contract.capability,
            effect,
            mode,
            reason,
            contract.policy_version,
            states,
            lease.id if lease else None,
        )

    def cached_authority_valid(
        self,
        authority: GovernanceCachedAuthority,
        envelope: GovernanceStalenessEnvelope,
        *,
        dimension: str,
        now: datetime,
        revocation_state_available: bool,
    ) -> bool:
        if authority.capability != envelope.capability or authority.valid_until <= now:
            return False
        if authority.revocation_sensitive and not revocation_state_available:
            return False
        maximum_age = envelope.maximum_age_by_dimension_seconds.get(dimension)
        if maximum_age is None:
            return False
        return (now - authority.captured_at).total_seconds() <= maximum_age

    def _validate_contract(self, contract: GovernanceAvailabilityContract) -> None:
        if contract.policy_version <= 0:
            raise ResiliencePolicyError("Availability contract requires a policy version")
        if contract.fail_open_allowed and not contract.required_evidence:
            raise ResiliencePolicyError("Fail-open continuity requires evidence")
        if (
            contract.capability in contract.emergency_capabilities
            and not contract.required_evidence
        ):
            raise ResiliencePolicyError("Emergency operation requires evidence")

    def _lease_valid(
        self,
        capability: Capability,
        mode: object,
        lease: GovernanceContinuityLease | None,
        *,
        now: datetime,
    ) -> bool:
        return bool(
            lease
            and lease.capability == capability
            and lease.mode == mode
            and lease.issued_at <= now < lease.expires_at
            and lease.authority
            and lease.self_renewal_prohibited
        )

    def _budget_available(
        self,
        budget: GovernanceAvailabilityBudget | None,
        usage: GovernanceAvailabilityBudgetUsage | None,
        *,
        now: datetime,
    ) -> bool:
        if budget is None or usage is None:
            return False
        if budget.maximum_duration_seconds <= 0:
            return False
        if (now - usage.started_at).total_seconds() > budget.maximum_duration_seconds:
            return False
        limits = (
            (budget.maximum_executions, usage.executions),
            (budget.maximum_external_effects, usage.external_effects),
            (budget.maximum_ai_tool_calls, usage.ai_tool_calls),
        )
        return all(limit is None or value < limit for limit, value in limits)


class GovernancePerformancePolicy:
    def validate_budget(self, budget: GovernanceLatencyBudget) -> None:
        if min(
            budget.end_to_end_milliseconds,
            budget.evaluation_milliseconds,
            budget.authorization_milliseconds,
            budget.evidence_milliseconds,
            budget.revocation_milliseconds,
        ) < 0:
            raise ResiliencePolicyError("Latency budgets cannot be negative")
        allocated = (
            budget.evaluation_milliseconds
            + budget.authorization_milliseconds
            + budget.evidence_milliseconds
            + budget.revocation_milliseconds
        )
        if allocated > budget.end_to_end_milliseconds:
            raise ResiliencePolicyError("Latency allocation exceeds end-to-end budget")

    def evaluate_deadline(
        self,
        deadline: GovernanceDeadline,
        *,
        started_at: datetime,
        completed_at: datetime,
        budget_milliseconds: int,
    ) -> GovernancePerformanceEvidence:
        elapsed = int((completed_at - started_at).total_seconds() * 1000)
        met = completed_at <= deadline.due_at and elapsed <= budget_milliseconds
        if met:
            reason = "DEADLINE_MET"
        elif deadline.deadline_class == GovernanceDeadlineClass.HARD:
            reason = "HARD_DEADLINE_MISSED"
        elif deadline.deadline_class == GovernanceDeadlineClass.FIRM:
            reason = "FIRM_DEADLINE_MISSED"
        else:
            reason = "DEADLINE_OBSERVED_LATE"
        return GovernancePerformanceEvidence(
            deadline.capability,
            started_at,
            completed_at,
            elapsed,
            budget_milliseconds,
            met,
            reason,
        )


class BackupRecoveryPolicy:
    REQUIRED_CHECKS = frozenset(
        {"schema", "references", "artifacts", "audit_chain", "git_reachability", "jobs"}
    )

    def mark_recoverable(
        self, backup: BackupManifest, verification: RestoreVerification
    ) -> BackupManifest:
        if verification.backup_id != backup.id or verification.status != RestoreStatus.PASSED:
            raise ResiliencePolicyError("A successful matching restore is required")
        if not (
            verification.isolated_environment
            and verification.production_credentials_disabled
            and verification.external_dispatch_blocked
        ):
            raise ResiliencePolicyError("Restore isolation controls are incomplete")
        if not self.REQUIRED_CHECKS.issubset(
            name for name, passed in verification.checks.items() if passed
        ):
            raise ResiliencePolicyError("Restore integrity checks are incomplete")
        return replace(backup, status=BackupStatus.RECOVERABLE)


class DisasterRecoveryStateMachine:
    _NEXT = {
        DisasterRecoveryStatus.DECLARED: DisasterRecoveryStatus.WRITES_FROZEN,
        DisasterRecoveryStatus.WRITES_FROZEN: DisasterRecoveryStatus.AUTHORITY_VERIFIED,
        DisasterRecoveryStatus.AUTHORITY_VERIFIED: DisasterRecoveryStatus.RECOVERY_POINT_SELECTED,
        DisasterRecoveryStatus.RECOVERY_POINT_SELECTED: DisasterRecoveryStatus.RESTORING,
        DisasterRecoveryStatus.RESTORING: DisasterRecoveryStatus.VERIFYING,
        DisasterRecoveryStatus.VERIFYING: DisasterRecoveryStatus.DEGRADED,
        DisasterRecoveryStatus.DEGRADED: DisasterRecoveryStatus.RECONCILING,
        DisasterRecoveryStatus.RECONCILING: DisasterRecoveryStatus.EXIT_REVIEW,
        DisasterRecoveryStatus.EXIT_REVIEW: DisasterRecoveryStatus.COMPLETED,
    }

    def transition(
        self, run: DisasterRecoveryRun, target: DisasterRecoveryStatus
    ) -> DisasterRecoveryRun:
        if target == DisasterRecoveryStatus.FAILED:
            return replace(run, status=target)
        if self._NEXT.get(run.status) != target:
            raise ResiliencePolicyError(f"Invalid DR transition {run.status} -> {target}")
        if target == DisasterRecoveryStatus.RECOVERY_POINT_SELECTED and not (
            run.commander and run.selected_recovery_point
        ):
            raise ResiliencePolicyError("Authority and recovery point are required")
        if target == DisasterRecoveryStatus.COMPLETED and (
            run.unresolved_workflows
            or run.unresolved_external_effects
            or run.missing_artifacts
            or not run.exit_reviewed_by
        ):
            raise ResiliencePolicyError(
                "DR reconciliation and independent exit review are required"
            )
        return replace(run, status=target)


class ReadinessPolicy:
    def evaluate(
        self,
        *,
        objective: RecoveryObjective | None,
        backup: BackupManifest | None,
        plan_version: int | None,
        mandatory_dependencies_ready: bool,
    ) -> ReadinessResult:
        failures: list[str] = []
        if objective is None:
            failures.append("RECOVERY_OBJECTIVE_MISSING")
        elif objective.tier in {CriticalityTier.TIER_0, CriticalityTier.TIER_1} and not (
            objective.approved_by and objective.approved_at
        ):
            failures.append("RECOVERY_OBJECTIVE_UNAPPROVED")
        if backup is None or backup.status != BackupStatus.RECOVERABLE:
            failures.append("VERIFIED_BACKUP_MISSING")
        if not plan_version:
            failures.append("RECOVERY_PLAN_MISSING")
        if not mandatory_dependencies_ready:
            failures.append("MANDATORY_DEPENDENCY_NOT_READY")
        return ReadinessResult(not failures, tuple(failures))
