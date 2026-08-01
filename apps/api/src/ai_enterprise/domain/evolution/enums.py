from enum import StrEnum


class LifecycleStatus(StrEnum):
    DRAFT = "draft"
    TESTING = "testing"
    APPROVED = "approved"
    ACTIVE = "active"
    PAUSED = "paused"
    REJECTED = "rejected"
    RETIRED = "retired"


class PolicyLevel(StrEnum):
    TASK = "task"
    WORKFLOW = "workflow"
    PROJECT = "project"
    PORTFOLIO = "portfolio"
    ENTERPRISE = "enterprise"
    SECURITY = "security"
    REGULATORY = "regulatory"
    CONSTITUTIONAL = "constitutional"


class Compatibility(StrEnum):
    BACKWARD = "backward"
    FORWARD = "forward"
    FULL = "full"
    BREAKING = "breaking"
    SEMANTICALLY_BREAKING = "semantically_breaking"


class RolloutStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"


class ControlEffectiveness(StrEnum):
    UNKNOWN = "unknown"
    EFFECTIVE = "effective"
    INEFFECTIVE = "ineffective"
