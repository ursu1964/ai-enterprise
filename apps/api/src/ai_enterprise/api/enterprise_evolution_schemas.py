from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class EvidenceReference(BaseModel):
    type: str = Field(pattern=r"^(performance|engineering|evolution)$")
    id: uuid.UUID
    hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ImprovementRequest(BaseModel):
    organization_id: uuid.UUID
    improvement_key: str = Field(pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$")
    category: str
    origin: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=240)
    expected_benefit: str = Field(min_length=1, max_length=20_000)
    risk_document: dict[str, Any]
    dependencies: list[str] = Field(default_factory=list, max_length=500)
    evidence: list[EvidenceReference] = Field(min_length=1, max_length=1000)


class ArtifactRequest(BaseModel):
    organization_id: uuid.UUID
    improvement_id: uuid.UUID | None = None
    artifact_type: str
    artifact_key: str = Field(min_length=1, max_length=240)
    version: str = Field(pattern=r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
    document: dict[str, Any]
    evidence: list[EvidenceReference] = Field(min_length=1, max_length=1000)
    parent_artifact_id: uuid.UUID | None = None


class EvolutionDecisionRequest(BaseModel):
    organization_id: uuid.UUID
    target_type: str = Field(pattern=r"^(improvement|artifact)$")
    target_id: uuid.UUID
    target_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: str = Field(pattern=r"^(approve|reject)$")
    rationale: str = Field(min_length=1, max_length=20_000)
    expires_at: datetime | None = None


class TransitionRequest(BaseModel):
    to_state: Literal[
        "analyzed",
        "simulated",
        "reviewed",
        "approved",
        "implemented",
        "measured",
        "accepted",
        "archived",
    ]
    evidence_artifact_ids: list[uuid.UUID] = Field(max_length=1000)
    decision_id: uuid.UUID | None = None
