from enum import StrEnum


class ChangeCategory(StrEnum):
    ARCHITECTURE = "architecture"
    POLICY = "policy"
    WORKFLOW = "workflow"
    AGENT_DEFINITION = "agent_definition"
    CREW_TEMPLATE = "crew_template"
    SCHEMA = "schema"
    MODEL = "model"
    INFRASTRUCTURE = "infrastructure"
    SECURITY_CONTROL = "security_control"
    ORGANIZATIONAL = "organizational"
    EXTERNAL_INTEGRATION = "external_integration"


class ChangeRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChangeStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_ANALYSIS = "under_analysis"
    VALIDATION_REQUIRED = "validation_required"
    READY_FOR_DECISION = "ready_for_decision"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class ImpactKnowledge(StrEnum):
    KNOWN = "known"
    UNKNOWN = "unknown"


class ChangeDecisionType(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"
