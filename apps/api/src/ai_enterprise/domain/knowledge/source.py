from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .enums import TrustLevel
from .errors import KnowledgeDomainError


@dataclass(frozen=True)
class KnowledgeSource:
    id: UUID
    source_type: str
    source_id: UUID
    source_hash: str
    organization_id: UUID
    project_id: UUID | None
    classification: str
    trust_level: TrustLevel
    occurred_at: datetime
    registered_at: datetime

    def __post_init__(self) -> None:
        if len(self.source_hash) != 64 or any(
            c not in "0123456789abcdef" for c in self.source_hash
        ):
            raise KnowledgeDomainError("source_hash must be a lowercase SHA-256 digest")

    @property
    def idempotency_key(self) -> tuple[str, UUID, str]:
        return self.source_type, self.source_id, self.source_hash


class SourceRegistry:
    """In-memory domain registry semantics; persistence adapters enforce the same unique key."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, UUID, str], KnowledgeSource] = {}

    def register(self, source: KnowledgeSource) -> KnowledgeSource:
        existing = self._by_key.get(source.idempotency_key)
        if existing is not None and existing != source:
            raise KnowledgeDomainError("source identity collision")
        self._by_key[source.idempotency_key] = source
        return existing or source
