from __future__ import annotations

from datetime import datetime

from ai_enterprise.domain.resilience.entities import (
    BackupManifest,
    CapabilityDecision,
    ContinuityActivation,
    DisasterRecoveryRun,
    ReadinessResult,
    RecoveryObjective,
    RestoreVerification,
)
from ai_enterprise.domain.resilience.enums import Capability, DisasterRecoveryStatus
from ai_enterprise.domain.resilience.policies import (
    BackupRecoveryPolicy,
    CapabilityGate,
    DisasterRecoveryStateMachine,
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
