from enum import StrEnum


class RegistryStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class BindingStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class ToolSideEffect(StrEnum):
    READ_ONLY = "read_only"
    WORKSPACE_WRITE = "workspace_write"
    CANDIDATE_ARTIFACT_WRITE = "candidate_artifact_write"
    CONTROL_PLANE_WRITE = "control_plane_write"
    EXTERNAL_EFFECT = "external_effect"


class ToolInvocationStatus(StrEnum):
    REQUESTED = "requested"
    AUTHORIZED = "authorized"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DENIED = "denied"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
