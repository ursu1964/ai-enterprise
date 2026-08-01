from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AuditActorResponse(BaseModel):
    type: str
    id: str | None = None


class AuditEventResponse(BaseModel):
    id: UUID
    project_id: UUID
    aggregate_type: str
    aggregate_id: UUID
    event_type: str
    occurred_at: datetime
    actor: AuditActorResponse
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    sequence: int
    payload: dict[str, Any]


class AuditTimelineResponse(BaseModel):
    project_id: UUID
    events: list[AuditEventResponse]
    next_cursor: str | None = None
    has_more: bool


class ProjectAuditSummaryResponse(BaseModel):
    project_id: UUID
    project_name: str
    manifest_sha256: str
    latest_execution_status: str | None
    latest_review_status: str | None
    candidate_patch_accepted: bool
    event_count: int
    artifact_count: int
    approval_count: int


class ProvenanceNodeResponse(BaseModel):
    id: UUID
    node_type: str
    label: str
    sha256: str | None = None
    created_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProvenanceEdgeResponse(BaseModel):
    source_id: UUID
    target_id: UUID
    relationship: str


class ProjectProvenanceResponse(BaseModel):
    project_id: UUID
    nodes: list[ProvenanceNodeResponse]
    edges: list[ProvenanceEdgeResponse]


class IntegrityResponse(BaseModel):
    project_id: UUID
    integrity_status: str
    event_count: int
    failures: list[dict[str, Any]] = Field(default_factory=list)
