from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ai_enterprise.domain.knowledge._hashing import stable_hash


@dataclass(frozen=True)
class WorkflowEvidence:
    id: UUID
    workflow_id: UUID
    workflow_type: str
    agent_id: UUID | None
    crew_id: UUID | None
    assignment_id: UUID | None
    task_id: UUID | None
    duration_seconds: int
    cpu_seconds: int
    memory_peak_bytes: int
    tests_passed: int
    tests_failed: int
    review_findings: int
    correct_review_findings: int
    false_negative_findings: int
    accepted: bool
    integration_success: bool
    rollback: bool
    retry_count: int
    revision_count: int
    scope_violations: int
    architecture_violations: int
    requirements_total: int
    requirements_verified: int
    prompt_version_id: UUID
    audit_record_id: UUID
    occurred_at: datetime
    evidence_hash: str

    @classmethod
    def create(cls, **values: object) -> "WorkflowEvidence":
        evidence_hash = stable_hash(values)
        return cls(evidence_hash=evidence_hash, **values)  # type: ignore[arg-type]

    def verify(self) -> bool:
        values = {key: value for key, value in self.__dict__.items() if key != "evidence_hash"}
        return self.evidence_hash == stable_hash(values)


class EvidenceInvariantError(ValueError):
    pass


def validate_evidence(evidence: WorkflowEvidence) -> None:
    counts = (
        evidence.duration_seconds,
        evidence.cpu_seconds,
        evidence.memory_peak_bytes,
        evidence.tests_passed,
        evidence.tests_failed,
        evidence.review_findings,
        evidence.correct_review_findings,
        evidence.false_negative_findings,
        evidence.retry_count,
        evidence.revision_count,
        evidence.scope_violations,
        evidence.architecture_violations,
        evidence.requirements_total,
        evidence.requirements_verified,
    )
    if any(value < 0 for value in counts):
        raise EvidenceInvariantError("observable counts cannot be negative")
    if evidence.correct_review_findings > evidence.review_findings:
        raise EvidenceInvariantError("correct findings cannot exceed all findings")
    if evidence.requirements_verified > evidence.requirements_total:
        raise EvidenceInvariantError("verified requirements cannot exceed total requirements")
    if not evidence.verify():
        raise EvidenceInvariantError("immutable evidence hash mismatch")


@dataclass(frozen=True)
class CompleteEvidenceWindow:
    records: tuple[WorkflowEvidence, ...]
    expected_workflow_ids: frozenset[UUID]
    window_hash: str

    @classmethod
    def build(
        cls,
        records: tuple[WorkflowEvidence, ...],
        *,
        expected_workflow_ids: frozenset[UUID],
    ) -> "CompleteEvidenceWindow":
        workflows = [record.workflow_id for record in records]
        identities = [record.id for record in records]
        if len(workflows) != len(set(workflows)) or len(identities) != len(set(identities)):
            raise EvidenceInvariantError("duplicate or replayed workflow evidence")
        if set(workflows) != set(expected_workflow_ids):
            raise EvidenceInvariantError("evidence window is incomplete or unexpected")
        for record in records:
            validate_evidence(record)
        digest = stable_hash(
            {
                "expected": sorted(map(str, expected_workflow_ids)),
                "records": sorted((str(record.id), record.evidence_hash) for record in records),
            }
        )
        return cls(records, expected_workflow_ids, digest)
