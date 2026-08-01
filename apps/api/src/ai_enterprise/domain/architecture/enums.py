from enum import StrEnum


class ArchitectureRunStatus(StrEnum):
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED_VALIDATION = "failed_validation"
    FAILED = "failed"


class ArchitectureArtifactStatus(StrEnum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


class ArchitectureReviewStatus(StrEnum):
    OPEN = "open"
    COMPLETED = "completed"
    SUPERSEDED = "superseded"
    CANCELLED = "cancelled"


class ArchitectureReviewDecision(StrEnum):
    RECOMMEND_APPROVAL = "recommend_approval"
    REQUEST_CHANGES = "request_changes"
    REJECT = "reject"


class ArchitectureRevisionStatus(StrEnum):
    REQUESTED = "requested"
    RUN_CREATED = "run_created"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
