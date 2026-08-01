from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class EvidenceReference(BaseModel):
    type: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_.-]*$")
    id: str = Field(min_length=1, max_length=240)
    hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class CognitiveRecordRequest(BaseModel):
    organization_id: uuid.UUID
    record_type: str
    record_key: str = Field(min_length=1, max_length=240)
    version: str = Field(pattern=r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
    document: dict[str, Any]
    evidence: list[EvidenceReference] = Field(min_length=1, max_length=1000)
    classification: str = Field(
        default="internal", pattern=r"^(public|internal|confidential|restricted)$"
    )
    confidence: float | None = Field(default=None, ge=0, le=1)
    parent_record_id: uuid.UUID | None = None


class CognitiveDecisionRequest(BaseModel):
    record_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: str = Field(pattern=r"^(accept|reject|defer)$")
    rationale: str = Field(min_length=1, max_length=20_000)
    decision_nonce: uuid.UUID


class CognitiveLinkRequest(BaseModel):
    source_record_id: uuid.UUID
    target_record_id: uuid.UUID
    relationship: str = Field(
        pattern=r"^(supports|derived_from|measures|affects|contradicts|depends_on)$"
    )
