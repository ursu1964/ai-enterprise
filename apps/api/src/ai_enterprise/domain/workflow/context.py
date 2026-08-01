import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ai_enterprise.domain.hashing import hash_json
from ai_enterprise.domain.workflow.enums import WorkflowState


class WorkflowContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    workflow_id: uuid.UUID
    project_id: uuid.UUID
    current_state: WorkflowState
    correlation_id: uuid.UUID
    actor_id: str
    permissions: tuple[str, ...] = ()
    artifact_ids: dict[str, uuid.UUID] = Field(default_factory=dict)
    approval_ids: dict[str, uuid.UUID] = Field(default_factory=dict)
    run_ids: dict[str, uuid.UUID] = Field(default_factory=dict)
    execution_id: uuid.UUID | None = None
    review_id: uuid.UUID | None = None
    integration_attempt_id: uuid.UUID | None = None
    commit_id: str | None = None
    audit_ids: tuple[uuid.UUID, ...] = ()
    cancellation_requested: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    def evolved(self, **updates: Any) -> "WorkflowContext":
        return self.model_copy(update=updates)

    def content_hash(self) -> str:
        return hash_json(self.model_dump(mode="json"))
