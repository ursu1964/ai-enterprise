from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SpecificationCreateRequest(BaseModel):
    organization_id: uuid.UUID
    project_id: uuid.UUID
    specification_key: str = Field(pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$")
    specification_type: str = Field(min_length=1, max_length=60)
    version: str = Field(pattern=r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
    document: dict[str, Any]
    requirements_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    architecture_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    work_package_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_specification_id: uuid.UUID | None = None


class SpecificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    specification_key: str
    specification_type: str
    version: str
    specification_document: dict[str, Any]
    specification_hash: str
    requirements_hash: str
    architecture_hash: str
    work_package_hash: str
    parent_specification_id: uuid.UUID | None
    created_by: str
    created_at: datetime


class DecisionRequest(BaseModel):
    bound_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: str = Field(min_length=1, max_length=30)
    rationale: str = Field(min_length=1, max_length=20_000)
    expires_at: datetime | None = None


class ValidationRequest(BaseModel):
    validator_version: str = Field(min_length=1, max_length=80)
    findings: list[dict[str, Any]] = Field(max_length=1000)


class GenerationRequest(BaseModel):
    generator_key: str = Field(min_length=1, max_length=120)
    generator_version: str = Field(min_length=1, max_length=80)
    parameters: dict[str, Any] = {}


class EvidenceNodeRequest(BaseModel):
    organization_id: uuid.UUID
    project_id: uuid.UUID
    node_type: str = Field(min_length=1, max_length=60)
    reference_id: uuid.UUID
    reference_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    classification: str = Field(pattern=r"^(public|internal|confidential|restricted)$")
    document: dict[str, Any]


class EvidenceEdgeRequest(BaseModel):
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    relationship: str = Field(min_length=1, max_length=80)
    document: dict[str, Any]


class DriftObservation(BaseModel):
    category: str
    severity: str = "high"
    expected_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    actual_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    promotion_blocking: bool = True
    evidence: dict[str, Any] = {}


class DriftRunRequest(BaseModel):
    repository_commit_hash: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    runtime_deployment_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    detector_version: str = Field(min_length=1, max_length=80)
    observations: list[DriftObservation] = Field(max_length=1000)
