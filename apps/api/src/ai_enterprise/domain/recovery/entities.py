from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from ai_enterprise.domain.recovery.enums import (
    RecoveryAssessmentStatus,
    RecoveryAttemptStatus,
    RecoveryStrategy,
    RollbackApprovalStatus,
)


@dataclass(frozen=True, slots=True)
class ChangedPath:
    path: str
    change_type: str
    old_mode: str | None = None
    new_mode: str | None = None
    old_path: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "path": self.path,
            "change_type": self.change_type,
            "old_mode": self.old_mode,
            "new_mode": self.new_mode,
            "old_path": self.old_path,
        }


@dataclass(frozen=True, slots=True)
class RollbackRecord:
    id: UUID
    integration_attempt_id: UUID
    integration_commit_id: UUID
    repository_id: UUID
    target_branch: str
    integration_commit_sha: str
    parent_commit_sha: str
    integration_tree_sha: str
    parent_tree_sha: str
    changed_paths: tuple[ChangedPath, ...]
    changed_paths_sha256: str
    inverse_diff_artifact_id: UUID
    inverse_diff_sha256: str
    original_patch_sha256: str
    approved_test_commands: tuple[dict[str, Any], ...]
    approved_test_commands_sha256: str
    external_side_effects_declared: bool
    database_change_detected: bool
    deployment_change_detected: bool
    recovery_policy_version: str
    rollback_binding_sha256: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RecoveryIncident:
    id: UUID
    integration_attempt_id: UUID
    reported_by: str
    severity: str
    summary: str
    details: str
    affected_environment: str
    detected_at: datetime
    external_reference: str | None = None


@dataclass(frozen=True, slots=True)
class RecoveryFinding:
    code: str
    severity: str
    message: str


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    strategy: RecoveryStrategy
    status: RecoveryAssessmentStatus
    risk_level: str
    direct_revert_possible: bool
    database_coordination_required: bool
    external_coordination_required: bool
    findings: tuple[RecoveryFinding, ...]


@dataclass(frozen=True, slots=True)
class RecoveryAssessment:
    id: UUID
    incident_id: UUID
    rollback_record_id: UUID
    status: RecoveryAssessmentStatus
    recommended_strategy: RecoveryStrategy
    risk_level: str
    expected_remote_head_sha: str
    integration_commit_is_ancestor: bool
    direct_revert_possible: bool
    database_coordination_required: bool
    external_coordination_required: bool
    required_test_commands: tuple[dict[str, Any], ...]
    findings: tuple[RecoveryFinding, ...]
    assessment_policy_version: str
    assessment_binding_sha256: str
    assessed_at: datetime


@dataclass(frozen=True, slots=True)
class RollbackApproval:
    id: UUID
    recovery_assessment_id: UUID
    rollback_record_id: UUID
    repository_id: UUID
    target_branch: str
    recovery_strategy: RecoveryStrategy
    expected_remote_head_sha: str
    integration_commit_sha: str
    required_test_commands: tuple[dict[str, Any], ...]
    required_test_commands_sha256: str
    approval_binding_sha256: str
    status: RollbackApprovalStatus
    approver_subject: str
    reason: str
    approved_at: datetime
    consumed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class RecoveryAttempt:
    id: UUID
    rollback_approval_id: UUID
    recovery_assessment_id: UUID
    rollback_record_id: UUID
    repository_id: UUID
    target_branch: str
    expected_remote_head_sha: str
    integration_commit_sha: str
    strategy: RecoveryStrategy
    status: RecoveryAttemptStatus
    correlation_id: UUID


@dataclass(frozen=True, slots=True)
class RemoteState:
    head_sha: str
    head_tree_sha: str
    integration_commit_is_ancestor: bool


@dataclass(frozen=True, slots=True)
class CommitPlan:
    tree_sha: str
    parent_sha: str
    author_name: str
    author_email: str
    author_timestamp: datetime
    committer_name: str
    committer_email: str
    committer_timestamp: datetime
    message: str
    message_sha256: str
    policy_version: str

