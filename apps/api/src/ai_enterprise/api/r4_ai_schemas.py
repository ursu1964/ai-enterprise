from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class RegisterTextSourceRequest(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=200_000)
    media_type: Literal["text/plain", "text/markdown"] = "text/plain"
    language: str = Field(default="en", min_length=2, max_length=20)


class SourceResponse(BaseModel):
    project_id: uuid.UUID
    source_id: str
    processing_status: str
    checksum: str
    prompt_injection_indicators: list[str] = []


class NormalizationResponse(BaseModel):
    project_id: uuid.UUID
    source_id: str
    normalization_id: uuid.UUID
    checksum: str
    segment_count: int
    segments: list[dict[str, Any]]


class InterpretationRunRequest(BaseModel):
    source_ids: list[str] = Field(min_length=1, max_length=20)
    operation_type: Literal["manifest_extraction"] = "manifest_extraction"
    requested_object_types: list[str] = Field(default_factory=list, max_length=30)
    prompt_version: Literal["0.1.0"] = "0.1.0"


class InterpretationRunResponse(BaseModel):
    project_id: uuid.UUID
    operation_id: str
    status: str
    candidate_object_count: int
    candidate_relationship_count: int
    ambiguity_count: int
    assumption_count: int
    probable_contradiction_count: int
    clarification_question_count: int
    usage: dict[str, Any]


class CandidateReviewRequest(BaseModel):
    action: Literal[
        "approve",
        "approve_with_edits",
        "reject",
        "defer",
        "merge_with_existing",
        "request_clarification",
        "classify_as_recommendation",
        "classify_as_unsupported",
    ]
    edits: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    rationale: str = Field(min_length=1, max_length=2000)


class CandidatePromotionResponse(BaseModel):
    project_id: uuid.UUID
    candidate_id: str
    status: str
    canonical_object_id: str | None = None
    canonical_relationship_id: str | None = None
    promotion_hash: str


class ClarificationAnswerRequest(BaseModel):
    answer: Any
    answered_by: str | None = Field(default=None, max_length=200)
