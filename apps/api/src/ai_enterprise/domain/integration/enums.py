from enum import StrEnum


class PatchStatus(StrEnum):
    GENERATED = "generated"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"
    ACCEPTED = "accepted"
    INTEGRATION_ELIGIBLE = "integration_eligible"
    INTEGRATION_APPROVED = "integration_approved"
    INTEGRATING = "integrating"
    INTEGRATION_FAILED = "integration_failed"
    INTEGRATED = "integrated"
    SUPERSEDED = "superseded"


class IntegrationApprovalDecision(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"
    REVOKED = "revoked"
    CONSUMED = "consumed"


class IntegrationAttemptStatus(StrEnum):
    QUEUED = "queued"
    VERIFYING = "verifying"
    VERIFICATION_FAILED = "verification_failed"
    SNAPSHOT_READY = "snapshot_ready"
    APPLYING_PATCH = "applying_patch"
    PATCH_APPLY_FAILED = "patch_apply_failed"
    PATCH_APPLIED = "patch_applied"
    TESTING = "testing"
    TESTS_FAILED = "tests_failed"
    COMMIT_CREATING = "commit_creating"
    COMMIT_FAILED = "commit_failed"
    COMMIT_CREATED = "commit_created"
    PUSHING = "pushing"
    PUSH_FAILED = "push_failed"
    INTEGRATED = "integrated"
