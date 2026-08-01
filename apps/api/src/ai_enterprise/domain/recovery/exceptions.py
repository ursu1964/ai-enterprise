class RecoveryError(Exception):
    code = "RECOVERY_ERROR"


class InvalidRecoveryTransition(RecoveryError):
    code = "INVALID_RECOVERY_TRANSITION"


class RollbackRecordNotFound(RecoveryError):
    code = "ROLLBACK_RECORD_NOT_FOUND"


class RecoveryAssessmentStale(RecoveryError):
    code = "RECOVERY_ASSESSMENT_STALE"


class RollbackApprovalHumanRequired(RecoveryError):
    code = "ROLLBACK_APPROVAL_HUMAN_REQUIRED"


class RollbackApprovalNotActive(RecoveryError):
    code = "ROLLBACK_APPROVAL_NOT_ACTIVE"


class RecoveryRemoteStateChanged(RecoveryError):
    code = "RECOVERY_REMOTE_STATE_CHANGED"


class RecoveryHistoryInvalid(RecoveryError):
    code = "RECOVERY_HISTORY_INVALID"


class RevertConflict(RecoveryError):
    code = "REVERT_CONFLICT"

    def __init__(self, message: str, *, paths: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.paths = paths


class RevertFailed(RecoveryError):
    code = "REVERT_FAILED"


class RollbackScopeViolation(RecoveryError):
    code = "ROLLBACK_SCOPE_VIOLATION"


class RecoveryTestFailed(RecoveryError):
    code = "RECOVERY_TEST_FAILED"


class RecoveryPushUncertain(RecoveryError):
    code = "RECOVERY_PUSH_UNCERTAIN"


class RecoveryRemoteVerificationFailed(RecoveryError):
    code = "RECOVERY_REMOTE_VERIFICATION_FAILED"

