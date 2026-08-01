from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ai_enterprise.domain.hashing import hash_json, hash_text

from .models import CLASSIFICATION_ORDER


@dataclass(frozen=True)
class ContextSource:
    source_type: str
    source_id: UUID
    content: str
    classification: str
    selection_reason: str
    approved: bool = False
    untrusted: bool = False
    retrieval_manifest_hash: str | None = None
    evidence_manifest_hash: str | None = None
    temporal_status: str | None = None
    trust_level: str | None = None

    @property
    def content_hash(self) -> str:
        return hash_text(self.content)

    @property
    def token_count(self) -> int:
        return max(1, (len(self.content) + 3) // 4)


@dataclass(frozen=True)
class ContextAssemblyPolicy:
    version: str
    allowed_source_types: tuple[str, ...]
    required_source_types: tuple[str, ...]
    denied_source_types: tuple[str, ...]
    maximum_total_tokens: int
    maximum_source_tokens: int
    maximum_repository_files: int
    require_approved_artifacts: bool = True
    allow_untrusted_repository_text: bool = False
    preserve_source_boundaries: bool = True
    maximum_classification: str = "internal"


@dataclass(frozen=True)
class ContextManifest:
    runtime_session_id: UUID
    policy_version: str
    sources: tuple[dict[str, Any], ...]
    total_tokens: int
    maximum_classification: str
    manifest_hash: str
    prompt_sections: tuple[dict[str, str], ...]
    retrieval_manifest_hashes: tuple[str, ...] = ()


class ContextPolicyViolation(ValueError):
    pass


class ContextAssembler:
    def assemble(
        self,
        runtime_session_id: UUID,
        policy: ContextAssemblyPolicy,
        sources: tuple[ContextSource, ...],
    ) -> ContextManifest:
        source_types = {source.source_type for source in sources}
        missing = sorted(set(policy.required_source_types) - source_types)
        if missing:
            raise ContextPolicyViolation(f"CTX-001 REQUIRED-SOURCE-MISSING: {','.join(missing)}")
        accepted: list[ContextSource] = []
        repository_files = 0
        for source in sorted(
            sources, key=lambda item: (item.source_type, str(item.source_id), item.content_hash)
        ):
            if (
                source.source_type in policy.denied_source_types
                or source.source_type not in policy.allowed_source_types
            ):
                raise ContextPolicyViolation("CTX-002 SOURCE-TYPE-DENIED")
            if CLASSIFICATION_ORDER.get(source.classification, 99) > CLASSIFICATION_ORDER.get(
                policy.maximum_classification, -1
            ):
                raise ContextPolicyViolation("CTX-003 CLASSIFICATION-VIOLATION")
            if (
                source.source_type.startswith("approved-")
                and policy.require_approved_artifacts
                and not source.approved
            ):
                raise ContextPolicyViolation("CTX-004 ARTIFACT-NOT-APPROVED")
            if source.source_type == "repository-file":
                repository_files += 1
                if not policy.allow_untrusted_repository_text or not source.untrusted:
                    raise ContextPolicyViolation("CTX-005 REPOSITORY-TEXT-MUST-BE-UNTRUSTED")
            if source.source_type == "retrieved-knowledge" and (
                source.retrieval_manifest_hash is None or source.evidence_manifest_hash is None
            ):
                raise ContextPolicyViolation("CTX-009 KNOWLEDGE-PROVENANCE-REQUIRED")
            if source.token_count > policy.maximum_source_tokens:
                raise ContextPolicyViolation("CTX-006 SOURCE-TOKEN-BUDGET-EXCEEDED")
            accepted.append(source)
        if repository_files > policy.maximum_repository_files:
            raise ContextPolicyViolation("CTX-007 REPOSITORY-FILE-LIMIT-EXCEEDED")
        total = sum(source.token_count for source in accepted)
        if total > policy.maximum_total_tokens:
            raise ContextPolicyViolation("CTX-008 TOTAL-TOKEN-BUDGET-EXCEEDED")
        records = tuple(
            {
                "source_type": source.source_type,
                "source_id": str(source.source_id),
                "content_hash": source.content_hash,
                "classification": source.classification,
                "token_count": source.token_count,
                "selection_reason": source.selection_reason,
                "trust_boundary": "untrusted-data" if source.untrusted else "trusted-input",
                "retrieval_manifest_hash": source.retrieval_manifest_hash,
                "evidence_manifest_hash": source.evidence_manifest_hash,
                "temporal_status": source.temporal_status,
                "trust_level": source.trust_level,
            }
            for source in accepted
        )
        prompt_sections = tuple(
            {
                "boundary": self._boundary(source),
                "content": source.content,
            }
            for source in accepted
        )
        document: dict[str, Any] = {
            "runtime_session_id": str(runtime_session_id),
            "policy_version": policy.version,
            "sources": records,
            "total_tokens": total,
            "retrieval_manifest_hashes": sorted(
                {
                    source.retrieval_manifest_hash
                    for source in accepted
                    if source.retrieval_manifest_hash is not None
                }
            ),
        }
        return ContextManifest(
            runtime_session_id=runtime_session_id,
            policy_version=policy.version,
            sources=records,
            total_tokens=total,
            maximum_classification=max(
                (source.classification for source in accepted),
                key=lambda value: CLASSIFICATION_ORDER[value],
                default="public",
            ),
            manifest_hash=hash_json(document),
            prompt_sections=prompt_sections,
            retrieval_manifest_hashes=tuple(document["retrieval_manifest_hashes"]),
        )

    @staticmethod
    def _boundary(source: ContextSource) -> str:
        if source.source_type == "retrieved-knowledge":
            if source.temporal_status != "current":
                return "STALE OR QUALIFIED KNOWLEDGE"
            if source.trust_level == "verified":
                return "VERIFIED ORGANIZATIONAL KNOWLEDGE"
            return "CURATED LESSONS"
        if source.untrusted:
            return "UNTRUSTED REPOSITORY CONTENT"
        return "AUTHORITATIVE INPUTS"
