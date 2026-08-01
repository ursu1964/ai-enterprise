from enum import StrEnum


class OrganizationStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class RoleStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class AgentStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class AssignmentStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"
    COMPLETED = "completed"


class Availability(StrEnum):
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    BUSY = "busy"
    DRAINING = "draining"
    SUSPENDED = "suspended"
    OFFLINE = "offline"
