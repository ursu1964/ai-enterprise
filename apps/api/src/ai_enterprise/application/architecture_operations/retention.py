from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ArchitectureRetentionPolicy:
    raw_success_days: int = 365
    raw_failure_days: int = 90
    operational_log_days: int = 90
    trace_days: int = 30
    metric_days: int = 450
    immutable_record_kinds: frozenset[str] = frozenset(
        {"artifact", "approval", "review", "revision_request", "audit_event", "attempt_metadata"}
    )

    def may_delete(self, record_kind: str, *, evidence_retained: bool, audited: bool) -> bool:
        if record_kind in self.immutable_record_kinds:
            return False
        bounded = record_kind in {"raw_success", "raw_failure", "operational_log", "trace"}
        return bounded and evidence_retained and audited


REQUIRED_BACKUP_COLLECTIONS = frozenset(
    {
        "architecture_runs",
        "architecture_execution_attempts",
        "architecture_artifacts",
        "architecture_reviews",
        "architecture_revision_requests",
        "architecture_approvals",
        "audit_events",
        "jobs",
        "project_manifests",
        "requirements_artifacts",
        "approvals",
    }
)

REQUIRED_RESTORE_CHECKS = frozenset(
    {
        "artifact_checksum",
        "review_checksum",
        "approval_checksum",
        "approval_evidence_checksum",
        "revision_lineage",
        "audit_chain",
    }
)


def verify_backup_contract(collections: set[str], restore_checks: dict[str, bool]) -> None:
    if not REQUIRED_BACKUP_COLLECTIONS.issubset(collections):
        raise ValueError("Architecture backup is incomplete")
    if not REQUIRED_RESTORE_CHECKS.issubset(
        key for key, passed in restore_checks.items() if passed
    ):
        raise ValueError("Architecture restore integrity evidence is incomplete")
