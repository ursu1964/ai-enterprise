from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from ai_enterprise.domain.enterprise_kernel.enums import EnterpriseResourceType


class EnterpriseResourceRelationInput(BaseModel):
    relation_type: str = Field(min_length=1, max_length=100)
    target_resource_id: UUID
    target_version: int | None = Field(default=None, ge=1)


class EnterpriseResourceEvidenceInput(BaseModel):
    artifact_id: UUID
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_type: str = Field(min_length=1, max_length=100)


class EnterpriseResourceClaimInput(BaseModel):
    resource_kind: str = Field(min_length=1, max_length=100)
    amount: int = Field(gt=0)
    unit: str = Field(min_length=1, max_length=40)


class RegisterEnterpriseResource(BaseModel):
    organization_id: UUID
    resource_type: EnterpriseResourceType
    resource_key: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=300)
    owner_id: str = Field(min_length=1, max_length=200)
    access_policy_ids: tuple[str, ...] = Field(min_length=1)
    governance_policy_ids: tuple[str, ...] = Field(min_length=1)
    retention_policy_id: str = Field(min_length=1, max_length=200)
    provenance: dict[str, Any] = Field(min_length=1)
    semantic_relations: tuple[EnterpriseResourceRelationInput, ...] = ()
    evidence: tuple[EnterpriseResourceEvidenceInput, ...] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScheduleEnterpriseWork(BaseModel):
    organization_id: UUID
    schedule_key: str = Field(min_length=1, max_length=200)
    work_type: str = Field(min_length=1, max_length=100)
    priority: int = Field(ge=0, le=100)
    target_resource_id: UUID
    target_resource_version: int = Field(ge=1)
    dependencies: tuple[UUID, ...] = ()
    required_approval_gate_ids: tuple[str, ...] = Field(min_length=1)
    capability_requirements: tuple[str, ...] = Field(min_length=1)
    resource_claims: tuple[EnterpriseResourceClaimInput, ...] = Field(min_length=1)
    evidence: tuple[EnterpriseResourceEvidenceInput, ...] = Field(min_length=1)


class KernelActor(BaseModel):
    subject: str
    roles: frozenset[str] = frozenset()
