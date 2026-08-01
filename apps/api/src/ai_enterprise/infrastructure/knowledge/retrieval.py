from __future__ import annotations

import hashlib
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from ai_enterprise.domain.knowledge.retrieval import (
    AuthorizedScope,
    Classification,
    HybridKnowledgeRanker,
    IndexVersion,
    KnowledgeRetrievalRequest,
    RetrievalCandidate,
    RetrievalManifest,
    RetrievalPolicy,
    RetrievedKnowledge,
)


class RetrievalDenied(PermissionError):
    pass


class RetrievalAuthorizer(Protocol):
    def authorize(
        self, request: KnowledgeRetrievalRequest, policy: RetrievalPolicy
    ) -> tuple[AuthorizedScope, ...]: ...


class RetrievalAuditSink(Protocol):
    def record(self, event_type: str, document: dict[str, object]) -> None: ...


@dataclass(frozen=True)
class RetrievalAuthorizationFacts:
    runtime_session_id: UUID
    session_active: bool
    session_actor_id: UUID
    assignment_id: UUID
    assignment_active: bool
    tool_authorized: bool
    allowed_source_types: tuple[str, ...]
    accessible_scopes: tuple[AuthorizedScope, ...]
    maximum_classification: str
    remaining_query_budget: int
    assignment_project_id: UUID | None = None


class GovernedRetrievalAuthorizer:
    """Fail-closed authorization snapshot resolved from relational runtime state."""

    def __init__(self, facts: RetrievalAuthorizationFacts) -> None:
        self.facts = facts

    def authorize(
        self, request: KnowledgeRetrievalRequest, policy: RetrievalPolicy
    ) -> tuple[AuthorizedScope, ...]:
        facts = self.facts
        if not facts.session_active or facts.runtime_session_id != request.runtime_session_id:
            raise RetrievalDenied("RET-A01 SESSION-INACTIVE-OR-MISMATCH")
        if facts.session_actor_id != request.actor_id:
            raise RetrievalDenied("RET-A02 ACTOR-MISMATCH")
        if not facts.assignment_active or facts.assignment_id != request.assignment_id:
            raise RetrievalDenied("RET-A03 ASSIGNMENT-INACTIVE-OR-MISMATCH")
        if not facts.tool_authorized:
            raise RetrievalDenied("RET-A04 KNOWLEDGE-TOOL-NOT-AUTHORIZED")
        if not set(policy.allowed_source_types).issubset(facts.allowed_source_types):
            raise RetrievalDenied("RET-A05 SOURCE-TYPE-DENIED")
        if (
            Classification[policy.maximum_classification]
            > Classification[facts.maximum_classification]
        ):
            raise RetrievalDenied("RET-A06 CLASSIFICATION-DENIED")
        if facts.remaining_query_budget < 1:
            raise RetrievalDenied("RET-A07 QUERY-BUDGET-EXHAUSTED")
        requested_types = set(request.requested_scope_types)
        scopes = tuple(
            scope for scope in facts.accessible_scopes if scope.scope_type in requested_types
        )
        if not policy.cross_project_access and facts.assignment_project_id is not None:
            scopes = tuple(
                scope
                for scope in scopes
                if scope.scope_type != "project" or scope.scope_id == facts.assignment_project_id
            )
        return scopes


class InMemoryKnowledgeIndex:
    """Relationally filtered index; semantic providers never see unauthorized items."""

    def __init__(self, items: tuple[RetrievalCandidate, ...], version: IndexVersion) -> None:
        self._items = items
        self.version = version

    def filtered_candidates(
        self,
        *,
        scopes: tuple[AuthorizedScope, ...],
        item_types: tuple[str, ...],
        maximum_classification: str,
        include_stale: bool,
        include_disputed: bool,
    ) -> tuple[RetrievalCandidate, ...]:
        allowed = {(scope.scope_type, scope.scope_id) for scope in scopes}
        maximum = Classification[maximum_classification]
        return tuple(
            item
            for item in self._items
            if (item.scope_type, item.scope_id) in allowed
            and item.item_type in item_types
            and Classification[item.classification] <= maximum
            and item.temporal_status not in {"withdrawn", "expired", "superseded"}
            and (include_stale or item.temporal_status != "stale")
            and (include_disputed or item.temporal_status != "disputed")
        )


class EmbeddingProvider(Protocol):
    version: str
    local: bool

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]: ...


class LocalHashEmbeddingProvider:
    """Dependency-free local embedding useful for deterministic/offline deployments."""

    version = "local-hash-embedding-v1"
    local = True

    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        return tuple(self._embed(text) for text in texts)

    def _embed(self, text: str) -> tuple[float, ...]:
        vector = [0.0] * self.dimensions
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode()).digest()
            vector[int.from_bytes(digest[:2]) % self.dimensions] += 1.0 if digest[2] & 1 else -1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return tuple(value / norm for value in vector)


class ProviderNeutralSemanticSimilarity:
    def __init__(self, provider: EmbeddingProvider) -> None:
        self.provider = provider
        self.version = provider.version

    def similarities(
        self, query: str, candidates: tuple[RetrievalCandidate, ...]
    ) -> dict[UUID, Decimal]:
        if not candidates:
            return {}
        restricted = any(
            Classification[item.classification] >= Classification.confidential
            for item in candidates
        )
        if restricted and not self.provider.local:
            raise RetrievalDenied("RET-011 RESTRICTED-EXTERNAL-EMBEDDING-DENIED")
        vectors = self.provider.embed(
            (query,) + tuple(f"{item.title} {item.statement}" for item in candidates)
        )
        query_vector = vectors[0]
        return {
            item.id: Decimal(
                str(max(0.0, sum(a * b for a, b in zip(query_vector, vector, strict=True))))
            )
            for item, vector in zip(candidates, vectors[1:], strict=True)
        }


@dataclass(frozen=True)
class RetrievalOutcome:
    retrieval_session_id: UUID
    results: tuple[RetrievedKnowledge, ...]
    manifest: RetrievalManifest
    status: str


class KnowledgeRetrievalService:
    def __init__(
        self,
        *,
        authorizer: RetrievalAuthorizer,
        index: InMemoryKnowledgeIndex,
        ranker: HybridKnowledgeRanker,
        audit: RetrievalAuditSink | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.authorizer = authorizer
        self.index = index
        self.ranker = ranker
        self.audit = audit
        self.clock = clock

    def retrieve(
        self, request: KnowledgeRetrievalRequest, policy: RetrievalPolicy
    ) -> RetrievalOutcome:
        started = self.clock()
        # This call must remain before index access and embedding/ranking.
        scopes = self.authorizer.authorize(request, policy)
        if not scopes:
            raise RetrievalDenied("RET-010 NO-AUTHORIZED-SCOPE")
        candidates = self.index.filtered_candidates(
            scopes=scopes,
            item_types=request.requested_item_types,
            maximum_classification=policy.maximum_classification,
            include_stale=request.include_stale,
            include_disputed=request.include_disputed,
        )
        ranked = self.ranker.rank(
            request.query_text,
            candidates,
            request.requested_scope_types,
            request.requested_item_types,
        )
        retrieval_session_id = uuid4()
        selected: list[RetrievedKnowledge] = []
        token_total = 0
        for candidate in ranked:
            item = candidate.item
            token_count = max(1, (len(item.title) + len(item.statement) + 4) // 4)
            if (
                len(selected) >= request.maximum_results
                or token_total + token_count > request.maximum_tokens
            ):
                continue
            token_total += token_count
            selected.append(
                RetrievedKnowledge(
                    retrieval_session_id,
                    item.id,
                    item.knowledge_key,
                    item.version_number,
                    item.title,
                    item.statement,
                    item.scope_type,
                    item.scope_id,
                    item.classification,
                    item.trust_level,
                    item.temporal_status,
                    item.evidence,
                    len(selected) + 1,
                    candidate.score.total,
                    candidate.score.document(),
                    item.content_hash,
                )
            )
        results = tuple(selected)
        manifest = RetrievalManifest.create(
            retrieval_session_id,
            request.query_hash,
            policy.version,
            self.index.version.version,
            results,
        )
        if self.audit is not None:
            elapsed_ms = int((self.clock() - started).total_seconds() * 1000)
            self.audit.record(
                "knowledge.retrieval.completed",
                {
                    "retrieval_session_id": str(retrieval_session_id),
                    "actor_id": str(request.actor_id),
                    "assignment_id": str(request.assignment_id),
                    "query_hash": request.query_hash,
                    "index_version": self.index.version.version,
                    "manifest_hash": manifest.manifest_hash,
                    "result_count": len(results),
                    "zero_results": not results,
                    "elapsed_ms": elapsed_ms,
                },
            )
        return RetrievalOutcome(retrieval_session_id, results, manifest, "completed")
