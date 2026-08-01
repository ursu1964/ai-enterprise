import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ._hashing import stable_hash
from .enums import CandidateStatus
from .evidence import EvidenceBinding
from .source import KnowledgeSource

ALLOWED_CANDIDATE_TYPES = frozenset(
    {
        "fact",
        "lesson",
        "procedure",
        "constraint",
        "pattern",
        "anti_pattern",
        "risk",
        "decision_rationale",
    }
)
FINDING_CODES = {
    "SOURCE_NOT_FOUND": "KNOW-001",
    "SOURCE_HASH_MISMATCH": "KNOW-002",
    "EVIDENCE_LOCATOR_INVALID": "KNOW-003",
    "SCOPE_INVALID": "KNOW-004",
    "CLASSIFICATION_DOWNGRADE": "KNOW-005",
    "DUPLICATE_CANDIDATE": "KNOW-006",
    "UNSUPPORTED_CLAIM": "KNOW-007",
    "SECRET_DETECTED": "KNOW-008",
    "SOURCE_NOT_ELIGIBLE": "KNOW-009",
}
CLASSIFICATION_RANK = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
_SECRET = re.compile(
    r"(?i)(?:api[_-]?key|password|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_./+\-=]{8,}"
)


class ExtractedKnowledgeCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    candidate_type: str
    title: str = Field(min_length=5, max_length=200)
    statement: str = Field(min_length=10, max_length=4000)
    scope_type: str
    scope_reference: str
    evidence_locators: list[dict[str, Any]] = Field(min_length=1)
    confidence_band: str
    suggested_valid_until: str | None = None


@dataclass(frozen=True)
class KnowledgeCandidate:
    id: UUID
    candidate_type: str
    title: str
    statement: str
    scope_type: str
    scope_id: UUID
    classification: str
    confidence_band: str
    evidence_bindings: tuple[EvidenceBinding, ...]
    status: CandidateStatus
    candidate_hash: str
    proposed_by_actor_type: str
    proposed_by_actor_id: UUID

    @classmethod
    def create(cls, **values: Any) -> "KnowledgeCandidate":
        values.pop("candidate_hash", None)
        digest = stable_hash(
            {key: value for key, value in values.items() if key not in {"id", "status"}}
        )
        return cls(candidate_hash=digest, **values)


@dataclass(frozen=True)
class ValidationFinding:
    code: str
    message: str


@dataclass(frozen=True)
class CandidateValidationResult:
    candidate: KnowledgeCandidate
    findings: tuple[ValidationFinding, ...]

    @property
    def valid(self) -> bool:
        return not self.findings


class CandidateValidator:
    def validate(
        self,
        candidate: KnowledgeCandidate,
        *,
        sources: Mapping[UUID, KnowledgeSource],
        expected_source_hashes: Mapping[UUID, str],
        eligible_source_types: frozenset[str],
        scope_exists: Callable[[str, UUID], bool],
        locator_resolves: Callable[[KnowledgeSource, Mapping[str, Any]], bool],
        existing_hashes: frozenset[str] = frozenset(),
    ) -> CandidateValidationResult:
        findings: list[ValidationFinding] = []
        self._basic_findings(candidate, findings, scope_exists, existing_hashes)
        for binding in candidate.evidence_bindings:
            source = sources.get(binding.knowledge_source_id)
            if source is None:
                self._add(findings, "SOURCE_NOT_FOUND", "bound source is not registered")
                continue
            if expected_source_hashes.get(source.id) != source.source_hash:
                self._add(findings, "SOURCE_HASH_MISMATCH", "bound source hash does not match")
            if source.source_type not in eligible_source_types:
                self._add(findings, "SOURCE_NOT_ELIGIBLE", "source type is not eligible")
            if CLASSIFICATION_RANK.get(candidate.classification, -1) < CLASSIFICATION_RANK.get(
                source.classification, 99
            ):
                self._add(
                    findings, "CLASSIFICATION_DOWNGRADE", "candidate reduces source classification"
                )
            if not locator_resolves(source, binding.evidence_locator):
                self._add(findings, "EVIDENCE_LOCATOR_INVALID", "evidence locator does not resolve")
        unique = {(finding.code, finding.message): finding for finding in findings}
        ordered = tuple(sorted(unique.values(), key=lambda finding: finding.code))
        status = (
            CandidateStatus.AWAITING_REVIEW if not ordered else CandidateStatus.VALIDATION_FAILED
        )
        return CandidateValidationResult(replace(candidate, status=status), ordered)

    @staticmethod
    def _add(findings: list[ValidationFinding], name: str, message: str) -> None:
        findings.append(ValidationFinding(FINDING_CODES[name], message))

    def _basic_findings(
        self,
        candidate: KnowledgeCandidate,
        findings: list[ValidationFinding],
        scope_exists: Callable[[str, UUID], bool],
        existing_hashes: frozenset[str],
    ) -> None:
        if (
            candidate.candidate_type not in ALLOWED_CANDIDATE_TYPES
            or not candidate.evidence_bindings
        ):
            self._add(findings, "UNSUPPORTED_CLAIM", "claim type or evidence is unsupported")
        if not 10 <= len(candidate.statement) <= 4000:
            self._add(findings, "UNSUPPORTED_CLAIM", "statement length is outside policy")
        if not scope_exists(candidate.scope_type, candidate.scope_id):
            self._add(findings, "SCOPE_INVALID", "candidate scope does not exist")
        if candidate.candidate_hash in existing_hashes:
            self._add(findings, "DUPLICATE_CANDIDATE", "candidate hash already exists")
        if _SECRET.search(candidate.title) or _SECRET.search(candidate.statement):
            self._add(findings, "SECRET_DETECTED", "candidate contains secret-like material")
