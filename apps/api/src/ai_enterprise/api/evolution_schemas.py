from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PrerequisiteAssessmentRequest(BaseModel):
    available_prerequisites: set[str]


class ShadowCommandAssessmentRequest(BaseModel):
    command_type: str
    payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    side_effecting: bool
    credential_scope: str | None = None


class ExceptionAssessmentRequest(BaseModel):
    exception_id: UUID
    policy_id: UUID
    owner_id: str
    reason: str
    scope_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    compensating_control_ids: tuple[UUID, ...]
    removal_plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    expires_at: datetime


class ConstitutionalApprovalInput(BaseModel):
    actor_id: str
    role: str
    signature_reference: str
    approved_at: datetime


class ConstitutionalAssessmentRequest(BaseModel):
    amendment_id: UUID
    change_proposal_id: UUID
    constitutional_policy_id: UUID
    proposed_by: str
    candidate_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    required_roles: tuple[str, ...]
    minimum_approval_count: int = Field(ge=2)
    cooling_off_until: datetime
    approvals: tuple[ConstitutionalApprovalInput, ...]


class EvolutionAssessmentResponse(BaseModel):
    eligible: bool
    assessment_type: str
    message: str
