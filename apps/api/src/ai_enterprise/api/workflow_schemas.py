import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ai_enterprise.domain.workflow.enums import WorkflowState


class StartWorkflowRequest(BaseModel):
    actor_id: str = Field(default="local-user", min_length=2, max_length=200)


class CancelWorkflowRequest(BaseModel):
    actor_id: str = Field(default="local-user", min_length=2, max_length=200)
    reason: str = Field(min_length=3, max_length=2000)


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    workflow_version: str
    state: WorkflowState
    current_step: str | None
    context_version: int
    correlation_id: uuid.UUID
    optimistic_version: int
    cancellation_requested_at: datetime | None
    failure_code: str | None
    failure_message: str | None
    recommended_operator_action: str | None
    started_at: datetime
    completed_at: datetime | None


class WorkflowTransitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sequence: int
    previous_state: WorkflowState
    current_state: WorkflowState
    step: str | None
    actor_type: str
    actor_id: str
    reason: str
    workflow_version: str
    correlation_id: uuid.UUID
    occurred_at: datetime
