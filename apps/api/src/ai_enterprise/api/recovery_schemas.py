import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RecoveryIncidentRequest(BaseModel):
    severity: str = Field(pattern=r"^(low|medium|high|critical)$")
    summary: str = Field(min_length=3, max_length=500)
    details: str = Field(min_length=3, max_length=20_000)
    affected_environment: str = Field(min_length=1, max_length=120)
    detected_at: datetime
    external_reference: str | None = Field(default=None, max_length=200)


class RecoveryIncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    integration_attempt_id: uuid.UUID
    rollback_record_id: uuid.UUID
    reported_by: str
    severity: str
    summary: str
    details: str
    affected_environment: str
    detected_at: datetime
    external_reference: str | None
    created_at: datetime


class RecoveryAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    incident_id: uuid.UUID
    rollback_record_id: uuid.UUID
    status: str
    recommended_strategy: str
    risk_level: str
    expected_remote_head_sha: str
    integration_commit_is_ancestor: bool
    direct_revert_possible: bool
    database_coordination_required: bool
    external_coordination_required: bool
    required_test_commands: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    assessment_policy_version: str
    assessment_binding_sha256: str
    assessed_by: str
    assessed_at: datetime


class RollbackApprovalRequest(BaseModel):
    decision: str = Field(pattern=r"^approved$")
    reason: str = Field(min_length=3, max_length=5000)


class RollbackApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    recovery_assessment_id: uuid.UUID
    rollback_record_id: uuid.UUID
    target_branch: str
    recovery_strategy: str
    expected_remote_head_sha: str
    integration_commit_sha: str
    status: str
    approver_subject: str
    approved_at: datetime
    expires_at: datetime | None


class RecoveryAttemptRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=5000)


class RecoveryAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    rollback_approval_id: uuid.UUID
    recovery_assessment_id: uuid.UUID
    rollback_record_id: uuid.UUID
    target_branch: str
    expected_remote_head_sha: str
    integration_commit_sha: str
    recovery_strategy: str
    status: str
    correlation_id: uuid.UUID
    failure_class: str | None
    failure_code: str | None
    failure_message: str | None
    created_at: datetime

