import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FormationRequest(BaseModel):
    project_id: uuid.UUID
    idea: str = Field(min_length=20, max_length=20_000)
    expected_outcome: str | None = Field(default=None, max_length=5_000)
    target_users: list[str] = Field(default_factory=list, max_length=50)
    constraints: list[str] = Field(default_factory=list, max_length=100)
    known_systems: list[str] = Field(default_factory=list, max_length=100)
    deadline: str | None = Field(default=None, max_length=200)
    budget_signal: str | None = Field(default=None, max_length=200)
    correction_attempt: int = Field(default=0, ge=0, le=3)


class FormationArtifactResponse(BaseModel):
    artifact_id: uuid.UUID
    artifact_type: str
    content_hash: str
    title: str
    human_summary: str


class FormationResponse(BaseModel):
    project_id: uuid.UUID
    status: str
    correction_attempt: int
    missing_information: list[str]
    next_action: str
    generated_at: datetime
    artifacts: list[FormationArtifactResponse]
    traceability: dict[str, Any]


class MockFactoryProjectResponse(BaseModel):
    project_id: uuid.UUID
    workflow_id: uuid.UUID
    name: str
    project_type: str
    repository_path: str
    project_record: str
    formation_pack: str
    workflow: str
    next_action: str
    dashboard_url: str


class MockFactoryPreviewProjectResponse(BaseModel):
    name: str
    project_type: str
    repository_path: str
    default_branch: str
    action: str
    ready: bool
    missing_information: list[str]
    operator_action: str
    existing_project_id: uuid.UUID | None = None
    dashboard_url: str | None = None


class MockFactoryLaunchIssueResponse(BaseModel):
    name: str
    project_type: str
    repository_path: str
    status: str
    issues: list[str]
    operator_action: str


class MockFactoryPreviewResponse(BaseModel):
    status: str
    human_summary: str
    ready_count: int
    reused_count: int
    blocked_count: int
    recommended_first_project: MockFactoryPreviewProjectResponse | None
    projects: list[MockFactoryPreviewProjectResponse]


class MockFactoryStartResponse(BaseModel):
    status: str
    human_summary: str
    started_count: int
    reused_count: int
    formation_pack_count: int
    workflow_count: int
    created_count: int = 0
    blocked_count: int = 0
    failed_count: int = 0
    workflows_started: list[uuid.UUID] = Field(default_factory=list)
    workflows_waiting: list[uuid.UUID] = Field(default_factory=list)
    created: list[MockFactoryProjectResponse] = Field(default_factory=list)
    reused: list[MockFactoryProjectResponse] = Field(default_factory=list)
    blocked: list[MockFactoryLaunchIssueResponse] = Field(default_factory=list)
    failed: list[MockFactoryLaunchIssueResponse] = Field(default_factory=list)
    recommended_first_project: MockFactoryProjectResponse | None = None
    next_action: str
    projects: list[MockFactoryProjectResponse]
