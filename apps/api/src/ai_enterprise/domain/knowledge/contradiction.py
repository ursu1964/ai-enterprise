from dataclasses import dataclass, replace
from uuid import UUID

from .enums import ContradictionStatus, TemporalStatus
from .errors import KnowledgeDomainError
from .item import KnowledgeItem, KnowledgeSupersession


@dataclass(frozen=True)
class KnowledgeContradiction:
    id: UUID
    first_item_id: UUID
    second_item_id: UUID
    contradiction_type: str
    status: ContradictionStatus
    evidence: tuple[dict[str, object], ...]

    def __post_init__(self) -> None:
        if self.first_item_id == self.second_item_id:
            raise KnowledgeDomainError("a knowledge item cannot contradict itself")


@dataclass(frozen=True)
class ContradictionResolution:
    contradiction: KnowledgeContradiction
    first_item: KnowledgeItem
    second_item: KnowledgeItem
    supersession: KnowledgeSupersession | None = None


def detect_exact_key_conflict(
    first: KnowledgeItem, second: KnowledgeItem, *, contradiction_id: UUID
) -> KnowledgeContradiction | None:
    if first.knowledge_key != second.knowledge_key or first.statement == second.statement:
        return None
    return KnowledgeContradiction(
        contradiction_id,
        first.id,
        second.id,
        "same_key_conflicting_statement",
        ContradictionStatus.DETECTED,
        ({"first_hash": first.knowledge_hash, "second_hash": second.knowledge_hash},),
    )


def mark_disputed(item: KnowledgeItem) -> KnowledgeItem:
    return replace(item, temporal_status=TemporalStatus.DISPUTED)


def resolve_by_supersession(
    contradiction: KnowledgeContradiction,
    *,
    first: KnowledgeItem,
    second: KnowledgeItem,
    supersession: KnowledgeSupersession,
) -> ContradictionResolution:
    pair = {contradiction.first_item_id, contradiction.second_item_id}
    if {supersession.superseded_item_id, supersession.superseding_item_id} != pair:
        raise KnowledgeDomainError("supersession does not resolve the contradiction pair")
    old = first if first.id == supersession.superseded_item_id else second
    new = second if old is first else first
    return ContradictionResolution(
        replace(contradiction, status=ContradictionStatus.RESOLVED),
        replace(old, temporal_status=TemporalStatus.SUPERSEDED),
        new,
        supersession,
    )
