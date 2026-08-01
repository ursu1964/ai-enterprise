from dataclasses import dataclass
from enum import StrEnum


class RecoveryAction(StrEnum):
    RECONSTRUCT_ARTIFACT = "reconstruct_artifact"
    COMPLETE_RUN = "complete_run"
    RETRY = "retry"
    NO_ACTION = "no_action"
    INVESTIGATE = "investigate"
    INTEGRITY_INCIDENT = "integrity_incident"


@dataclass(frozen=True, slots=True)
class ArchitectureRunSnapshot:
    run_id: str
    project_id: str
    status: str
    latest_attempt_status: str | None
    artifact_present: bool
    successful_attempt_count: int = 0
    artifact_checksum_valid: bool = True
    lease_expired: bool = False


@dataclass(frozen=True, slots=True)
class ArchitectureInspection:
    snapshot: ArchitectureRunSnapshot
    recovery_action: RecoveryAction
    recovery_eligible: bool
    reason: str


@dataclass(frozen=True, slots=True)
class IntegrityFinding:
    code: str
    severity: str
    aggregate_id: str
    description: str


@dataclass(frozen=True, slots=True)
class ArchitectureIntegrityRecord:
    run_id: str
    run_status: str
    attempt_statuses: tuple[str, ...]
    artifact_ids: tuple[str, ...]
    artifact_checksum_valid: bool = True
    review_checksum_valid: bool = True
    approval_checksum_valid: bool = True
    approval_evidence_checksum_valid: bool = True
    audit_chain_valid: bool = True
    revision_lineage_valid: bool = True
