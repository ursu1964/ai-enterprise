from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BlueprintCreateRequest(BaseModel):
    organization_id: uuid.UUID
    blueprint_key: str = Field(min_length=3, max_length=200)
    version: int = Field(default=1, gt=0)
    title: str = Field(min_length=3, max_length=200)
    kind: str = Field(min_length=3, max_length=80)
    source_project_id: uuid.UUID
    source_phase: str = Field(min_length=2, max_length=80)
    source_artifact_id: uuid.UUID | None = None
    supersedes_id: uuid.UUID | None = None
    pattern: dict[str, Any]
    evidence: dict[str, Any]
    economic_proof: dict[str, Any]
    recommended_use: str = Field(min_length=3)


class BlueprintTransitionRequest(BaseModel):
    lifecycle: str
    rationale: str = Field(min_length=3)
    evidence: dict[str, Any] = Field(default_factory=dict)


class BlueprintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    blueprint_key: str
    version: int
    title: str
    kind: str
    lifecycle: str
    source_project_id: uuid.UUID
    source_phase: str
    source_artifact_id: uuid.UUID | None
    supersedes_id: uuid.UUID | None
    pattern: dict[str, Any]
    evidence: dict[str, Any]
    economic_proof: dict[str, Any]
    recommended_use: str
    reuse_count: int
    created_by: str
    created_at: datetime
    updated_at: datetime


class BlueprintDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    blueprint_id: uuid.UUID
    previous_lifecycle: str
    lifecycle: str
    reviewer: str
    rationale: str
    evidence: dict[str, Any]
    created_at: datetime
