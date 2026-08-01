from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from ai_enterprise.application.resilience.service import ResilienceControlPlane
from ai_enterprise.domain.resilience.entities import (
    BackupManifest,
    ContinuityActivation,
    ContinuityPolicy,
    DisasterRecoveryRun,
    RecoveryObjective,
    RestoreVerification,
)
from ai_enterprise.domain.resilience.enums import (
    BackupStatus,
    Capability,
    ContinuityMode,
    CriticalityTier,
    DisasterRecoveryStatus,
    RestoreStatus,
)
from ai_enterprise.domain.resilience.policies import ResiliencePolicyError

NOW = datetime(2026, 7, 31, tzinfo=UTC)


def _objective() -> RecoveryObjective:
    return RecoveryObjective(
        uuid4(),
        CriticalityTier.TIER_0,
        60,
        30,
        180,
        60,
        "primary",
        "deputy",
        1,
        "risk-board",
        NOW,
    )


def _backup() -> BackupManifest:
    return BackupManifest(
        uuid4(),
        "control-plane",
        "hash",
        10,
        1000,
        "regional-v1",
        "schema-v1",
        "checkpoint",
        ("recovery-site",),
    )


def test_tier_zero_objective_requires_distinct_owners_approval_and_valid_times() -> None:
    service = ResilienceControlPlane()
    service.validate_objective(_objective())
    with pytest.raises(ResiliencePolicyError):
        service.validate_objective(replace(_objective(), approved_by=None, approved_at=None))
    with pytest.raises(ResiliencePolicyError):
        service.validate_objective(replace(_objective(), deputy_owner="primary"))
    with pytest.raises(ResiliencePolicyError):
        service.validate_objective(replace(_objective(), mtpd_seconds=100))


def test_capability_gate_fails_closed_and_prohibition_dominates() -> None:
    service = ResilienceControlPlane()
    assert not service.authorize(Capability.INTEGRATE_PATCH, None, now=NOW).allowed
    allow = ContinuityPolicy(
        ContinuityMode.NO_EXTERNAL_ACTION,
        frozenset({Capability.INTEGRATE_PATCH}),
        frozenset(),
        600,
        1,
    )
    deny = ContinuityPolicy(
        ContinuityMode.INCIDENT_ONLY,
        frozenset(),
        frozenset({Capability.INTEGRATE_PATCH}),
        600,
        2,
    )
    activations = (
        ContinuityActivation(uuid4(), allow, NOW, NOW + timedelta(minutes=10), "a", "x"),
        ContinuityActivation(uuid4(), deny, NOW, NOW + timedelta(minutes=10), "b", "y"),
    )
    decision = service.authorize(Capability.INTEGRATE_PATCH, activations, now=NOW)
    assert not decision.allowed and decision.reason == "EXPLICITLY_PROHIBITED"


def test_expired_activation_does_not_silently_restore_mutations() -> None:
    policy = ContinuityPolicy(
        ContinuityMode.READ_ONLY_GOVERNANCE,
        frozenset({Capability.READ_GOVERNANCE}),
        frozenset(),
        60,
        1,
    )
    activation = ContinuityActivation(
        uuid4(), policy, NOW - timedelta(minutes=2), NOW - timedelta(minutes=1), "a", "x"
    )
    service = ResilienceControlPlane()
    assert service.authorize(Capability.READ_GOVERNANCE, (activation,), now=NOW).allowed
    assert not service.authorize(Capability.CREATE_PROJECT, (activation,), now=NOW).allowed


def test_invalid_or_overlong_continuity_policy_fails_closed() -> None:
    policy = ContinuityPolicy(
        ContinuityMode.NO_EXTERNAL_ACTION,
        frozenset({Capability.INTEGRATE_PATCH}),
        frozenset({Capability.INTEGRATE_PATCH}),
        30,
        1,
    )
    activation = ContinuityActivation(
        uuid4(), policy, NOW, NOW + timedelta(minutes=2), "a", "invalid"
    )
    decision = ResilienceControlPlane().authorize(
        Capability.INTEGRATE_PATCH, (activation,), now=NOW
    )
    assert not decision.allowed and decision.reason == "INVALID_CONTINUITY_POLICY_STATE"


def test_backup_requires_isolated_complete_restore_verification() -> None:
    backup = _backup()
    checks = {
        "schema": True,
        "references": True,
        "artifacts": True,
        "audit_chain": True,
        "git_reachability": True,
        "jobs": True,
    }
    verification = RestoreVerification(
        uuid4(), backup.id, RestoreStatus.PASSED, True, True, True, checks
    )
    recovered = ResilienceControlPlane().verify_restore(backup, verification)
    assert recovered.status == BackupStatus.RECOVERABLE
    with pytest.raises(ResiliencePolicyError):
        ResilienceControlPlane().verify_restore(
            backup, replace(verification, external_dispatch_blocked=False)
        )
    with pytest.raises(ResiliencePolicyError):
        ResilienceControlPlane().verify_restore(
            backup, replace(verification, checks={**checks, "artifacts": False})
        )


def test_dr_cannot_skip_steps_or_complete_with_unreconciled_state() -> None:
    service = ResilienceControlPlane()
    run = DisasterRecoveryRun(uuid4(), 1, DisasterRecoveryStatus.DECLARED, "commander", "site-b")
    with pytest.raises(ResiliencePolicyError):
        service.advance_dr(run, DisasterRecoveryStatus.RESTORING)
    run = replace(run, status=DisasterRecoveryStatus.EXIT_REVIEW, unresolved_workflows=1)
    with pytest.raises(ResiliencePolicyError):
        service.advance_dr(run, DisasterRecoveryStatus.COMPLETED)
    run = replace(run, unresolved_workflows=0, exit_reviewed_by="independent-reviewer")
    assert service.advance_dr(run, DisasterRecoveryStatus.COMPLETED).status == (
        DisasterRecoveryStatus.COMPLETED
    )


def test_readiness_fails_closed_without_verified_foundations() -> None:
    result = ResilienceControlPlane().readiness(
        objective=None, backup=None, plan_version=None, mandatory_dependencies_ready=False
    )
    assert not result.ready
    assert set(result.failures) == {
        "RECOVERY_OBJECTIVE_MISSING",
        "VERIFIED_BACKUP_MISSING",
        "RECOVERY_PLAN_MISSING",
        "MANDATORY_DEPENDENCY_NOT_READY",
    }
    ready = ResilienceControlPlane().readiness(
        objective=_objective(),
        backup=replace(_backup(), status=BackupStatus.RECOVERABLE),
        plan_version=1,
        mandatory_dependencies_ready=True,
    )
    assert ready.ready
