from dataclasses import dataclass
from uuid import UUID

from ai_enterprise.domain.hashing import hash_json

from .models import RequirementsReviewDecision


class RequirementsRevisionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RevisionFeedback:
    source_artifact_id: UUID
    source_artifact_hash: str
    summary: str
    findings: tuple[dict[str, object], ...]
    feedback_hash: str


class RevisionFeedbackPolicy:
    def create(
        self,
        *,
        artifact_id: UUID,
        artifact_hash: str,
        decision: RequirementsReviewDecision,
    ) -> RevisionFeedback:
        if decision.decision != "changes_requested":
            raise RequirementsRevisionError("Only changes-requested decisions create revisions")
        findings = tuple(item.model_dump(mode="json") for item in decision.findings)
        payload = {
            "source_artifact_id": str(artifact_id),
            "source_artifact_hash": artifact_hash,
            "summary": decision.summary,
            "findings": findings,
        }
        return RevisionFeedback(
            artifact_id,
            artifact_hash,
            decision.summary,
            findings,
            hash_json(payload),
        )
