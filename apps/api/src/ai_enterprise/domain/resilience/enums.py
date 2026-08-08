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


class GovernanceAvailabilityClass(StrEnum):
    NON_CRITICAL = "non_critical"
    STANDARD = "standard"
    HIGH = "high"
    MISSION_CRITICAL = "mission_critical"
    SAFETY_CRITICAL = "safety_critical"
    CONTINUITY_MANDATORY = "continuity_mandatory"


class GovernanceDependencyCriticality(StrEnum):
    HARD_REQUIRED = "hard_required"
    SAFETY_REQUIRED = "safety_required"
    AUTHORITY_REQUIRED = "authority_required"
    ASSURANCE_REQUIRED = "assurance_required"
    DEGRADABLE = "degradable"
    OPTIONAL = "optional"


class GovernanceDependencyState(StrEnum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    STALE = "stale"
    PARTITIONED = "partitioned"
    RATE_LIMITED = "rate_limited"
    OVERLOADED = "overloaded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class ContinuityMode(StrEnum):
    NORMAL = "normal"
    READ_ONLY_GOVERNANCE = "read_only_governance"
    NO_EXTERNAL_ACTION = "no_external_action"
    AUDIT_PRESERVATION = "audit_preservation"
    INCIDENT_ONLY = "incident_only"
    FAIL_CLOSED = "fail_closed"
    QUEUE_ONLY = "queue_only"
    PREAUTHORIZED_ONLY = "preauthorized_only"
    CACHED_GOVERNANCE = "cached_governance"
    SAFE_OPERATION_ONLY = "safe_operation_only"
    EMERGENCY_OPERATION = "emergency_operation"
    DEGRADED_AUTONOMY = "degraded_autonomy"
    MANUAL_GOVERNANCE = "manual_governance"
    RECOVERY_MODE = "recovery_mode"


class GovernanceContinuityEffect(StrEnum):
    CONTINUE_NORMAL = "continue_normal"
    CONTINUE_DEGRADED = "continue_degraded"
    QUEUE = "queue"
    READ_ONLY = "read_only"
    SAFE_OPERATION_ONLY = "safe_operation_only"
    EMERGENCY_MODE = "emergency_mode"
    BLOCK = "block"


class GovernanceAdmissionEffect(StrEnum):
    ADMIT = "admit"
    ADMIT_DEGRADED = "admit_degraded"
    QUEUE = "queue"
    DEFER = "defer"
    REJECT = "reject"
    EMERGENCY_ONLY = "emergency_only"


class GovernanceDeadlineClass(StrEnum):
    HARD = "hard"
    FIRM = "firm"
    SOFT = "soft"
    OBSERVATIONAL = "observational"


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
