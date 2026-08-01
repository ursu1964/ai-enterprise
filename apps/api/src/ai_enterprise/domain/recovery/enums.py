from enum import StrEnum


class RecoveryStrategy(StrEnum):
    NO_ACTION = "no_action"
    REVERT_COMMIT = "revert_commit"
    COMPENSATING_PATCH = "compensating_patch"
    MANUAL_RECOVERY = "manual_recovery"


class RecoveryAssessmentStatus(StrEnum):
    PENDING = "pending"
    EVALUATING = "evaluating"
    REVERTIBLE = "revertible"
    COMPENSATION_REQUIRED = "compensation_required"
    MANUAL_INTERVENTION_REQUIRED = "manual_intervention_required"
    NO_ACTION_REQUIRED = "no_action_required"
    FAILED = "failed"


class RollbackApprovalStatus(StrEnum):
    ACTIVE = "active"
    DENIED = "denied"
    REVOKED = "revoked"
    CONSUMED = "consumed"
    EXPIRED = "expired"


class RecoveryAttemptStatus(StrEnum):
    QUEUED = "queued"
    CLAIMED = "claimed"
    VERIFYING_REMOTE = "verifying_remote"
    PREPARING_WORKSPACE = "preparing_workspace"
    CREATING_REVERT = "creating_revert"
    APPLYING_COMPENSATION = "applying_compensation"
    RUNNING_TESTS = "running_tests"
    CREATING_COMMIT = "creating_commit"
    PUSHING = "pushing"
    VERIFYING_REMOTE_RESULT = "verifying_remote_result"
    RECOVERED = "recovered"
    REMOTE_STATE_CHANGED = "remote_state_changed"
    REVERT_CONFLICT = "revert_conflict"
    TEST_FAILED = "test_failed"
    COMMIT_FAILED = "commit_failed"
    PUSH_FAILED = "push_failed"
    PUSH_UNCERTAIN = "push_uncertain"
    REMOTE_VERIFICATION_FAILED = "remote_verification_failed"
    CANCELLED = "cancelled"


class FailureClass(StrEnum):
    TRANSIENT_INFRASTRUCTURE = "transient_infrastructure"
    DETERMINISTIC_VALIDATION = "deterministic_validation"
    CONCURRENCY_CONFLICT = "concurrency_conflict"
    AUTHORIZATION = "authorization"
    INTEGRITY = "integrity"
    EXTERNAL_SIDE_EFFECT = "external_side_effect"
    UNKNOWN = "unknown"


class PipelineStage(StrEnum):
    CLAIM = "claim"
    ARTIFACT_READ = "artifact_read"
    SNAPSHOT = "snapshot"
    REMOTE_VERIFICATION = "remote_verification"
    REVERT = "revert"
    TEST = "test"
    COMMIT = "commit"
    PUSH = "push"
    REMOTE_RESULT_VERIFICATION = "remote_result_verification"


class PushReconciliation(StrEnum):
    PUSH_SUCCEEDED = "push_succeeded"
    NOT_PUSHED = "not_pushed"
    REMOTE_DIVERGED = "remote_diverged"

