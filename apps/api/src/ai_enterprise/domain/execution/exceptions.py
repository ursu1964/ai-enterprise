class ExecutionError(Exception):
    code = "execution_error"


class WorkPackageNotApprovedError(ExecutionError):
    code = "work_package_not_approved"


class ApprovalInvalidError(ExecutionError):
    code = "approval_invalid"


class BaseCommitMismatchError(ExecutionError):
    code = "base_commit_mismatch"


class SnapshotCreationError(ExecutionError):
    code = "snapshot_creation_failed"


class ImplementationPlanError(ExecutionError):
    code = "implementation_plan_failed"


class ContainerExecutionError(ExecutionError):
    code = "container_execution_failed"


class ExecutionTimeoutError(ExecutionError):
    code = "execution_timed_out"


class ScopeViolationError(ExecutionError):
    code = "scope_violation"


class InvalidTestCommandError(ExecutionError):
    code = "invalid_test_command"


class PatchGenerationError(ExecutionError):
    code = "patch_generation_failed"


class HostRepositoryChangedError(ExecutionError):
    code = "host_repository_changed"


class IdempotencyConflictError(ExecutionError):
    code = "idempotency_conflict"
