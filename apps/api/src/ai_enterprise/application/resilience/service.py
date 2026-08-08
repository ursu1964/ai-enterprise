from __future__ import annotations

from datetime import datetime

from ai_enterprise.domain.resilience.entities import (
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
from ai_enterprise.domain.resilience.enums import Capability, DisasterRecoveryStatus
from ai_enterprise.domain.resilience.policies import (
    BackupRecoveryPolicy,
    CapabilityGate,
    DisasterRecoveryStateMachine,
    GovernanceAvailabilityPolicy,
    GovernancePerformancePolicy,
    ReadinessPolicy,
    RecoveryObjectivePolicy,
)


class ResilienceControlPlane:
    """Pure command service; persistence and real providers remain injected."""

    def validate_objective(self, objective: RecoveryObjective) -> None:
        RecoveryObjectivePolicy().validate(objective)

    def authorize(
        self,
        capability: Capability,
        activations: tuple[ContinuityActivation, ...] | None,
        *,
        now: datetime,
    ) -> CapabilityDecision:
        return CapabilityGate().decide(capability, activations, now=now)

    def verify_restore(
        self, backup: BackupManifest, verification: RestoreVerification
    ) -> BackupManifest:
        return BackupRecoveryPolicy().mark_recoverable(backup, verification)

    def decide_continuity(
        self,
        contract: GovernanceAvailabilityContract,
        dependencies: tuple[GovernanceDependencyAvailability, ...],
        *,
        lease: GovernanceContinuityLease | None,
        budget: GovernanceAvailabilityBudget | None,
        usage: GovernanceAvailabilityBudgetUsage | None,
        now: datetime,
    ) -> GovernanceContinuityDecision:
        return GovernanceAvailabilityPolicy().decide(
            contract,
            dependencies,
            lease=lease,
            budget=budget,
            usage=usage,
            now=now,
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
        return GovernanceAvailabilityPolicy().cached_authority_valid(
            authority,
            envelope,
            dimension=dimension,
            now=now,
            revocation_state_available=revocation_state_available,
        )

    def validate_latency_budget(self, budget: GovernanceLatencyBudget) -> None:
        GovernancePerformancePolicy().validate_budget(budget)

    def evaluate_deadline(
        self,
        deadline: GovernanceDeadline,
        *,
        started_at: datetime,
        completed_at: datetime,
        budget_milliseconds: int,
    ) -> GovernancePerformanceEvidence:
        return GovernancePerformancePolicy().evaluate_deadline(
            deadline,
            started_at=started_at,
            completed_at=completed_at,
            budget_milliseconds=budget_milliseconds,
        )

    def advance_dr(
        self, run: DisasterRecoveryRun, target: DisasterRecoveryStatus
    ) -> DisasterRecoveryRun:
        return DisasterRecoveryStateMachine().transition(run, target)

    def readiness(
        self,
        *,
        objective: RecoveryObjective | None,
        backup: BackupManifest | None,
        plan_version: int | None,
        mandatory_dependencies_ready: bool,
    ) -> ReadinessResult:
        return ReadinessPolicy().evaluate(
            objective=objective,
            backup=backup,
            plan_version=plan_version,
            mandatory_dependencies_ready=mandatory_dependencies_ready,
        )
