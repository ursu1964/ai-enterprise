from __future__ import annotations

import re
import unicodedata
from enum import StrEnum
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_enterprise.domain.hashing import hash_json, hash_text

R4_CANONICAL_TIMESTAMP = "2026-08-05T00:00:00Z"
R4_ALLOWED_OBJECT_ID_PREFIXES: dict[str, str] = {
    "Intent": "INT",
    "Outcome": "OUT",
    "Stakeholder": "STK",
    "Capability": "CAP",
    "Process": "PRC",
    "Requirement": "REQ",
    "Rule": "RUL",
    "Entity": "ENT",
    "Integration": "INTG",
    "QualityRequirement": "QREQ",
    "Constraint": "CON",
    "Risk": "RISK",
    "TechnologyPreference": "TECH",
}


class R4Value(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceProcessingStatus(StrEnum):
    REGISTERED = "registered"
    NORMALIZATION_PENDING = "normalization_pending"
    NORMALIZED = "normalized"
    INTERPRETATION_PENDING = "interpretation_pending"
    INTERPRETED = "interpreted"
    FAILED = "failed"
    ARCHIVED = "archived"


class SegmentType(StrEnum):
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE_ROW = "table_row"
    QUOTED_STATEMENT = "quoted_statement"
    METADATA = "metadata"
    UNKNOWN = "unknown"


class R4OperationType(StrEnum):
    MANIFEST_EXTRACTION = "manifest_extraction"
    AMBIGUITY_DETECTION = "ambiguity_detection"
    ASSUMPTION_DETECTION = "assumption_detection"
    PROBABLE_CONTRADICTION_DETECTION = "probable_contradiction_detection"
    CLARIFICATION_QUESTION_GENERATION = "clarification_question_generation"
    CANDIDATE_REQUIREMENT_DRAFTING = "candidate_requirement_drafting"
    SEMANTIC_CLASSIFICATION = "semantic_classification"
    CANDIDATE_RELATIONSHIP_EXTRACTION = "candidate_relationship_extraction"


class R4OperationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    SCHEMA_FAILED = "schema_failed"
    PROVIDER_FAILED = "provider_failed"
    VALIDATION_FAILED = "validation_failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class PromptStatus(StrEnum):
    DRAFT = "draft"
    EVALUATION = "evaluation"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class SupportType(StrEnum):
    DIRECT = "direct"
    CONTEXTUAL = "contextual"
    INFERRED = "inferred"
    ASSUMED = "assumed"
    UNSUPPORTED = "unsupported"


class CandidateStatus(StrEnum):
    PENDING_VALIDATION = "pending_validation"
    VALIDATION_FAILED = "validation_failed"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    APPROVED_WITH_EDITS = "approved_with_edits"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    SUPERSEDED = "superseded"
    PROMOTED = "promoted"


class ReviewAction(StrEnum):
    APPROVE = "approve"
    APPROVE_WITH_EDITS = "approve_with_edits"
    REJECT = "reject"
    DEFER = "defer"
    MERGE_WITH_EXISTING = "merge_with_existing"
    REQUEST_CLARIFICATION = "request_clarification"
    CLASSIFY_AS_RECOMMENDATION = "classify_as_recommendation"
    CLASSIFY_AS_UNSUPPORTED = "classify_as_unsupported"


class ClarificationPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ExpectedAnswerType(StrEnum):
    FREE_TEXT = "free_text"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    DECIMAL = "decimal"
    PERCENTAGE = "percentage"
    CURRENCY = "currency"
    DURATION = "duration"
    DATE = "date"
    DATETIME = "datetime"
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    STAKEHOLDER_REFERENCE = "stakeholder_reference"
    OBJECT_REFERENCE = "object_reference"
    STRUCTURED_METRIC = "structured_metric"


class RegisteredTextSource(R4Value):
    source_id: str = Field(pattern=r"^SRC-[0-9]{3,6}$")
    project_id: str = Field(min_length=1)
    source_type: Literal["client_manifest_text"] = "client_manifest_text"
    name: str = Field(min_length=1, max_length=300)
    media_type: Literal["text/plain", "text/markdown"] = "text/plain"
    language: str = Field(default="en", min_length=2, max_length=20)
    text: str = Field(min_length=1, max_length=200_000)
    checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    captured_at: str = R4_CANONICAL_TIMESTAMP
    captured_by: str = Field(min_length=1, max_length=200)
    processing_status: SourceProcessingStatus = SourceProcessingStatus.REGISTERED

    @model_validator(mode="after")
    def validate_checksum(self) -> RegisteredTextSource:
        if self.checksum != hash_text(self.text):
            raise ValueError("registered source checksum does not match text")
        return self


class SourceSegment(R4Value):
    id: str = Field(pattern=r"^SEG-[0-9]{3,6}-[0-9]{4}$")
    source_id: str = Field(pattern=r"^SRC-[0-9]{3,6}$")
    sequence: int = Field(ge=1)
    segment_type: SegmentType
    heading_path: tuple[str, ...] = ()
    text: str = Field(min_length=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    checksum: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_segment(self) -> SourceSegment:
        if self.end_offset <= self.start_offset:
            raise ValueError("source segment end offset must be greater than start offset")
        if self.checksum != hash_text(self.text):
            raise ValueError("source segment checksum does not match text")
        return self


class NormalizedSource(R4Value):
    source_id: str = Field(pattern=r"^SRC-[0-9]{3,6}$")
    normalization_version: Literal["0.1"] = "0.1"
    language: str = Field(default="en", min_length=2, max_length=20)
    normalized_text: str = Field(min_length=1)
    character_count: int = Field(ge=1)
    segment_count: int = Field(ge=1)
    normalized_at: str = R4_CANONICAL_TIMESTAMP
    checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    segments: tuple[SourceSegment, ...]

    @model_validator(mode="after")
    def validate_normalized_source(self) -> NormalizedSource:
        if self.character_count != len(self.normalized_text):
            raise ValueError("normalized source character count is incorrect")
        if self.segment_count != len(self.segments):
            raise ValueError("normalized source segment count is incorrect")
        if self.checksum != hash_text(self.normalized_text):
            raise ValueError("normalized source checksum does not match text")
        return self


class PromptDefinition(R4Value):
    prompt_id: Literal["PROMPT-AEPM-EXTRACTOR"] = "PROMPT-AEPM-EXTRACTOR"
    version: Literal["0.1.0"] = "0.1.0"
    name: str = "AEPM Candidate Extractor"
    operation_type: Literal[R4OperationType.MANIFEST_EXTRACTION] = (
        R4OperationType.MANIFEST_EXTRACTION
    )
    system_instruction_ref: str = "prompts/manifest-extraction/system-aepm-extractor-0.1.0.md"
    task_template_ref: str = "prompts/manifest-extraction/task-aepm-extractor-0.1.0.md"
    response_schema_ref: str = "specifications/AI-EXTRACTION-RESPONSE-0.1.schema.json"
    status: PromptStatus = PromptStatus.ACTIVE
    approved_by: str = "system"


class SourceSupport(R4Value):
    source_id: str = Field(pattern=r"^SRC-[0-9]{3,6}$")
    segment_id: str = Field(pattern=r"^SEG-[0-9]{3,6}-[0-9]{4}$")
    support_type: SupportType
    quoted_fragment: str | None = Field(default=None, max_length=1000)


class CandidateObject(R4Value):
    candidate_id: str = Field(pattern=r"^CAND-OBJ-[0-9]{4}$")
    proposed_type: str = Field(min_length=1, max_length=80)
    proposed_id: str = Field(pattern=r"^[A-Z][A-Z0-9-]{2,63}$")
    name: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=4000)
    truth_status: Literal["asserted", "inferred", "assumed", "disputed"]
    approval_status: Literal["pending"] = "pending"
    confidence: float = Field(ge=0, le=1)
    source_support: tuple[SourceSupport, ...] = Field(min_length=1)
    attributes: dict[str, Any] = Field(default_factory=dict)
    interpretation_rationale: str = Field(min_length=1, max_length=2000)
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_candidate(self) -> CandidateObject:
        if all(item.support_type is SupportType.UNSUPPORTED for item in self.source_support):
            if self.truth_status != "disputed":
                raise ValueError("unsupported candidates must use disputed truth status")
        if self.approval_status != "pending":
            raise ValueError("AI candidates must default to pending approval")
        return self


class CandidateRelationship(R4Value):
    candidate_id: str = Field(pattern=r"^CAND-REL-[0-9]{4}$")
    type: str = Field(min_length=1, max_length=80)
    source_candidate_ref: str = Field(pattern=r"^CAND-OBJ-[0-9]{4}$")
    target_candidate_ref: str = Field(pattern=r"^CAND-OBJ-[0-9]{4}$")
    truth_status: Literal["asserted", "inferred", "assumed", "disputed"]
    approval_status: Literal["pending"] = "pending"
    confidence: float = Field(ge=0, le=1)
    source_support: tuple[SourceSupport, ...] = Field(min_length=1)
    interpretation_rationale: str = Field(min_length=1, max_length=2000)


class AmbiguityRecord(R4Value):
    id: str = Field(pattern=r"^AMB-[0-9]{3}$")
    category: str = Field(min_length=1, max_length=120)
    statement: str = Field(min_length=1, max_length=2000)
    source_refs: tuple[SourceSupport, ...]
    affected_candidate_refs: tuple[str, ...] = ()
    severity: Literal["error", "warning", "information", "recommendation"]
    blocking: bool
    confidence: float = Field(ge=0, le=1)
    recommended_resolution: str = Field(min_length=1, max_length=2000)


class AssumptionRecord(R4Value):
    id: str = Field(pattern=r"^ASM-[0-9]{3}$")
    statement: str = Field(min_length=1, max_length=2000)
    reason: str = Field(min_length=1, max_length=2000)
    source_refs: tuple[SourceSupport, ...]
    affected_candidate_refs: tuple[str, ...] = ()
    confidence: float = Field(ge=0, le=1)
    approval_status: Literal["pending"] = "pending"
    status: Literal["open", "resolved", "rejected"] = "open"


class ProbableContradictionRecord(R4Value):
    id: str = Field(pattern=r"^PCON-[0-9]{3}$")
    statement_a: dict[str, str]
    statement_b: dict[str, str]
    contradiction_type: str = Field(min_length=1, max_length=120)
    confidence: float = Field(ge=0, le=1)
    severity: Literal["error", "warning", "information", "recommendation"]
    blocking_recommendation: bool
    explanation: str = Field(min_length=1, max_length=2000)
    status: Literal["pending_review"] = "pending_review"


class MissingInformationRecord(R4Value):
    id: str = Field(pattern=r"^MISS-[0-9]{3}$")
    category: str = Field(min_length=1, max_length=120)
    related_candidate_refs: tuple[str, ...] = ()
    description: str = Field(min_length=1, max_length=2000)
    severity: Literal["error", "warning", "information", "recommendation"]
    blocking: bool
    source_refs: tuple[SourceSupport, ...]


class ClarificationQuestionCandidate(R4Value):
    id: str = Field(pattern=r"^QUE-[0-9]{3}$")
    origin_type: Literal["ambiguity", "assumption", "probable_contradiction", "missing_information"]
    origin_ref: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=120)
    priority: ClarificationPriority
    blocking: bool
    question: str = Field(min_length=1, max_length=1000)
    explanation: str = Field(min_length=1, max_length=2000)
    expected_answer_type: ExpectedAnswerType
    answer_options: tuple[str, ...] = ()
    affected_candidate_refs: tuple[str, ...] = ()
    source_refs: tuple[SourceSupport, ...]
    status: Literal["open", "answered", "closed"] = "open"


class ExtractionResponse(R4Value):
    operation_id: str = Field(pattern=r"^AIOP-[0-9]{4}$")
    source_summary: dict[str, Any]
    candidate_objects: tuple[CandidateObject, ...] = ()
    candidate_relationships: tuple[CandidateRelationship, ...] = ()
    ambiguities: tuple[AmbiguityRecord, ...] = ()
    assumptions: tuple[AssumptionRecord, ...] = ()
    probable_contradictions: tuple[ProbableContradictionRecord, ...] = ()
    missing_information: tuple[MissingInformationRecord, ...] = ()
    clarification_candidates: tuple[ClarificationQuestionCandidate, ...] = ()
    unsupported_requests: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_references(self) -> ExtractionResponse:
        candidates = {item.candidate_id for item in self.candidate_objects}
        for relationship in self.candidate_relationships:
            if relationship.source_candidate_ref not in candidates:
                raise ValueError("candidate relationship source candidate is missing")
            if relationship.target_candidate_ref not in candidates:
                raise ValueError("candidate relationship target candidate is missing")
        return self


class InterpretationRequest(R4Value):
    operation_id: str = Field(pattern=r"^AIOP-[0-9]{4}$")
    project_id: str = Field(min_length=1)
    operation_type: Literal[R4OperationType.MANIFEST_EXTRACTION] = (
        R4OperationType.MANIFEST_EXTRACTION
    )
    source_segments: tuple[SourceSegment, ...] = Field(min_length=1)
    prompt: PromptDefinition = Field(default_factory=PromptDefinition)
    parameters: dict[str, Any] = Field(default_factory=lambda: {"temperature": 0})
    correlation_id: str = Field(min_length=1)


class AdapterResult(R4Value):
    operation_id: str = Field(pattern=r"^AIOP-[0-9]{4}$")
    structured_output: dict[str, Any]
    raw_provider_response_ref: str
    model_metadata: dict[str, Any]
    input_token_count: int = Field(ge=0)
    output_token_count: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    finish_status: str
    provider_request_id: str
    safety_metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ModelAdapter(Protocol):
    def interpret(self, request: InterpretationRequest) -> AdapterResult: ...


class CandidateReview(R4Value):
    id: str = Field(pattern=r"^REV-[0-9]{4}$")
    candidate_id: str = Field(pattern=r"^CAND-(OBJ|REL)-[0-9]{4}$")
    reviewer_id: str = Field(min_length=1, max_length=200)
    action: ReviewAction
    original_payload_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    approved_payload_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    edits: tuple[dict[str, Any], ...] = ()
    rationale: str = Field(min_length=1, max_length=2000)
    reviewed_at: str = R4_CANONICAL_TIMESTAMP


class EvaluationMetrics(R4Value):
    schema_compliance_rate: float = Field(ge=0, le=1)
    source_attribution_accuracy: float = Field(ge=0, le=1)
    unsupported_invention_rate: float = Field(ge=0, le=1)
    object_extraction_precision: float = Field(ge=0, le=1)
    object_extraction_recall: float = Field(ge=0, le=1)
    human_acceptance_rate: float = Field(ge=0, le=1)
    blocking_ambiguity_recall: float = Field(ge=0, le=1)

    @property
    def passes_r4_thresholds(self) -> bool:
        return (
            self.schema_compliance_rate >= 0.99
            and self.source_attribution_accuracy >= 0.95
            and self.unsupported_invention_rate < 0.02
            and self.object_extraction_precision >= 0.90
            and self.object_extraction_recall >= 0.80
            and self.human_acceptance_rate >= 0.80
            and self.blocking_ambiguity_recall >= 0.85
        )


def register_text_source(
    *,
    source_id: str,
    project_id: str,
    name: str,
    text: str,
    captured_by: str,
    media_type: Literal["text/plain", "text/markdown"] = "text/plain",
    language: str = "en",
) -> RegisteredTextSource:
    if "\x00" in text:
        raise ValueError("source text contains unsupported null bytes")
    return RegisteredTextSource(
        source_id=source_id,
        project_id=project_id,
        name=name,
        media_type=media_type,
        language=language,
        text=text,
        checksum=hash_text(text),
        captured_by=captured_by,
    )


def normalize_and_segment(source: RegisteredTextSource) -> NormalizedSource:
    normalized = unicodedata.normalize("NFC", source.text).replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f]", "", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized).strip()
    segments: list[SourceSegment] = []
    headings: list[str] = []
    offset = 0
    sequence = 1
    for block in re.split(r"\n{2,}", normalized):
        for line in [item.strip() for item in block.split("\n") if item.strip()]:
            start = normalized.find(line, offset)
            end = start + len(line)
            offset = end
            segment_type = _segment_type(line)
            if segment_type is SegmentType.HEADING:
                headings = [line.lstrip("#").strip()]
            segments.append(
                SourceSegment(
                    id=f"SEG-{source.source_id.removeprefix('SRC-')}-{sequence:04d}",
                    source_id=source.source_id,
                    sequence=sequence,
                    segment_type=segment_type,
                    heading_path=tuple(headings),
                    text=line,
                    start_offset=start,
                    end_offset=end,
                    checksum=hash_text(line),
                )
            )
            sequence += 1
    if not segments:
        raise ValueError("source normalization produced no segments")
    return NormalizedSource(
        source_id=source.source_id,
        language=source.language,
        normalized_text=normalized,
        character_count=len(normalized),
        segment_count=len(segments),
        checksum=hash_text(normalized),
        segments=tuple(segments),
    )


def validate_extraction_response(
    output: dict[str, Any],
    *,
    known_segment_ids: set[str],
) -> ExtractionResponse:
    response = ExtractionResponse.model_validate(output)
    for candidate in response.candidate_objects:
        expected_prefix = R4_ALLOWED_OBJECT_ID_PREFIXES.get(candidate.proposed_type)
        if expected_prefix is None:
            raise ValueError(f"unsupported candidate object type {candidate.proposed_type}")
        if not candidate.proposed_id.startswith(f"{expected_prefix}-"):
            raise ValueError(
                f"candidate {candidate.candidate_id} proposed_id must use "
                f"{expected_prefix}- prefix"
            )
    for support in _all_support(response):
        if support.segment_id not in known_segment_ids:
            raise ValueError(f"AI output referenced unknown source segment {support.segment_id}")
    if any(item.approval_status != "pending" for item in response.candidate_objects):
        raise ValueError("AI output cannot approve candidate objects")
    if any(item.approval_status != "pending" for item in response.candidate_relationships):
        raise ValueError("AI output cannot approve candidate relationships")
    return response


def duplicate_candidate_findings(response: ExtractionResponse) -> tuple[str, ...]:
    findings: list[str] = []
    proposed_ids = [item.proposed_id for item in response.candidate_objects]
    if len(proposed_ids) != len(set(proposed_ids)):
        findings.append("duplicate proposed candidate identifiers")
    names = [
        (item.proposed_type.lower(), item.name.strip().lower())
        for item in response.candidate_objects
    ]
    if len(names) != len(set(names)):
        findings.append("duplicate candidate names within object type")
    triples = [
        (item.type, item.source_candidate_ref, item.target_candidate_ref)
        for item in response.candidate_relationships
    ]
    if len(triples) != len(set(triples)):
        findings.append("duplicate candidate relationship triples")
    return tuple(findings)


def prompt_injection_indicators(text: str) -> tuple[str, ...]:
    patterns = {
        "ignore_previous_instructions": r"ignore (all )?(previous|above) instructions",
        "reveal_system_prompt": r"(reveal|print|show).{0,40}system prompt",
        "change_output_schema": r"(change|ignore|bypass).{0,40}(schema|json schema)",
        "execute_command": r"(run|execute).{0,40}(shell|command|bash|powershell)",
    }
    lowered = text.lower()
    return tuple(name for name, pattern in patterns.items() if re.search(pattern, lowered))


class MockManifestExtractionAdapter:
    def interpret(self, request: InterpretationRequest) -> AdapterResult:
        first = request.source_segments[0]
        candidate_objects: list[dict[str, Any]] = [
            {
                "candidate_id": "CAND-OBJ-0001",
                "proposed_type": "Intent",
                "proposed_id": "INT-001",
                "name": _title_from_segment(first.text),
                "description": first.text,
                "truth_status": "asserted",
                "approval_status": "pending",
                "confidence": 0.9,
                "source_support": [_support(first)],
                "attributes": {},
                "interpretation_rationale": "The source directly states the project intent.",
                "warnings": [],
            }
        ]
        next_index = 2
        for segment in request.source_segments:
            lowered = segment.text.lower()
            if "manager" in lowered or "user" in lowered or "customer" in lowered:
                candidate_objects.append(
                    {
                        "candidate_id": f"CAND-OBJ-{next_index:04d}",
                        "proposed_type": "Stakeholder",
                        "proposed_id": f"STK-{next_index - 1:03d}",
                        "name": _stakeholder_name(segment.text),
                        "description": segment.text,
                        "truth_status": "asserted",
                        "approval_status": "pending",
                        "confidence": 0.86,
                        "source_support": [_support(segment)],
                        "attributes": {},
                        "interpretation_rationale": (
                            "The source directly names a stakeholder or user group."
                        ),
                        "warnings": [],
                    }
                )
                next_index += 1
            if "workflow" in lowered or "tracking" in lowered or "receiving" in lowered:
                candidate_objects.append(
                    {
                        "candidate_id": f"CAND-OBJ-{next_index:04d}",
                        "proposed_type": "Capability",
                        "proposed_id": f"CAP-{next_index - 1:03d}",
                        "name": _capability_name(segment.text),
                        "description": segment.text,
                        "truth_status": "asserted",
                        "approval_status": "pending",
                        "confidence": 0.84,
                        "source_support": [_support(segment)],
                        "attributes": {},
                        "interpretation_rationale": (
                            "The source directly describes a workflow or capability."
                        ),
                        "warnings": [],
                    }
                )
                next_index += 1
        output = {
            "operation_id": request.operation_id,
            "source_summary": {
                "supported_language": "en",
                "source_scope": "client manifesto",
                "interpretation_notes": list(
                    prompt_injection_indicators(" ".join(s.text for s in request.source_segments))
                ),
            },
            "candidate_objects": candidate_objects,
            "candidate_relationships": [],
            "ambiguities": [],
            "assumptions": [],
            "probable_contradictions": [],
            "missing_information": [],
            "clarification_candidates": [],
            "unsupported_requests": [],
        }
        return AdapterResult(
            operation_id=request.operation_id,
            structured_output=output,
            raw_provider_response_ref=f"mock://{request.operation_id}",
            model_metadata={"provider": "mock", "model": "deterministic-r4-mock"},
            input_token_count=sum(len(item.text.split()) for item in request.source_segments),
            output_token_count=len(hash_json(output)),
            latency_ms=0,
            finish_status="stop",
            provider_request_id=f"mock-{request.operation_id}",
        )


def _support(segment: SourceSegment) -> dict[str, str]:
    return {
        "source_id": segment.source_id,
        "segment_id": segment.id,
        "support_type": "direct",
        "quoted_fragment": segment.text[:160],
    }


def _stakeholder_name(text: str) -> str:
    match = re.search(r"([A-Z]?[a-z]+(?: [a-z]+){0,2} managers?)", text)
    if match:
        return match.group(1).title()
    return "Client Stakeholder"


def _capability_name(text: str) -> str:
    if "inventory tracking" in text.lower() and "receiving" in text.lower():
        return "Inventory Tracking and Receiving Workflows"
    words = re.findall(r"[A-Za-z0-9]+", text)[:6]
    return " ".join(words) or "Client Capability"


def _segment_type(line: str) -> SegmentType:
    if line.startswith("#"):
        return SegmentType.HEADING
    if line.startswith(("- ", "* ", "1. ")):
        return SegmentType.LIST_ITEM
    if "|" in line and line.count("|") >= 2:
        return SegmentType.TABLE_ROW
    if line.startswith(">"):
        return SegmentType.QUOTED_STATEMENT
    return SegmentType.PARAGRAPH


def _all_support(response: ExtractionResponse) -> tuple[SourceSupport, ...]:
    supports: list[SourceSupport] = []
    for collection in (
        response.candidate_objects,
        response.candidate_relationships,
        response.ambiguities,
        response.assumptions,
        response.missing_information,
        response.clarification_candidates,
    ):
        for item in collection:
            supports.extend(
                item.source_support if hasattr(item, "source_support") else item.source_refs
            )
    return tuple(supports)


def _title_from_segment(text: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", text)[:8]
    return " ".join(words) or "Candidate Project Intent"
