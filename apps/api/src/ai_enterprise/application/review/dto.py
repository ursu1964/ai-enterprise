from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ReviewerFindingInput(BaseModel):
    rule_id: str = Field(min_length=1, max_length=128)
    category: Literal[
        "correctness",
        "security",
        "architecture",
        "quality",
        "testing",
        "integrity",
        "scope",
    ]
    severity: Literal[
        "info",
        "low",
        "medium",
        "high",
        "critical",
    ]
    title: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1, max_length=10_000)
    blocking: bool = False
    file_path: str | None = None
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)
    evidence: dict[str, Any] | None = None


class ReviewerAgentOutput(BaseModel):
    schema_version: Literal[1]
    summary: str = Field(min_length=1, max_length=20_000)
    findings: list[ReviewerFindingInput] = Field(
        default_factory=list,
        max_length=200,
    )


class CreatePatchReviewRequest(BaseModel):
    idempotency_key: str = Field(
        min_length=16,
        max_length=128,
        pattern=r"^[a-zA-Z0-9._:-]+$",
    )


class PatchReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    work_package_id: uuid.UUID
    execution_run_id: uuid.UUID
    status: str
    base_commit: str
    expected_patch_sha256: str
    actual_patch_sha256: str | None
    decision_summary: str | None
    review_report_artifact_id: uuid.UUID | None
    failure_code: str | None
    failure_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class PatchReviewFindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patch_review_run_id: uuid.UUID
    rule_id: str
    category: str
    severity: str
    status: str
    title: str
    description: str
    file_path: str | None
    line_start: int | None
    line_end: int | None
    evidence: dict[str, Any] | None
    blocking: bool
    created_at: datetime


class PatchReviewCheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patch_review_run_id: uuid.UUID
    sequence: int
    check_type: str
    name: str
    command: list[str] | None
    status: str
    exit_code: int | None
    duration_ms: int | None
    stdout_artifact_id: uuid.UUID | None
    stderr_artifact_id: uuid.UUID | None
