from ai_enterprise.domain.recovery.enums import RecoveryAttemptStatus
from ai_enterprise.domain.recovery.exceptions import InvalidRecoveryTransition

_TRANSITIONS: dict[RecoveryAttemptStatus, frozenset[RecoveryAttemptStatus]] = {
    RecoveryAttemptStatus.QUEUED: frozenset(
        {RecoveryAttemptStatus.CLAIMED, RecoveryAttemptStatus.CANCELLED}
    ),
    RecoveryAttemptStatus.CLAIMED: frozenset(
        {RecoveryAttemptStatus.VERIFYING_REMOTE, RecoveryAttemptStatus.CANCELLED}
    ),
    RecoveryAttemptStatus.VERIFYING_REMOTE: frozenset(
        {
            RecoveryAttemptStatus.PREPARING_WORKSPACE,
            RecoveryAttemptStatus.REMOTE_STATE_CHANGED,
            RecoveryAttemptStatus.REMOTE_VERIFICATION_FAILED,
        }
    ),
    RecoveryAttemptStatus.PREPARING_WORKSPACE: frozenset(
        {
            RecoveryAttemptStatus.CREATING_REVERT,
            RecoveryAttemptStatus.APPLYING_COMPENSATION,
            RecoveryAttemptStatus.REMOTE_VERIFICATION_FAILED,
        }
    ),
    RecoveryAttemptStatus.CREATING_REVERT: frozenset(
        {RecoveryAttemptStatus.RUNNING_TESTS, RecoveryAttemptStatus.REVERT_CONFLICT}
    ),
    RecoveryAttemptStatus.APPLYING_COMPENSATION: frozenset(
        {RecoveryAttemptStatus.RUNNING_TESTS, RecoveryAttemptStatus.REVERT_CONFLICT}
    ),
    RecoveryAttemptStatus.RUNNING_TESTS: frozenset(
        {RecoveryAttemptStatus.CREATING_COMMIT, RecoveryAttemptStatus.TEST_FAILED}
    ),
    RecoveryAttemptStatus.CREATING_COMMIT: frozenset(
        {RecoveryAttemptStatus.PUSHING, RecoveryAttemptStatus.COMMIT_FAILED}
    ),
    RecoveryAttemptStatus.PUSHING: frozenset(
        {
            RecoveryAttemptStatus.VERIFYING_REMOTE_RESULT,
            RecoveryAttemptStatus.PUSH_FAILED,
            RecoveryAttemptStatus.PUSH_UNCERTAIN,
        }
    ),
    RecoveryAttemptStatus.PUSH_UNCERTAIN: frozenset(
        {
            RecoveryAttemptStatus.VERIFYING_REMOTE_RESULT,
            RecoveryAttemptStatus.PUSH_FAILED,
            RecoveryAttemptStatus.REMOTE_STATE_CHANGED,
        }
    ),
    RecoveryAttemptStatus.VERIFYING_REMOTE_RESULT: frozenset(
        {
            RecoveryAttemptStatus.RECOVERED,
            RecoveryAttemptStatus.REMOTE_VERIFICATION_FAILED,
        }
    ),
}


def assert_recovery_transition(
    current: RecoveryAttemptStatus,
    target: RecoveryAttemptStatus,
) -> None:
    if target not in _TRANSITIONS.get(current, frozenset()):
        raise InvalidRecoveryTransition(f"Cannot transition recovery from {current} to {target}")


def can_transition(
    current: RecoveryAttemptStatus,
    target: RecoveryAttemptStatus,
) -> bool:
    return target in _TRANSITIONS.get(current, frozenset())
