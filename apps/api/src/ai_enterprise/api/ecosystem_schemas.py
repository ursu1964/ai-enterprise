from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EntityRequest(BaseModel):
    organization_id: uuid.UUID
    entity_type: str
    entity_key: str = Field(min_length=1, max_length=240)
    display_name: str = Field(min_length=1, max_length=240)
    document: dict[str, Any]
    classification: str = Field(pattern=r"^(public|internal|confidential|restricted)$")


class AssetRequest(BaseModel):
    organization_id: uuid.UUID
    entity_id: uuid.UUID
    asset_type: str
    asset_key: str = Field(min_length=1, max_length=240)
    version: str = Field(pattern=r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
    document: dict[str, Any]
    evidence: list[dict[str, str]] = Field(min_length=1, max_length=1000)
    parent_asset_id: uuid.UUID | None = None


class ApprovalRequest(BaseModel):
    asset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    decision: str = Field(pattern=r"^(approve|reject)$")
    rationale: str = Field(min_length=1, max_length=20_000)
    expires_at: datetime | None = None


class InvocationRequest(BaseModel):
    organization_id: uuid.UUID
    connector_asset_id: uuid.UUID
    contract_asset_id: uuid.UUID
    direction: str = Field(pattern=r"^(inbound|outbound)$")
    operation: str = Field(min_length=1, max_length=160)
    identity_reference: str = Field(min_length=1, max_length=240)
    request_nonce: uuid.UUID
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    policy_version: str = Field(min_length=1, max_length=80)
    status: str = Field(pattern=r"^(authorized|denied|completed|failed)$")
    evidence_document: dict[str, Any]


class EdgeRequest(BaseModel):
    source_entity_id: uuid.UUID
    target_entity_id: uuid.UUID
    relationship: str = Field(
        pattern=r"^(consumes|provides|certifies|regulates|supplies|collaborates|federates_with|trusts)$"
    )
    document: dict[str, Any]
