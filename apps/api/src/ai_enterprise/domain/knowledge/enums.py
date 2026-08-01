from enum import StrEnum


class TrustLevel(StrEnum):
    AUTHORITATIVE = "authoritative"
    VERIFIED = "verified"
    REVIEWED = "reviewed"
    UNVERIFIED = "unverified"
    EXTERNAL = "external"


class CandidateStatus(StrEnum):
    PROPOSED = "proposed"
    VALIDATING = "validating"
    VALIDATION_FAILED = "validation_failed"
    AWAITING_REVIEW = "awaiting_review"
    PROMOTED = "promoted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class TemporalStatus(StrEnum):
    CURRENT = "current"
    STALE = "stale"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"
    DISPUTED = "disputed"


class ReviewDecision(StrEnum):
    PROMOTE = "promote"
    CHANGES_REQUESTED = "changes_requested"
    REJECT = "reject"


class ContradictionStatus(StrEnum):
    DETECTED = "detected"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    ACCEPTED_EXCEPTION = "accepted_exception"
    DISMISSED = "dismissed"
