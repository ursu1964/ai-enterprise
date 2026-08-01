from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from ai_enterprise.application.enterprise_kernel.dto import (
    EnterpriseResourceClaimInput,
    EnterpriseResourceEvidenceInput,
    EnterpriseResourceRelationInput,
)


class EnterpriseResourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    resource_type: str
    resource_key: str
    display_name: str
    version: int
    state: str
    owner_id: str
    access_policy_ids: tuple[str, ...]
    governance_policy_ids: tuple[str, ...]
    retention_policy_id: str
    provenance: dict[str, Any]
    semantic_relations: tuple[EnterpriseResourceRelationInput, ...]
    evidence: tuple[EnterpriseResourceEvidenceInput, ...]
    metadata: dict[str, Any]
    registered_by: str
    registered_at: datetime
    content_hash: str


class EnterpriseScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    resource_claims: tuple[EnterpriseResourceClaimInput, ...]
    evidence: tuple[EnterpriseResourceEvidenceInput, ...]
    state: str
    scheduled_by: str
    scheduled_at: datetime
    content_hash: str


class EnterpriseModuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    module_key: str
    display_name: str
    capability_ids: tuple[str, ...]
    owned_resource_ids: tuple[UUID, ...]
    integration_resource_ids: tuple[UUID, ...]
    governance_policy_ids: tuple[str, ...]
    evidence: tuple[EnterpriseResourceEvidenceInput, ...]
    state: str
    registered_by: str
    registered_at: datetime
    content_hash: str


class OrganizationalThreadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    thread_key: str
    root_resource_id: UUID
    resource_sequence: tuple[UUID, ...]
    schedule_sequence: tuple[UUID, ...]
    current_state: str
    owner_id: str
    evidence: tuple[EnterpriseResourceEvidenceInput, ...]
    opened_by: str
    opened_at: datetime
    content_hash: str


class OperatingMaturitySnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    snapshot_key: str
    maturity_level: int
    covered_resource_types: tuple[str, ...]
    module_count: int
    active_thread_count: int
    evidence: tuple[EnterpriseResourceEvidenceInput, ...]
    recorded_by: str
    recorded_at: datetime
    content_hash: str
