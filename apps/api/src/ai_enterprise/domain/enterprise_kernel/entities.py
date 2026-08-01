from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from .enums import EnterpriseResourceState, EnterpriseResourceType, EnterpriseScheduleState


@dataclass(frozen=True, slots=True)
class EnterpriseResourceRelation:
    relation_type: str
    target_resource_id: UUID
    target_version: int | None = None


@dataclass(frozen=True, slots=True)
class EnterpriseResourceEvidence:
    artifact_id: UUID
    content_hash: str
    evidence_type: str


@dataclass(frozen=True, slots=True)
class EnterpriseResource:
    id: UUID
    organization_id: UUID
    resource_type: EnterpriseResourceType
    resource_key: str
    display_name: str
    version: int
    state: EnterpriseResourceState
    owner_id: str
    access_policy_ids: tuple[str, ...]
    governance_policy_ids: tuple[str, ...]
    retention_policy_id: str
    provenance: dict[str, Any]
    semantic_relations: tuple[EnterpriseResourceRelation, ...]
    evidence: tuple[EnterpriseResourceEvidence, ...]
    metadata: dict[str, Any]
    registered_by: str
    registered_at: datetime
    content_hash: str


@dataclass(frozen=True, slots=True)
class EnterpriseResourceAuditRecord:
    event_type: str
    resource_id: UUID
    actor_id: str
    occurred_at: datetime
    payload: dict[str, Any]
    payload_hash: str


@dataclass(frozen=True, slots=True)
class EnterpriseResourceClaim:
    resource_kind: str
    amount: int
    unit: str


@dataclass(frozen=True, slots=True)
class EnterpriseSchedule:
    id: UUID
    organization_id: UUID
    schedule_key: str
    work_type: str
    priority: int
    target_resource_id: UUID
    target_resource_version: int
    dependencies: tuple[UUID, ...]
    required_approval_gate_ids: tuple[str, ...]
    capability_requirements: tuple[str, ...]
    resource_claims: tuple[EnterpriseResourceClaim, ...]
    evidence: tuple[EnterpriseResourceEvidence, ...]
    state: EnterpriseScheduleState
    scheduled_by: str
    scheduled_at: datetime
    content_hash: str
