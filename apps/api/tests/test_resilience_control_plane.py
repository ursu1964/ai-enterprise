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
    GovernanceAvailabilityBudget,
    GovernanceAvailabilityBudgetUsage,
    GovernanceAvailabilityContract,
    GovernanceCachedAuthority,
    GovernanceContinuityLease,
    GovernanceDeadline,
    GovernanceDependencyAvailability,
    GovernanceLatencyBudget,
    GovernanceStalenessEnvelope,
    RecoveryObjective,
    RestoreVerification,
)
from ai_enterprise.domain.resilience.enums import (
    BackupStatus,
    Capability,
    ContinuityMode,
    CriticalityTier,
    DisasterRecoveryStatus,
    GovernanceAvailabilityClass,
    GovernanceContinuityEffect,
    GovernanceDeadlineClass,
    GovernanceDependencyCriticality,
    GovernanceDependencyState,
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


def test_availability_contract_fails_closed_for_unhandled_hard_dependency() -> None:
    contract = GovernanceAvailabilityContract(
        "availability-contract.ai-tools",
        Capability.DISPATCH_EXTERNAL_COMMAND,
        GovernanceAvailabilityClass.MISSION_CRITICAL,
        {},
        fail_open_allowed=False,
        cached_authority_allowed=False,
        queue_allowed=False,
        emergency_capabilities=frozenset(),
        required_evidence=True,
        policy_version=1,
    )
    dependency = GovernanceDependencyAvailability(
        "governance-evaluator",
        GovernanceDependencyState.UNAVAILABLE,
        GovernanceDependencyCriticality.HARD_REQUIRED,
        NOW,
    )

    decision = ResilienceControlPlane().decide_continuity(
        contract, (dependency,), lease=None, budget=None, usage=None, now=NOW
    )

    assert decision.effect == GovernanceContinuityEffect.BLOCK
    assert decision.mode == ContinuityMode.FAIL_CLOSED
    assert decision.reason == "HARD_REQUIRED_DEPENDENCY_UNAVAILABLE"


def test_degraded_continuity_requires_valid_lease_and_remaining_budget() -> None:
    contract = GovernanceAvailabilityContract(
        "availability-contract.ai-tools",
        Capability.DISPATCH_EXTERNAL_COMMAND,
        GovernanceAvailabilityClass.HIGH,
        {"risk": ContinuityMode.PREAUTHORIZED_ONLY},
        fail_open_allowed=False,
        cached_authority_allowed=True,
        queue_allowed=False,
        emergency_capabilities=frozenset(),
        required_evidence=True,
        policy_version=7,
    )
    dependency = GovernanceDependencyAvailability(
        "risk",
        GovernanceDependencyState.UNAVAILABLE,
        GovernanceDependencyCriticality.DEGRADABLE,
        NOW,
    )
    lease = GovernanceContinuityLease(
        uuid4(),
        Capability.DISPATCH_EXTERNAL_COMMAND,
        ContinuityMode.PREAUTHORIZED_ONLY,
        NOW,
        NOW + timedelta(minutes=5),
        "continuity-authority",
        "tool-gateway",
    )
    budget = GovernanceAvailabilityBudget(
        maximum_duration_seconds=300,
        maximum_executions=2,
        maximum_ai_tool_calls=1,
    )
    service = ResilienceControlPlane()

    allowed = service.decide_continuity(
        contract,
        (dependency,),
        lease=lease,
        budget=budget,
        usage=GovernanceAvailabilityBudgetUsage(NOW, executions=1),
        now=NOW + timedelta(seconds=10),
    )
    exhausted = service.decide_continuity(
        contract,
        (dependency,),
        lease=lease,
        budget=budget,
        usage=GovernanceAvailabilityBudgetUsage(NOW, executions=2),
        now=NOW + timedelta(seconds=10),
    )

    assert allowed.effect == GovernanceContinuityEffect.CONTINUE_DEGRADED
    assert allowed.lease_id == lease.id
    assert exhausted.effect == GovernanceContinuityEffect.BLOCK
    assert exhausted.reason == "CONTINUITY_BUDGET_EXHAUSTED"


def test_cached_authority_is_rejected_when_stale_or_revocation_state_is_unknown() -> None:
    authority = GovernanceCachedAuthority(
        "permission.customer.read",
        "support-service",
        Capability.READ_GOVERNANCE,
        NOW - timedelta(seconds=20),
        NOW + timedelta(minutes=1),
        revocation_sensitive=True,
    )
    envelope = GovernanceStalenessEnvelope(
        Capability.READ_GOVERNANCE,
        {"identity": 30},
    )
    service = ResilienceControlPlane()

    assert service.cached_authority_valid(
        authority,
        envelope,
        dimension="identity",
        now=NOW,
        revocation_state_available=True,
    )
    assert not service.cached_authority_valid(
        authority,
        envelope,
        dimension="identity",
        now=NOW,
        revocation_state_available=False,
    )
    assert not service.cached_authority_valid(
        authority,
        envelope,
        dimension="identity",
        now=NOW + timedelta(seconds=20),
        revocation_state_available=True,
    )


def test_performance_deadline_and_latency_budget_are_governance_constraints() -> None:
    service = ResilienceControlPlane()
    service.validate_latency_budget(
        GovernanceLatencyBudget(
            Capability.DISPATCH_EXTERNAL_COMMAND,
            end_to_end_milliseconds=100,
            evaluation_milliseconds=30,
            authorization_milliseconds=30,
            evidence_milliseconds=20,
            revocation_milliseconds=10,
        )
    )
    with pytest.raises(ResiliencePolicyError):
        service.validate_latency_budget(
            GovernanceLatencyBudget(
                Capability.DISPATCH_EXTERNAL_COMMAND,
                end_to_end_milliseconds=50,
                evaluation_milliseconds=30,
                authorization_milliseconds=30,
                evidence_milliseconds=10,
            )
        )

    deadline = GovernanceDeadline(
        "commit-auth-deadline",
        Capability.DISPATCH_EXTERNAL_COMMAND,
        GovernanceDeadlineClass.HARD,
        NOW + timedelta(milliseconds=50),
        GovernanceContinuityEffect.BLOCK,
    )
    evidence = service.evaluate_deadline(
        deadline,
        started_at=NOW,
        completed_at=NOW + timedelta(milliseconds=80),
        budget_milliseconds=100,
    )

    assert not evidence.deadline_met
    assert evidence.reason == "HARD_DEADLINE_MISSED"
