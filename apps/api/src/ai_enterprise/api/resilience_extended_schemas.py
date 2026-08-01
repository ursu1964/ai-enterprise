from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GovernanceRecordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(min_length=1, max_length=40)
    policy_version: int = Field(gt=0)
    payload: dict[str, Any]
    provider_evidence_hash: str | None = Field(default=None, min_length=32, max_length=128)
