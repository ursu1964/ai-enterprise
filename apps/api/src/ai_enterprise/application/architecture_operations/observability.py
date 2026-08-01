from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from ai_enterprise.observability import increment_metric


class ArchitectureMetric(StrEnum):
    RUNS = "architecture_runs_total"
    RUNS_ACTIVE = "architecture_runs_active"
    RUNS_COMPLETED = "architecture_runs_completed_total"
    RUNS_FAILED = "architecture_runs_failed_total"
    EXECUTION_ATTEMPTS = "architecture_execution_attempts_total"
    EXECUTION_ATTEMPT_DURATION = "architecture_execution_attempt_duration_seconds"
    EXECUTION_TIMEOUTS = "architecture_execution_timeouts_total"
    EXECUTION_REPAIRS = "architecture_execution_repairs_total"
    EXECUTION_VALIDATION_FAILURES = "architecture_execution_validation_failures_total"
    ARTIFACTS_CREATED = "architecture_artifacts_created_total"
    REVIEWS_OPEN = "architecture_reviews_open"
    REVIEWS_COMPLETED = "architecture_reviews_completed_total"
    CHANGES_REQUESTED = "architecture_changes_requested_total"
    REVISIONS = "architecture_revisions_total"
    APPROVALS = "architecture_approvals_total"
    APPROVAL_DENIALS = "architecture_approval_denials_total"
    ELIGIBILITY_CHECKS = "architecture_work_package_eligibility_checks_total"
    ELIGIBILITY_FAILURES = "architecture_work_package_eligibility_failures_total"


ALLOWED_LABELS: Final = frozenset(
    {"status", "model_name", "crew_version", "failure_code", "decision", "policy_version"}
)
FORBIDDEN_FIELDS: Final = frozenset(
    {
        "prompt",
        "raw_output",
        "artifact_content",
        "review_content",
        "approval_content",
        "secret",
        "token",
        "api_key",
        "authorization",
    }
)
HIGH_CARDINALITY_LABELS: Final = frozenset(
    {"project_id", "run_id", "attempt_id", "artifact_id", "actor_id", "correlation_id"}
)


def record_metric(metric: ArchitectureMetric, labels: Mapping[str, str] | None = None) -> None:
    """Record a metric after enforcing the architecture label-cardinality contract."""
    supplied = set(labels or {})
    invalid = supplied - ALLOWED_LABELS
    if invalid:
        raise ValueError(f"Invalid architecture metric labels: {sorted(invalid)}")
    # The current metric backend is unlabeled; validation makes a future exporter safe.
    increment_metric(metric.value)


def safe_event(event: str, metadata: Mapping[str, object]) -> dict[str, object]:
    """Build structured metadata without model content or credential-bearing fields."""
    unsafe = {key.lower() for key in metadata} & FORBIDDEN_FIELDS
    if unsafe:
        raise ValueError(f"Unsafe architecture log fields: {sorted(unsafe)}")
    return {"event": event, **metadata}


ARCHITECTURE_SPANS: Final = (
    "architecture.create_run",
    "architecture.claim_job",
    "architecture.execute_run",
    "architecture.build_input",
    "architecture.model.generate",
    "architecture.model.repair",
    "architecture.validate.schema",
    "architecture.validate.semantic",
    "architecture.render_markdown",
    "architecture.persist_artifact",
    "architecture.open_review",
    "architecture.complete_review",
    "architecture.create_revision",
    "architecture.approve",
    "architecture.verify_work_package_eligibility",
)


@dataclass(frozen=True, slots=True)
class ArchitectureWorkerHealth:
    database_reachable: bool
    queue_reachable: bool
    lease_store_reachable: bool
    accepting_work: bool
    active_leases: int = 0

    @property
    def live(self) -> bool:
        return self.database_reachable and self.queue_reachable

    @property
    def ready(self) -> bool:
        return self.live and self.lease_store_reachable and self.accepting_work

    def payload(self) -> dict[str, object]:
        return {"live": self.live, "ready": self.ready, "active_leases": self.active_leases}
