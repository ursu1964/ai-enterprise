from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ai_enterprise.domain.resilience.enums import Capability, CriticalityTier


class RecoveryObjectiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: CriticalityTier
    rto_seconds: int = Field(gt=0)
    rpo_seconds: int = Field(ge=0)
    mtpd_seconds: int = Field(gt=0)
    work_recovery_time_seconds: int = Field(ge=0)
    primary_owner: str = Field(min_length=1)
    deputy_owner: str = Field(min_length=1)


class CapabilityDecisionResponse(BaseModel):
    capability: Capability
    allowed: bool
    reason: str
    activation_ids: tuple[UUID, ...]
    evaluated_at: datetime


class ReadinessResponse(BaseModel):
    service_id: UUID
    ready: bool
    failures: tuple[str, ...]
