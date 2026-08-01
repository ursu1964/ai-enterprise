from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ai_enterprise.domain.hashing import hash_json
from ai_enterprise.domain.recovery.bindings import approval_binding_hash
from ai_enterprise.infrastructure.database.models import (
    ProjectModel,
    RecoveryAssessmentModel,
    RecoveryAttemptModel,
    RollbackApprovalModel,
    RollbackRecordModel,
)
from ai_enterprise.infrastructure.recovery.attempt_store import (
    RecoveryAttemptStoreError,
    SqlAlchemyRecoveryAttemptStore,
)


def _bound_models() -> tuple[
    RecoveryAttemptModel,
    RollbackApprovalModel,
    RecoveryAssessmentModel,
    RollbackRecordModel,
    ProjectModel,
]:
    project_id = uuid4()
    attempt_id = uuid4()
    approval_id = uuid4()
    assessment_id = uuid4()
    rollback_id = uuid4()
    commands = [{"argv": ["pytest"], "timeout_seconds": 60}]
    commands_hash = hash_json({"commands": commands})
    project = ProjectModel(
        id=project_id,
        name="p",
        description="p",
        status="active",
        manifest_hash="a" * 64,
        manifest={},
        repository_path="/tmp/repo",
        repository_url="ssh://git/repo",
        default_branch="main",
    )
    rollback = RollbackRecordModel(
        id=rollback_id,
        integration_attempt_id=uuid4(),
        integration_commit_id=uuid4(),
        project_id=project_id,
        target_branch="main",
        integration_commit_sha="b" * 40,
        parent_commit_sha="a" * 40,
        integration_tree_sha="d" * 40,
        parent_tree_sha="c" * 40,
        changed_paths=[
            {
                "path": "app.py",
                "change_type": "M",
                "old_mode": "100644",
                "new_mode": "100644",
                "old_path": None,
            }
        ],
        changed_paths_sha256="1" * 64,
        inverse_diff_artifact_id=uuid4(),
        inverse_diff_sha256="2" * 64,
        original_patch_sha256="3" * 64,
        approved_test_commands=commands,
        approved_test_commands_sha256=commands_hash,
        external_side_effects_declared=False,
        database_change_detected=False,
        deployment_change_detected=False,
        recovery_policy_version="recovery-v1",
        rollback_binding_sha256="4" * 64,
        created_at=datetime.now(UTC),
    )
    assessment = RecoveryAssessmentModel(
        id=assessment_id,
        incident_id=uuid4(),
        rollback_record_id=rollback_id,
        status="revertible",
        recommended_strategy="revert_commit",
        risk_level="medium",
        expected_remote_head_sha="e" * 40,
        integration_commit_is_ancestor=True,
        direct_revert_possible=True,
        database_coordination_required=False,
        external_coordination_required=False,
        required_test_commands=commands,
        findings=[],
        assessment_policy_version="recovery-assessment-v1",
        assessment_binding_sha256="5" * 64,
        assessed_by="human:assessor",
        assessed_at=datetime.now(UTC),
    )
    binding = approval_binding_hash(
        recovery_assessment_id=str(assessment_id),
        rollback_record_id=str(rollback_id),
        repository_id=str(project_id),
        target_branch="main",
        strategy="revert_commit",
        expected_remote_head_sha="e" * 40,
        integration_commit_sha="b" * 40,
        required_test_commands_sha256=commands_hash,
        assessment_policy_version=assessment.assessment_policy_version,
        recovery_policy_version=rollback.recovery_policy_version,
    )
    approval = RollbackApprovalModel(
        id=approval_id,
        recovery_assessment_id=assessment_id,
        rollback_record_id=rollback_id,
        project_id=project_id,
        target_branch="main",
        recovery_strategy="revert_commit",
        expected_remote_head_sha="e" * 40,
        integration_commit_sha="b" * 40,
        required_test_commands=commands,
        required_test_commands_sha256=commands_hash,
        approval_binding_sha256=binding,
        status="consumed",
        approver_subject="human:approver",
        reason="confirmed",
        approved_at=datetime.now(UTC),
        consumed_at=datetime.now(UTC),
    )
    attempt = RecoveryAttemptModel(
        id=attempt_id,
        rollback_approval_id=approval_id,
        recovery_assessment_id=assessment_id,
        rollback_record_id=rollback_id,
        project_id=project_id,
        target_branch="main",
        expected_remote_head_sha="e" * 40,
        integration_commit_sha="b" * 40,
        recovery_strategy="revert_commit",
        status="queued",
        correlation_id=uuid4(),
    )
    return attempt, approval, assessment, rollback, project


def test_store_accepts_exact_consumed_approval_binding() -> None:
    values = _bound_models()
    SqlAlchemyRecoveryAttemptStore._validate(*values)
    commands = SqlAlchemyRecoveryAttemptStore._commands(values[1])
    assert commands[0].argv == ("pytest",)
    assert SqlAlchemyRecoveryAttemptStore._scope(values[3]).allowed_paths == ("app.py",)


def test_store_rejects_modified_approval_tests() -> None:
    attempt, approval, assessment, rollback, project = _bound_models()
    approval.required_test_commands = [{"argv": ["python", "unsafe.py"]}]
    with pytest.raises(RecoveryAttemptStoreError, match="RECOVERY_TEST_BINDING_MISMATCH"):
        SqlAlchemyRecoveryAttemptStore._validate(attempt, approval, assessment, rollback, project)


def test_store_rejects_non_revert_strategy() -> None:
    attempt, approval, assessment, rollback, project = _bound_models()
    attempt.recovery_strategy = "manual_recovery"
    with pytest.raises(RecoveryAttemptStoreError, match="RECOVERY_STRATEGY_NOT_EXECUTABLE"):
        SqlAlchemyRecoveryAttemptStore._validate(attempt, approval, assessment, rollback, project)
