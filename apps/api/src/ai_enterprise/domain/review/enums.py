from enum import StrEnum


class PatchReviewStatus(StrEnum):
    PENDING = "pending"
    PREPARING = "preparing"
    RUNNING = "running"
    EVALUATING = "evaluating"
    ACCEPTED = "accepted"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class FindingSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingStatus(StrEnum):
    OPEN = "open"
    ACCEPTED_RISK = "accepted_risk"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ReviewDecision(StrEnum):
    ACCEPT = "accept"
    CHANGES_REQUESTED = "changes_requested"
    REJECT = "reject"
