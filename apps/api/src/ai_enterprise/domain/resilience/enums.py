from enum import StrEnum


class CriticalityTier(StrEnum):
    TIER_0 = "tier_0"
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"


class DependencyRequirement(StrEnum):
    MANDATORY = "mandatory"
    REPLACEABLE = "replaceable"
    OPTIONAL = "optional"
    CACHED = "cached"
    MANUAL = "manually_substitutable"


class ContinuityMode(StrEnum):
    NORMAL = "normal"
    READ_ONLY_GOVERNANCE = "read_only_governance"
    NO_EXTERNAL_ACTION = "no_external_action"
    AUDIT_PRESERVATION = "audit_preservation"
    INCIDENT_ONLY = "incident_only"


class Capability(StrEnum):
    READ_GOVERNANCE = "read_governance"
    CREATE_PROJECT = "create_project"
    START_AGENT_WORK = "start_agent_work"
    GRANT_APPROVAL = "grant_approval"
    INTEGRATE_PATCH = "integrate_patch"
    EXECUTE_RECOVERY = "execute_recovery"
    DISPATCH_EXTERNAL_COMMAND = "dispatch_external_command"
    APPEND_AUDIT = "append_audit"


class BackupStatus(StrEnum):
    CREATED = "created"
    VERIFYING = "verifying"
    RECOVERABLE = "recoverable"
    FAILED = "failed"


class RestoreStatus(StrEnum):
    QUEUED = "queued"
    RESTORING = "restoring"
    VERIFYING = "verifying"
    PASSED = "passed"
    FAILED = "failed"


class DisasterRecoveryStatus(StrEnum):
    DECLARED = "declared"
    WRITES_FROZEN = "writes_frozen"
    AUTHORITY_VERIFIED = "authority_verified"
    RECOVERY_POINT_SELECTED = "recovery_point_selected"
    RESTORING = "restoring"
    VERIFYING = "verifying"
    DEGRADED = "degraded"
    RECONCILING = "reconciling"
    EXIT_REVIEW = "exit_review"
    COMPLETED = "completed"
    FAILED = "failed"
