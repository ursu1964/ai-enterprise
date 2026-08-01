import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ._hashing import stable_hash
from .enums import TemporalStatus, TrustLevel
from .errors import KnowledgeDomainError

_KEY = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)+$")


@dataclass(frozen=True)
class KnowledgeItem:
    id: UUID
    knowledge_key: str
    version_number: int
    item_type: str
    title: str
    statement: str
    scope_type: str
    scope_id: UUID
    classification: str
    trust_level: TrustLevel
    temporal_status: TemporalStatus
    valid_from: datetime
    valid_until: datetime | None
    evidence_manifest_hash: str
    knowledge_hash: str
    promoted_from_candidate_id: UUID
    promotion_review_id: UUID | None

    def __post_init__(self) -> None:
        if not _KEY.fullmatch(self.knowledge_key) or self.version_number < 1:
            raise KnowledgeDomainError("knowledge key/version violates deterministic key policy")

    @classmethod
    def calculate_hash(cls, **values: object) -> str:
        return stable_hash(
            {key: value for key, value in values.items() if key not in {"id", "knowledge_hash"}}
        )


@dataclass(frozen=True)
class KnowledgeSupersession:
    superseded_item_id: UUID
    superseding_item_id: UUID
    reason: str
    created_at: datetime

    def __post_init__(self) -> None:
        if self.superseded_item_id == self.superseding_item_id or not self.reason.strip():
            raise KnowledgeDomainError("supersession requires distinct items and a reason")
