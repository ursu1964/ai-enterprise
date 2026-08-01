from dataclasses import dataclass
from uuid import UUID

from ai_enterprise.domain.integration.exceptions import RevisionLineageError


@dataclass(frozen=True, slots=True)
class RevisionLineage:
    parent_attempt_id: UUID
    root_attempt_id: UUID
    source_review_id: UUID
    lineage_depth: int


class RevisionLineagePolicy:
    def derive(
        self,
        *,
        parent_id: UUID,
        parent_root_id: UUID | None,
        parent_depth: int,
        source_review_id: UUID,
    ) -> RevisionLineage:
        if parent_depth < 0:
            raise RevisionLineageError("Parent lineage depth is invalid")
        return RevisionLineage(
            parent_attempt_id=parent_id,
            root_attempt_id=parent_root_id or parent_id,
            source_review_id=source_review_id,
            lineage_depth=parent_depth + 1,
        )
