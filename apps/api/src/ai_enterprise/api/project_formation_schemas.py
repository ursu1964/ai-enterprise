import uuid
from datetime import datetime
from typing import Any, Literal

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


class ClientBlueprintImportRequest(BaseModel):
    manifest: dict[str, Any] | None = None
    manifest_text: str | None = Field(default=None, min_length=2, max_length=200_000)
    interpretation_output: dict[str, Any] | None = None
    ai_operation: dict[str, Any] | None = None
    content_type: Literal["application/json", "application/yaml", "text/yaml"] = (
        "application/json"
    )
    repository_path: str | None = Field(default=None, max_length=2000)
    repository_url: str | None = Field(default=None, max_length=2000)
    default_branch: str = Field(default="main", min_length=1, max_length=200)


class ClientBlueprintReviewRequest(BaseModel):
    decision: Literal["approved", "changes_requested", "rejected"]
    reviewer_comment: str | None = Field(default=None, max_length=5000)
    corrected_manifest: dict[str, Any] | None = None
    corrected_manifest_text: str | None = Field(default=None, min_length=2, max_length=200_000)
    content_type: Literal["application/json", "application/yaml", "text/yaml"] = (
        "application/json"
    )
    interpretation_output: dict[str, Any] | None = None
    ai_operation: dict[str, Any] | None = None


class ClientBlueprintClarificationAnswerRequest(BaseModel):
    clarification_report: dict[str, Any]
    answers: list[dict[str, Any]] = Field(min_length=1, max_length=100)
    respondent_id: str | None = Field(default=None, min_length=1, max_length=200)


class ClientBlueprintArtifactResponse(BaseModel):
    artifact_id: uuid.UUID
    artifact_type: str
    media_type: str
    content_hash: str
    download_url: str | None = None


class ClientBlueprintResponse(BaseModel):
    project_id: uuid.UUID
    status: str
    review_state: str
    project_name: str
    source_manifest_sha256: str
    validation_report: dict[str, Any]
    interpretation_batch: dict[str, Any] | None
    clarification_report: dict[str, Any]
    missing_information: list[str]
    assumptions: list[str]
    canonical_model: dict[str, Any]
    canonical_object_count: int
    relationship_count: int
    artifacts: list[ClientBlueprintArtifactResponse]
    blueprint_download_url: str | None
    traceability: dict[str, Any]
    proof: dict[str, Any]
    next_action: str


class FoundryWorkspaceRequest(BaseModel):
    intake: dict[str, Any] = Field(default_factory=dict)
    workspace_path: str | None = Field(default=None, max_length=2000)
    github_repository_url: str | None = Field(default=None, max_length=2000)
    overwrite_existing: bool = False


class FoundryWorkspaceResponse(BaseModel):
    project_id: uuid.UUID
    status: str
    workspace_path: str
    github_repository_url: str | None
    created_files: list[str]
    reused_files: list[str]
    created_directories: list[str]
    missing_information: list[str]
    next_action: str
    proof: dict[str, Any]


class MockFactoryProjectResponse(BaseModel):
    project_id: uuid.UUID
    workflow_id: uuid.UUID
    name: str
    project_type: str
    repository_path: str
    result_category: str
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


class MockFactoryLaunchSummaryResponse(BaseModel):
    mode: str
    created_count: int = 0
    reused_count: int = 0
    blocked_count: int = 0
    failed_count: int = 0
    review_needed_count: int = 0
    workflows_started_count: int = 0
    workflows_waiting_count: int = 0
    recommended_first_project_id: uuid.UUID | None = None
    recommended_first_project_name: str | None = None
    recommended_first_project_url: str | None = None
    operator_action: str


class MockFactoryPreviewResponse(BaseModel):
    status: str
    human_summary: str
    launch_plan: MockFactoryLaunchSummaryResponse
    ready_count: int
    would_create_count: int = 0
    would_reuse_count: int = 0
    would_block_count: int = 0
    reused_count: int
    blocked_count: int
    recommended_first_project: MockFactoryPreviewProjectResponse | None
    would_create: list[MockFactoryPreviewProjectResponse] = Field(default_factory=list)
    would_reuse: list[MockFactoryPreviewProjectResponse] = Field(default_factory=list)
    would_block: list[MockFactoryLaunchIssueResponse] = Field(default_factory=list)
    projects: list[MockFactoryPreviewProjectResponse]


class MockFactoryStartResponse(BaseModel):
    status: str
    human_summary: str
    launch_result: MockFactoryLaunchSummaryResponse
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
