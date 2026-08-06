from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class R10RoleWorkspaceRequest(BaseModel):
    manifest_ref: str = Field(min_length=1, max_length=200)
    role: str = Field(
        pattern=(
            r"^(client|business_analyst|product_owner|domain_expert|architect|developer|"
            r"tester|designer|devops_engineer|operator|administrator|ai_agent|auditor)$"
        )
    )
    components: list[str] = Field(default_factory=list)


class R10ManifestStudioSessionRequest(BaseModel):
    manifest_ref: str = Field(min_length=1, max_length=200)
    validation_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    approval_workflow_ref: str = Field(min_length=1, max_length=200)


class R10VisualModelRequest(BaseModel):
    manifest_object_ref: str = Field(min_length=1, max_length=240)
    object_kind: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    nodes: list[str]
    edges: list[str] = Field(default_factory=list)


class R10SearchIndexSnapshotRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    targets: list[str]
    result_refs: list[str]


class R10AiInteractionProposalRequest(BaseModel):
    ai_session_ref: str = Field(min_length=1, max_length=200)
    manifest_ref: str = Field(min_length=1, max_length=200)
    recommendation: str = Field(min_length=1, max_length=1000)
    impact_analysis_ref: str = Field(min_length=1, max_length=200)
    validation_ref: str = Field(min_length=1, max_length=200)


class R10ApprovalWorkspaceRequest(BaseModel):
    proposal_ref: str = Field(min_length=1, max_length=200)
    affected_object_refs: list[str]
    risk_ref: str = Field(min_length=1, max_length=200)
    simulation_ref: str = Field(min_length=1, max_length=200)
    reviewer_comments: list[str] = Field(default_factory=list)


class R10ExplainabilityViewRequest(BaseModel):
    object_ref: str = Field(min_length=1, max_length=240)
    answers: dict[str, str]
    traceability_refs: list[str]


class R10ExperienceProfileRequest(BaseModel):
    user_ref: str = Field(min_length=1, max_length=200)
    role: str = Field(
        pattern=(
            r"^(client|business_analyst|product_owner|domain_expert|architect|developer|"
            r"tester|designer|devops_engineer|operator|administrator|ai_agent|auditor)$"
        )
    )
    device: str = Field(
        pattern=r"^(desktop|tablet|mobile|browser|command_line|api|ai_conversation)$"
    )
    personalization: dict[str, str] = Field(default_factory=dict)


class R10TraceabilityViewRequest(BaseModel):
    object_ref: str = Field(min_length=1, max_length=240)
    lineage_refs: list[str]


class R10CollaborationThreadRequest(BaseModel):
    manifest_object_ref: str = Field(min_length=1, max_length=240)
    comments: list[str] = Field(default_factory=list)
    review_refs: list[str] = Field(default_factory=list)
    assignment_refs: list[str] = Field(default_factory=list)
    notification_refs: list[str] = Field(default_factory=list)


class R10NotificationRuleRequest(BaseModel):
    event_type: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    role: str = Field(
        pattern=(
            r"^(client|business_analyst|product_owner|domain_expert|architect|developer|"
            r"tester|designer|devops_engineer|operator|administrator|ai_agent|auditor)$"
        )
    )
    object_ref: str = Field(min_length=1, max_length=240)
    delivery_channels: list[str]


class R10RoleDashboardRequest(BaseModel):
    role: str = Field(
        pattern=(
            r"^(client|business_analyst|product_owner|domain_expert|architect|developer|"
            r"tester|designer|devops_engineer|operator|administrator|ai_agent|auditor)$"
        )
    )
    widgets: list[str]
    source_refs: list[str]


class R10DocumentationPanelRequest(BaseModel):
    object_ref: str = Field(min_length=1, max_length=240)
    source_refs: list[str]


class R10WorkspaceSurfaceRequest(BaseModel):
    surface_type: str = Field(pattern=r"^(generation|runtime|governance)$")
    role: str = Field(
        pattern=(
            r"^(client|business_analyst|product_owner|domain_expert|architect|developer|"
            r"tester|designer|devops_engineer|operator|administrator|ai_agent|auditor)$"
        )
    )
    visible_object_refs: list[str]
    source_system_refs: list[str]


class R10ExperienceApiContractRequest(BaseModel):
    platform_api_refs: list[str]


class R10RecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    record_type: str
    record_id: str
    role: str | None
    object_ref: str | None
    status: str
    record_document: dict[str, Any]
    record_hash: str


class R10ExperienceDashboardResponse(BaseModel):
    project_id: uuid.UUID
    workspace_count: int
    manifest_studio_session_count: int
    visual_model_count: int
    search_snapshot_count: int
    ai_proposal_count: int
    pending_ai_proposal_count: int
    approval_workspace_count: int
    explainability_view_count: int
    experience_profile_count: int
    traceability_view_count: int
    collaboration_thread_count: int
    notification_rule_count: int
    role_dashboard_count: int
    navigation_map_count: int
    documentation_panel_count: int
    workspace_surface_count: int
    ai_interaction_policy_count: int
    experience_api_contract_count: int
