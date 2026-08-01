from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from .entities import (
    BackupManifest,
    CapabilityDecision,
    ContinuityActivation,
    DisasterRecoveryRun,
    ReadinessResult,
    RecoveryObjective,
    RestoreVerification,
)
from .enums import (
    BackupStatus,
    Capability,
    CriticalityTier,
    DisasterRecoveryStatus,
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
