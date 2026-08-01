from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest

from ai_enterprise.domain.recovery.bindings import hash_commands, rollback_binding_hash
from ai_enterprise.domain.recovery.entities import (
    ChangedPath,
    RecoveryAttemptStatus,
    RemoteState,
    RollbackApproval,
    RollbackRecord,
)
from ai_enterprise.domain.recovery.enums import (
    FailureClass,
    PipelineStage,
    PushReconciliation,
    RecoveryAssessmentStatus,
    RecoveryStrategy,
    RollbackApprovalStatus,
)
from ai_enterprise.domain.recovery.exceptions import (
    InvalidRecoveryTransition,
    RecoveryHistoryInvalid,
    RecoveryRemoteStateChanged,
)
from ai_enterprise.domain.recovery.policies import (
    PushReconciliationPolicy,
    RecoveryRemoteStatePolicy,
    RecoveryRetryPolicy,
    RecoveryRiskClassifier,
    RecoveryStrategyPolicy,
)
from ai_enterprise.domain.recovery.state_machine import assert_recovery_transition


def _rollback_record(**overrides: Any) -> RollbackRecord:
    values: dict[str, Any] = {
        "id": uuid4(),
        "integration_attempt_id": uuid4(),
        "integration_commit_id": uuid4(),
        "repository_id": uuid4(),
        "target_branch": "main",
        "integration_commit_sha": "b" * 40,
        "parent_commit_sha": "a" * 40,
        "integration_tree_sha": "d" * 40,
        "parent_tree_sha": "c" * 40,
        "changed_paths": (ChangedPath("src/a.py", "modified"),),
        "changed_paths_sha256": "1" * 64,
        "inverse_diff_artifact_id": uuid4(),
        "inverse_diff_sha256": "2" * 64,
        "original_patch_sha256": "3" * 64,
        "approved_test_commands": ({"argv": ["pytest"]},),
        "approved_test_commands_sha256": "4" * 64,
        "external_side_effects_declared": False,
        "database_change_detected": False,
        "deployment_change_detected": False,
        "recovery_policy_version": "recovery-v1",
        "rollback_binding_sha256": "5" * 64,
        "created_at": datetime.now(UTC),
    }
    values.update(overrides)
    return RollbackRecord(**values)


def _approval() -> RollbackApproval:
    return RollbackApproval(
        id=uuid4(),
        recovery_assessment_id=uuid4(),
        rollback_record_id=uuid4(),
        repository_id=uuid4(),
        target_branch="main",
        recovery_strategy=RecoveryStrategy.REVERT_COMMIT,
        expected_remote_head_sha="d" * 40,
        integration_commit_sha="b" * 40,
        required_test_commands=({"argv": ["pytest"]},),
        required_test_commands_sha256="1" * 64,
        approval_binding_sha256="2" * 64,
        status=RollbackApprovalStatus.ACTIVE,
        approver_subject="human:1",
        reason="Regression confirmed",
        approved_at=datetime.now(UTC),
    )


def test_strategy_is_conservative_for_risky_change() -> None:
    decision = RecoveryStrategyPolicy().determine(
        rollback_record=_rollback_record(database_change_detected=True),
        remote_state=RemoteState("d" * 40, "e" * 40, True),
    )
    assert decision.strategy == RecoveryStrategy.COMPENSATING_PATCH
    assert decision.status == RecoveryAssessmentStatus.COMPENSATION_REQUIRED
    assert decision.database_coordination_required is True


def test_missing_ancestry_requires_manual_recovery() -> None:
    decision = RecoveryStrategyPolicy().determine(
        rollback_record=_rollback_record(),
        remote_state=RemoteState("d" * 40, "e" * 40, False),
    )
    assert decision.strategy == RecoveryStrategy.MANUAL_RECOVERY
    assert decision.risk_level == "critical"


def test_remote_policy_binds_head_and_ancestry() -> None:
    approval = _approval()
    policy = RecoveryRemoteStatePolicy()
    policy.verify_before_execution(
        approval=approval,
        current_remote_head_sha=approval.expected_remote_head_sha,
        integration_commit_is_ancestor=True,
    )
    with pytest.raises(RecoveryRemoteStateChanged):
        policy.verify_before_execution(
            approval=approval,
            current_remote_head_sha="f" * 40,
            integration_commit_is_ancestor=True,
        )
    with pytest.raises(RecoveryHistoryInvalid):
        policy.verify_before_execution(
            approval=approval,
            current_remote_head_sha=approval.expected_remote_head_sha,
            integration_commit_is_ancestor=False,
        )


def test_retry_policy_never_blindly_retries_push() -> None:
    decision = RecoveryRetryPolicy().decide(
        stage=PipelineStage.PUSH,
        failure_class=FailureClass.TRANSIENT_INFRASTRUCTURE,
        workspace_modified=True,
        push_started=True,
    )
    assert decision.automatically_retry is False
    assert decision.reconcile_remote_first is True


def test_push_reconciliation_has_three_explicit_outcomes() -> None:
    policy = PushReconciliationPolicy()
    assert policy.reconcile(
        remote_head_sha="new", expected_commit_sha="new", old_head_sha="old"
    ) == PushReconciliation.PUSH_SUCCEEDED
    assert policy.reconcile(
        remote_head_sha="old", expected_commit_sha="new", old_head_sha="old"
    ) == PushReconciliation.NOT_PUSHED
    assert policy.reconcile(
        remote_head_sha="other", expected_commit_sha="new", old_head_sha="old"
    ) == PushReconciliation.REMOTE_DIVERGED


def test_state_machine_rejects_skipping_tests() -> None:
    assert_recovery_transition(
        RecoveryAttemptStatus.RUNNING_TESTS,
        RecoveryAttemptStatus.CREATING_COMMIT,
    )
    with pytest.raises(InvalidRecoveryTransition):
        assert_recovery_transition(
            RecoveryAttemptStatus.CREATING_REVERT,
            RecoveryAttemptStatus.PUSHING,
        )


def test_risk_classifier_flags_database_and_deployment_paths() -> None:
    assert RecoveryRiskClassifier().classify(
        changed_paths=("migrations/001.py", "helm/app/values.yaml")
    ) == (True, True, False)


def test_binding_is_canonical_and_sensitive_to_protected_fields() -> None:
    commands = ({"timeout": 30, "argv": ["pytest"]},)
    assert hash_commands(commands) == hash_commands(
        ({"argv": ["pytest"], "timeout": 30},)
    )
    arguments = {
        "integration_attempt_id": "attempt",
        "integration_commit_sha": "commit",
        "parent_commit_sha": "parent",
        "integration_tree_sha": "tree",
        "parent_tree_sha": "parent-tree",
        "changed_paths_sha256": "paths",
        "inverse_diff_sha256": "inverse",
        "original_patch_sha256": "patch",
        "approved_test_commands_sha256": "tests",
        "recovery_policy_version": "v1",
    }
    original = rollback_binding_hash(**arguments)
    arguments["parent_commit_sha"] = "changed"
    assert rollback_binding_hash(**arguments) != original

