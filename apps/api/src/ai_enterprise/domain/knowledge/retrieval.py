from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import IntEnum
from typing import Any, Protocol
from uuid import UUID

from ai_enterprise.domain.hashing import hash_json


class Classification(IntEnum):
    public = 0
    internal = 1
    confidential = 2
    restricted = 3


TRUST_SCORE = {"unverified": 0, "observed": 4, "reviewed": 7, "verified": 10}
TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9_.:/-]*")


class RetrievalCandidate(Protocol):
    id: UUID
    knowledge_key: str
    version_number: int
    item_type: str
    title: str
    statement: str
    scope_type: str
    scope_id: UUID
    classification: str
    trust_level: str
    temporal_status: str
    evidence: tuple[dict[str, Any], ...]
    valid_from: datetime
    content_hash: str


@dataclass(frozen=True)
class KnowledgeRetrievalRequest:
    runtime_session_id: UUID
    actor_id: UUID
    assignment_id: UUID
    query_text: str
    requested_scope_types: tuple[str, ...]
    requested_item_types: tuple[str, ...]
    maximum_results: int
    maximum_tokens: int
    include_stale: bool = False
    include_disputed: bool = False

    def __post_init__(self) -> None:
        if not self.query_text.strip():
            raise ValueError("RET-001 QUERY-REQUIRED")
        if self.maximum_results < 1 or self.maximum_results > 100:
            raise ValueError("RET-002 INVALID-RESULT-LIMIT")
        if self.maximum_tokens < 1:
            raise ValueError("RET-003 INVALID-TOKEN-BUDGET")

    @property
    def query_hash(self) -> str:
        return hash_json(
            {
                "query_text": self.query_text,
                "requested_scope_types": sorted(self.requested_scope_types),
                "requested_item_types": sorted(self.requested_item_types),
                "maximum_results": self.maximum_results,
                "maximum_tokens": self.maximum_tokens,
                "include_stale": self.include_stale,
                "include_disputed": self.include_disputed,
            }
        )


@dataclass(frozen=True)
class RetrievalPolicy:
    version: str
    maximum_classification: str
    allowed_source_types: tuple[str, ...]
    cross_project_access: bool = False
    semantic_weight: Decimal = Decimal("20")


@dataclass(frozen=True)
class AuthorizedScope:
    scope_type: str
    scope_id: UUID


@dataclass(frozen=True)
class IndexVersion:
    version: str
    item_set_hash: str
    embedding_model_version: str
    tokenizer_version: str
    lexical_analyzer_version: str
    policy_version: str
    created_at: datetime

    @classmethod
    def build(
        cls,
        *,
        items: tuple[RetrievalCandidate, ...],
        embedding_model_version: str,
        policy_version: str,
        created_at: datetime,
        tokenizer_version: str = "ascii-word-v1",
        lexical_analyzer_version: str = "overlap-v1",
    ) -> IndexVersion:
        item_set_hash = hash_json(
            {
                "items": sorted(
                    (str(item.id), item.content_hash, item.version_number) for item in items
                )
            }
        )
        version = f"knowledge-index-{item_set_hash[:16]}"
        return cls(
            version,
            item_set_hash,
            embedding_model_version,
            tokenizer_version,
            lexical_analyzer_version,
            policy_version,
            created_at.astimezone(UTC),
        )


@dataclass(frozen=True)
class EmbeddingRecord:
    """Immutable derived-index provenance; the vector is never authoritative knowledge."""

    knowledge_item_id: UUID
    knowledge_item_hash: str
    model_deployment: str
    embedding_policy_version: str
    vector_hash: str
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        knowledge_item_id: UUID,
        knowledge_item_hash: str,
        model_deployment: str,
        embedding_policy_version: str,
        vector: tuple[float, ...],
        created_at: datetime,
    ) -> EmbeddingRecord:
        return cls(
            knowledge_item_id,
            knowledge_item_hash,
            model_deployment,
            embedding_policy_version,
            hash_json({"vector": vector}),
            created_at.astimezone(UTC),
        )
@dataclass(frozen=True)
class ScoreBreakdown:
    scope_match: Decimal
    item_type_match: Decimal
    lexical_relevance: Decimal
    semantic_relevance: Decimal
    trust_level: Decimal
    freshness: Decimal
    evidence_quality: Decimal

    @property
    def total(self) -> Decimal:
        return sum(
            (
                self.scope_match,
                self.item_type_match,
                self.lexical_relevance,
                self.semantic_relevance,
                self.trust_level,
                self.freshness,
                self.evidence_quality,
            ),
            Decimal(),
        ).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

    def document(self) -> dict[str, str]:
        return {
            "scope_match": str(self.scope_match),
            "item_type_match": str(self.item_type_match),
            "lexical_relevance": str(self.lexical_relevance),
            "semantic_relevance": str(self.semantic_relevance),
            "trust_level": str(self.trust_level),
            "freshness": str(self.freshness),
            "evidence_quality": str(self.evidence_quality),
        }


@dataclass(frozen=True)
class RankedKnowledge:
    item: RetrievalCandidate
    score: ScoreBreakdown


@dataclass(frozen=True)
class RetrievedKnowledge:
    retrieval_session_id: UUID
    knowledge_item_id: UUID
    knowledge_key: str
    version_number: int
    title: str
    statement: str
    scope_type: str
    scope_id: UUID
    classification: str
    trust_level: str
    temporal_status: str
    evidence: tuple[dict[str, Any], ...]
    rank: int
    score: Decimal
    score_breakdown: dict[str, str]
    knowledge_hash: str

    @property
    def token_count(self) -> int:
        return max(1, (len(self.title) + len(self.statement) + 4) // 4)


@dataclass(frozen=True)
class RetrievalManifestItem:
    knowledge_item_id: UUID
    knowledge_hash: str
    rank: int
    score: Decimal
    trust_level: str
    temporal_status: str
    evidence_manifest_hash: str


@dataclass(frozen=True)
class RetrievalManifest:
    retrieval_session_id: UUID
    query_hash: str
    policy_version: str
    index_version: str
    items: tuple[RetrievalManifestItem, ...]
    manifest_hash: str

    @classmethod
    def create(
        cls,
        retrieval_session_id: UUID,
        query_hash: str,
        policy_version: str,
        index_version: str,
        results: tuple[RetrievedKnowledge, ...],
    ) -> RetrievalManifest:
        items = tuple(
            RetrievalManifestItem(
                item.knowledge_item_id,
                item.knowledge_hash,
                item.rank,
                item.score,
                item.trust_level,
                item.temporal_status,
                hash_json({"evidence": item.evidence}),
            )
            for item in results
        )
        document = {
            "retrieval_session_id": str(retrieval_session_id),
            "query_hash": query_hash,
            "policy_version": policy_version,
            "index_version": index_version,
            "items": [
                {
                    "knowledge_item_id": str(item.knowledge_item_id),
                    "knowledge_hash": item.knowledge_hash,
                    "rank": item.rank,
                    "score": str(item.score),
                    "trust_level": item.trust_level,
                    "temporal_status": item.temporal_status,
                    "evidence_manifest_hash": item.evidence_manifest_hash,
                }
                for item in items
            ],
        }
        return cls(
            retrieval_session_id,
            query_hash,
            policy_version,
            index_version,
            items,
            hash_json(document),
        )


class SemanticSimilarity(Protocol):
    version: str

    def similarities(
        self, query: str, candidates: tuple[RetrievalCandidate, ...]
    ) -> dict[UUID, Decimal]: ...


class HybridKnowledgeRanker:
    def __init__(self, semantic: SemanticSimilarity) -> None:
        self.semantic = semantic

    def rank(
        self,
        query_text: str,
        candidates: tuple[RetrievalCandidate, ...],
        requested_scopes: tuple[str, ...],
        requested_item_types: tuple[str, ...],
    ) -> tuple[RankedKnowledge, ...]:
        semantic = self.semantic.similarities(query_text, candidates)
        query_tokens = set(TOKEN_PATTERN.findall(query_text.lower()))
        ranked = []
        for item in candidates:
            item_tokens = set(TOKEN_PATTERN.findall(f"{item.title} {item.statement}".lower()))
            lexical = Decimal(0)
            if query_tokens:
                lexical = (
                    Decimal(20)
                    * Decimal(len(query_tokens & item_tokens))
                    / Decimal(len(query_tokens))
                )
            evidence_quality = min(Decimal(5), Decimal(len(item.evidence) * 2))
            freshness = Decimal(5 if item.temporal_status == "current" else 2)
            score = ScoreBreakdown(
                Decimal(30 if item.scope_type in requested_scopes else 0),
                Decimal(10 if item.item_type in requested_item_types else 0),
                lexical.quantize(Decimal("0.001")),
                (semantic.get(item.id, Decimal(0)) * Decimal(20)).quantize(Decimal("0.001")),
                Decimal(TRUST_SCORE.get(item.trust_level, 0)),
                freshness,
                evidence_quality,
            )
            ranked.append(RankedKnowledge(item, score))
        return tuple(
            sorted(
                ranked,
                key=lambda entry: (
                    -entry.score.total,
                    -TRUST_SCORE.get(entry.item.trust_level, 0),
                    -entry.item.valid_from.timestamp(),
                    entry.item.knowledge_key,
                    -entry.item.version_number,
                ),
            )
        )


@dataclass(frozen=True)
class FreshnessPolicy:
    version: str
    default_validity_days: dict[str, int | None]
    stale_retrieval_allowed: bool
    require_revalidation_on_source_change: bool

    def status_for(self, item_type: str, valid_from: datetime, now: datetime) -> str:
        days = self.default_validity_days.get(item_type)
        if days is None:
            return "current"
        return (
            "stale"
            if now.astimezone(UTC) > valid_from.astimezone(UTC) + timedelta(days=days)
            else "current"
        )


@dataclass(frozen=True)
class KnowledgeQualityReport:
    evidence_completeness: str
    source_trust: str
    scope_precision: str
    temporal_validity: str
    contradiction_status: str
    review_independence: str
    reproducibility: str
    findings: tuple[dict[str, Any], ...] = ()


def quality_report(
    item: RetrievalCandidate, *, reviewer_independent: bool
) -> KnowledgeQualityReport:
    findings: list[dict[str, Any]] = []
    if not item.evidence:
        findings.append({"code": "KQ-001", "message": "evidence required"})
    if item.temporal_status != "current":
        findings.append({"code": "KQ-002", "message": f"temporal status: {item.temporal_status}"})
    return KnowledgeQualityReport(
        "complete" if item.evidence else "missing",
        item.trust_level,
        "explicit" if item.scope_type and item.scope_id else "ambiguous",
        item.temporal_status,
        "clear" if item.temporal_status != "disputed" else "unresolved",
        "independent" if reviewer_independent else "not-independent",
        "reproducible"
        if all("source_hash" in evidence for evidence in item.evidence)
        else "partial",
        tuple(findings),
    )


def requires_revalidation(bound_source_hash: str, current_source_hash: str) -> bool:
    """Source changes qualify knowledge; historical records are retained."""
    return bound_source_hash != current_source_hash
