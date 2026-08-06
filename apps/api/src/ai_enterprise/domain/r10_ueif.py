from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_enterprise.domain.specification.kernel import specification_hash


class UeifValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class UeifRole(StrEnum):
    CLIENT = "client"
    BUSINESS_ANALYST = "business_analyst"
    PRODUCT_OWNER = "product_owner"
    DOMAIN_EXPERT = "domain_expert"
    ARCHITECT = "architect"
    DEVELOPER = "developer"
    TESTER = "tester"
    DESIGNER = "designer"
    DEVOPS_ENGINEER = "devops_engineer"
    OPERATOR = "operator"
    ADMINISTRATOR = "administrator"
    AI_AGENT = "ai_agent"
    AUDITOR = "auditor"


class UeifInteractionStep(StrEnum):
    OBSERVE = "observe"
    UNDERSTAND = "understand"
    MODIFY = "modify"
    VALIDATE = "validate"
    APPROVE = "approve"
    GENERATE = "generate"
    EXECUTE = "execute"
    MONITOR = "monitor"


class UeifDevice(StrEnum):
    DESKTOP = "desktop"
    TABLET = "tablet"
    MOBILE = "mobile"
    BROWSER = "browser"
    COMMAND_LINE = "command_line"
    API = "api"
    AI_CONVERSATION = "ai_conversation"


class UeifProposalStatus(StrEnum):
    PROPOSED = "proposed"
    REVIEW_REQUIRED = "review_required"


class UeifApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class UeifWorkspaceSurfaceType(StrEnum):
    GENERATION = "generation"
    RUNTIME = "runtime"
    GOVERNANCE = "governance"


class UeifExperienceClient(StrEnum):
    WEB_APPLICATION = "web_application"
    DESKTOP_CLIENT = "desktop_client"
    MOBILE_APPLICATION = "mobile_application"
    IDE_EXTENSION = "ide_extension"
    COMMAND_LINE_TOOL = "command_line_tool"
    AI_ASSISTANT = "ai_assistant"
    THIRD_PARTY_INTEGRATION = "third_party_integration"


class UeifRoleWorkspace(UeifValue):
    schema_version: Literal["ueif-role-workspace-0.1"] = "ueif-role-workspace-0.1"
    workspace_id: str = Field(pattern=r"^UEIF-WS-[0-9]{4}$")
    project_id: str = Field(min_length=1)
    manifest_ref: str = Field(min_length=1, max_length=200)
    role: UeifRole
    components: tuple[str, ...]
    lifecycle_steps: tuple[UeifInteractionStep, ...]
    owns_project_data: bool = False
    workspace_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_workspace(self) -> UeifRoleWorkspace:
        required = {
            "navigation",
            "project_view",
            "knowledge_view",
            "task_view",
            "generation_view",
            "runtime_view",
            "governance_view",
        }
        if not required.issubset(set(self.components)):
            raise ValueError("UEIF workspace requires standard workspace components")
        if tuple(sorted(set(self.components))) != self.components:
            raise ValueError("UEIF workspace components must be unique and sorted")
        sorted_lifecycle_steps = tuple(
            sorted(set(self.lifecycle_steps), key=lambda item: item.value)
        )
        if sorted_lifecycle_steps != self.lifecycle_steps:
            raise ValueError("UEIF lifecycle steps must be unique and sorted")
        if self.owns_project_data:
            raise ValueError("UEIF interfaces may not own project data")
        if self.workspace_hash != _role_workspace_hash(self):
            raise ValueError("UEIF role workspace hash does not match canonical content")
        return self


class UeifManifestStudioSession(UeifValue):
    schema_version: Literal["ueif-manifest-studio-session-0.1"] = (
        "ueif-manifest-studio-session-0.1"
    )
    session_id: str = Field(pattern=r"^UEIF-STUDIO-[0-9]{4}$")
    manifest_ref: str = Field(min_length=1, max_length=200)
    capabilities: tuple[str, ...]
    validation_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    approval_workflow_ref: str = Field(min_length=1, max_length=200)
    direct_manifest_write: bool = False
    session_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_session(self) -> UeifManifestStudioSession:
        required = {
            "structured_editing",
            "natural_language_assistance",
            "semantic_validation",
            "auto_completion",
            "dependency_visualization",
            "version_comparison",
            "collaboration",
            "approval_workflow",
        }
        if not required.issubset(set(self.capabilities)):
            raise ValueError("UEIF Manifest Studio requires all authoring capabilities")
        if tuple(sorted(set(self.capabilities))) != self.capabilities:
            raise ValueError("UEIF Manifest Studio capabilities must be unique and sorted")
        if self.direct_manifest_write:
            raise ValueError("UEIF Manifest Studio changes must flow through approval workflow")
        if self.session_hash != _manifest_studio_session_hash(self):
            raise ValueError("UEIF Manifest Studio hash does not match canonical content")
        return self


class UeifVisualModel(UeifValue):
    schema_version: Literal["ueif-visual-model-0.1"] = "ueif-visual-model-0.1"
    visual_id: str = Field(pattern=r"^UEIF-VIS-[0-9]{4}$")
    manifest_object_ref: str = Field(min_length=1, max_length=240)
    object_kind: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    nodes: tuple[str, ...]
    edges: tuple[str, ...] = ()
    generated_from_manifest: bool = True
    independently_editable: bool = False
    visual_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_visual(self) -> UeifVisualModel:
        for values in (self.nodes, self.edges):
            if tuple(sorted(set(values))) != values:
                raise ValueError("UEIF visual model values must be unique and sorted")
        if not self.generated_from_manifest or self.independently_editable:
            raise ValueError(
                "UEIF visual models are generated from Manifest and not edited directly"
            )
        if self.visual_hash != _visual_model_hash(self):
            raise ValueError("UEIF visual model hash does not match canonical content")
        return self


class UeifSearchIndexSnapshot(UeifValue):
    schema_version: Literal["ueif-search-index-snapshot-0.1"] = (
        "ueif-search-index-snapshot-0.1"
    )
    search_id: str = Field(pattern=r"^UEIF-SRCH-[0-9]{4}$")
    query: str = Field(min_length=1, max_length=500)
    semantic: bool = True
    targets: tuple[str, ...]
    result_refs: tuple[str, ...]
    search_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_search(self) -> UeifSearchIndexSnapshot:
        for values in (self.targets, self.result_refs):
            if tuple(sorted(set(values))) != values:
                raise ValueError("UEIF search values must be unique and sorted")
        if not self.semantic:
            raise ValueError("UEIF universal search must be semantic")
        if not self.targets:
            raise ValueError("UEIF universal search requires targets")
        if self.search_hash != _search_index_hash(self):
            raise ValueError("UEIF search snapshot hash does not match canonical content")
        return self


class UeifAiInteractionProposal(UeifValue):
    schema_version: Literal["ueif-ai-interaction-proposal-0.1"] = (
        "ueif-ai-interaction-proposal-0.1"
    )
    proposal_id: str = Field(pattern=r"^UEIF-AIP-[0-9]{4}$")
    ai_session_ref: str = Field(min_length=1, max_length=200)
    manifest_ref: str = Field(min_length=1, max_length=200)
    recommendation: str = Field(min_length=1, max_length=1000)
    impact_analysis_ref: str = Field(min_length=1, max_length=200)
    validation_ref: str = Field(min_length=1, max_length=200)
    status: UeifProposalStatus = UeifProposalStatus.REVIEW_REQUIRED
    directly_modifies_manifest: bool = False
    proposal_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_ai_proposal(self) -> UeifAiInteractionProposal:
        if self.directly_modifies_manifest:
            raise ValueError("UEIF AI recommendations must become proposals, not direct edits")
        if self.status is not UeifProposalStatus.REVIEW_REQUIRED:
            raise ValueError("UEIF AI proposals require human review")
        if self.proposal_hash != _ai_interaction_proposal_hash(self):
            raise ValueError("UEIF AI proposal hash does not match canonical content")
        return self


class UeifApprovalWorkspace(UeifValue):
    schema_version: Literal["ueif-approval-workspace-0.1"] = "ueif-approval-workspace-0.1"
    approval_workspace_id: str = Field(pattern=r"^UEIF-APR-[0-9]{4}$")
    proposal_ref: str = Field(min_length=1, max_length=200)
    affected_object_refs: tuple[str, ...]
    risk_ref: str = Field(min_length=1, max_length=200)
    simulation_ref: str = Field(min_length=1, max_length=200)
    reviewer_comments: tuple[str, ...] = ()
    status: UeifApprovalStatus = UeifApprovalStatus.PENDING
    explicit_approval_required: bool = True
    approval_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_approval_workspace(self) -> UeifApprovalWorkspace:
        if tuple(sorted(set(self.affected_object_refs))) != self.affected_object_refs:
            raise ValueError("UEIF approval affected objects must be unique and sorted")
        if not self.explicit_approval_required:
            raise ValueError("UEIF approval must be explicit")
        if self.approval_hash != _approval_workspace_hash(self):
            raise ValueError("UEIF approval workspace hash does not match canonical content")
        return self


class UeifExplainabilityView(UeifValue):
    schema_version: Literal["ueif-explainability-view-0.1"] = "ueif-explainability-view-0.1"
    explainability_id: str = Field(pattern=r"^UEIF-EXP-[0-9]{4}$")
    object_ref: str = Field(min_length=1, max_length=240)
    answers: dict[str, str]
    traceability_refs: tuple[str, ...]
    explainability_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_explainability(self) -> UeifExplainabilityView:
        required = {
            "what_am_i",
            "why_do_i_exist",
            "who_requested_me",
            "which_manifest_defines_me",
            "which_artifacts_depend_on_me",
            "which_runtime_services_use_me",
            "which_ai_sessions_referenced_me",
        }
        if not required.issubset(set(self.answers)):
            raise ValueError("UEIF explainability requires all mandatory questions")
        if tuple(sorted(set(self.traceability_refs))) != self.traceability_refs:
            raise ValueError("UEIF explainability traceability refs must be unique and sorted")
        if self.explainability_hash != _explainability_view_hash(self):
            raise ValueError("UEIF explainability hash does not match canonical content")
        return self


class UeifExperienceProfile(UeifValue):
    schema_version: Literal["ueif-experience-profile-0.1"] = "ueif-experience-profile-0.1"
    profile_id: str = Field(pattern=r"^UEIF-PROF-[0-9]{4}$")
    user_ref: str = Field(min_length=1, max_length=200)
    role: UeifRole
    device: UeifDevice
    personalization: dict[str, str]
    accessibility: tuple[str, ...]
    changes_project_semantics: bool = False
    profile_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_profile(self) -> UeifExperienceProfile:
        required_accessibility = {
            "keyboard_navigation",
            "screen_readers",
            "high_contrast",
            "scalable_typography",
            "localization",
            "color_independent_communication",
        }
        if not required_accessibility.issubset(set(self.accessibility)):
            raise ValueError("UEIF accessibility requirements are mandatory")
        if tuple(sorted(set(self.accessibility))) != self.accessibility:
            raise ValueError("UEIF accessibility values must be unique and sorted")
        if self.changes_project_semantics:
            raise ValueError("UEIF personalization may not change project semantics")
        if self.profile_hash != _experience_profile_hash(self):
            raise ValueError("UEIF experience profile hash does not match canonical content")
        return self


class UeifTraceabilityView(UeifValue):
    schema_version: Literal["ueif-traceability-view-0.1"] = "ueif-traceability-view-0.1"
    traceability_view_id: str = Field(pattern=r"^UEIF-TRACE-[0-9]{4}$")
    object_ref: str = Field(min_length=1, max_length=240)
    lineage_refs: tuple[str, ...]
    complete_lifecycle_visible: bool = True
    traceability_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_traceability_view(self) -> UeifTraceabilityView:
        if tuple(sorted(set(self.lineage_refs))) != self.lineage_refs:
            raise ValueError("UEIF traceability lineage refs must be unique and sorted")
        required_stages = {
            "requirement",
            "manifest_object",
            "knowledge_node",
            "transformation",
            "artifact",
            "deployment",
            "runtime",
            "audit",
        }
        if not required_stages.issubset(
            {ref.split(":", 1)[0] for ref in self.lineage_refs}
        ):
            raise ValueError("UEIF traceability requires complete lifecycle lineage")
        if not self.complete_lifecycle_visible:
            raise ValueError("UEIF traceability must expose complete lifecycle lineage")
        if self.traceability_hash != _traceability_view_hash(self):
            raise ValueError("UEIF traceability hash does not match canonical content")
        return self


class UeifCollaborationThread(UeifValue):
    schema_version: Literal["ueif-collaboration-thread-0.1"] = (
        "ueif-collaboration-thread-0.1"
    )
    thread_id: str = Field(pattern=r"^UEIF-COLL-[0-9]{4}$")
    manifest_object_ref: str = Field(min_length=1, max_length=240)
    comments: tuple[str, ...] = ()
    review_refs: tuple[str, ...] = ()
    assignment_refs: tuple[str, ...] = ()
    notification_refs: tuple[str, ...] = ()
    anchored_to_manifest_object: bool = True
    collaboration_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_collaboration_thread(self) -> UeifCollaborationThread:
        for values in (
            self.comments,
            self.review_refs,
            self.assignment_refs,
            self.notification_refs,
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError("UEIF collaboration values must be unique and sorted")
        if not self.anchored_to_manifest_object:
            raise ValueError("UEIF collaboration must be anchored to Manifest objects")
        if self.collaboration_hash != _collaboration_thread_hash(self):
            raise ValueError("UEIF collaboration hash does not match canonical content")
        return self


class UeifNotificationRule(UeifValue):
    schema_version: Literal["ueif-notification-rule-0.1"] = "ueif-notification-rule-0.1"
    notification_id: str = Field(pattern=r"^UEIF-NOTIF-[0-9]{4}$")
    event_type: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    role: UeifRole
    object_ref: str = Field(min_length=1, max_length=240)
    delivery_channels: tuple[UeifDevice, ...]
    contextual: bool = True
    notification_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_notification_rule(self) -> UeifNotificationRule:
        sorted_channels = tuple(
            sorted(set(self.delivery_channels), key=lambda item: item.value)
        )
        if sorted_channels != self.delivery_channels:
            raise ValueError("UEIF notification channels must be unique and sorted")
        if not self.contextual:
            raise ValueError("UEIF notifications must be contextual")
        if self.notification_hash != _notification_rule_hash(self):
            raise ValueError("UEIF notification hash does not match canonical content")
        return self


class UeifRoleDashboard(UeifValue):
    schema_version: Literal["ueif-role-dashboard-0.1"] = "ueif-role-dashboard-0.1"
    dashboard_id: str = Field(pattern=r"^UEIF-DASH-[0-9]{4}$")
    role: UeifRole
    widgets: tuple[str, ...]
    source_refs: tuple[str, ...]
    derived_from_manifest: bool = True
    dashboard_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_role_dashboard(self) -> UeifRoleDashboard:
        if tuple(sorted(set(self.widgets))) != self.widgets:
            raise ValueError("UEIF dashboard widgets must be unique and sorted")
        if tuple(sorted(set(self.source_refs))) != self.source_refs:
            raise ValueError("UEIF dashboard source refs must be unique and sorted")
        if not self.derived_from_manifest:
            raise ValueError("UEIF dashboards must derive from Manifest/platform data")
        if self.dashboard_hash != _role_dashboard_hash(self):
            raise ValueError("UEIF dashboard hash does not match canonical content")
        return self


class UeifNavigationMap(UeifValue):
    schema_version: Literal["ueif-navigation-map-0.1"] = "ueif-navigation-map-0.1"
    navigation_id: str = Field(pattern=r"^UEIF-NAV-[0-9]{4}$")
    hierarchy: tuple[str, ...]
    technology_independent: bool = True
    navigation_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_navigation_map(self) -> UeifNavigationMap:
        required_hierarchy = (
            "organization",
            "workspace",
            "portfolio",
            "project",
            "manifest",
            "objects",
            "artifacts",
            "runtime",
        )
        if self.hierarchy != required_hierarchy:
            raise ValueError("UEIF navigation must follow the universal project hierarchy")
        if not self.technology_independent:
            raise ValueError("UEIF navigation may not depend on technology")
        if self.navigation_hash != _navigation_map_hash(self):
            raise ValueError("UEIF navigation hash does not match canonical content")
        return self


class UeifDocumentationPanel(UeifValue):
    schema_version: Literal["ueif-documentation-panel-0.1"] = (
        "ueif-documentation-panel-0.1"
    )
    documentation_id: str = Field(pattern=r"^UEIF-DOC-[0-9]{4}$")
    object_ref: str = Field(min_length=1, max_length=240)
    source_refs: tuple[str, ...]
    generated_from_platform_context: bool = True
    manual_only: bool = False
    documentation_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_documentation_panel(self) -> UeifDocumentationPanel:
        required_sources = {"manifest", "registry", "knowledge_graph", "runtime", "governance"}
        if not required_sources.issubset({ref.split(":", 1)[0] for ref in self.source_refs}):
            raise ValueError("UEIF embedded documentation requires all platform sources")
        if tuple(sorted(set(self.source_refs))) != self.source_refs:
            raise ValueError("UEIF documentation sources must be unique and sorted")
        if not self.generated_from_platform_context or self.manual_only:
            raise ValueError("UEIF documentation must be generated from platform context")
        if self.documentation_hash != _documentation_panel_hash(self):
            raise ValueError("UEIF documentation hash does not match canonical content")
        return self


class UeifWorkspaceSurface(UeifValue):
    schema_version: Literal["ueif-workspace-surface-0.1"] = "ueif-workspace-surface-0.1"
    surface_id: str = Field(pattern=r"^UEIF-SURF-[0-9]{4}$")
    surface_type: UeifWorkspaceSurfaceType
    role: UeifRole
    visible_object_refs: tuple[str, ...]
    source_system_refs: tuple[str, ...]
    real_time_status_visible: bool = True
    derived_from_platform_state: bool = True
    surface_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_workspace_surface(self) -> UeifWorkspaceSurface:
        if tuple(sorted(set(self.visible_object_refs))) != self.visible_object_refs:
            raise ValueError("UEIF workspace surface visible objects must be unique and sorted")
        if tuple(sorted(set(self.source_system_refs))) != self.source_system_refs:
            raise ValueError("UEIF workspace surface source systems must be unique and sorted")
        required_source = {
            UeifWorkspaceSurfaceType.GENERATION: "artifact",
            UeifWorkspaceSurfaceType.RUNTIME: "runtime",
            UeifWorkspaceSurfaceType.GOVERNANCE: "governance",
        }[self.surface_type]
        if required_source not in {ref.split(":", 1)[0] for ref in self.source_system_refs}:
            raise ValueError("UEIF workspace surface must derive from its platform subsystem")
        if not self.real_time_status_visible:
            raise ValueError("UEIF workspace surfaces must expose status")
        if not self.derived_from_platform_state:
            raise ValueError("UEIF workspace surfaces must derive from platform state")
        if self.surface_hash != _workspace_surface_hash(self):
            raise ValueError("UEIF workspace surface hash does not match canonical content")
        return self


class UeifAiInteractionPolicy(UeifValue):
    schema_version: Literal["ueif-ai-interaction-policy-0.1"] = (
        "ueif-ai-interaction-policy-0.1"
    )
    policy_id: str = Field(pattern=r"^UEIF-AIPOL-[0-9]{4}$")
    allowed_actions: tuple[str, ...]
    prohibited_actions: tuple[str, ...]
    proposals_required: bool = True
    approvals_blocked_for_ai: bool = True
    history_mutation_blocked: bool = True
    policy_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_ai_policy(self) -> UeifAiInteractionPolicy:
        required_allowed = {
            "explain",
            "recommend",
            "summarize",
            "analyze",
            "generate_proposals",
            "answer_questions",
        }
        required_prohibited = {
            "approve_changes",
            "bypass_governance",
            "modify_approved_manifests",
            "hide_traceability",
            "alter_platform_history",
        }
        if not required_allowed.issubset(set(self.allowed_actions)):
            raise ValueError("UEIF AI policy requires all allowed interaction actions")
        if not required_prohibited.issubset(set(self.prohibited_actions)):
            raise ValueError("UEIF AI policy requires all prohibited interaction actions")
        for values in (self.allowed_actions, self.prohibited_actions):
            if tuple(sorted(set(values))) != values:
                raise ValueError("UEIF AI policy actions must be unique and sorted")
        if not self.proposals_required:
            raise ValueError("UEIF AI policy must require structured proposals")
        if not self.approvals_blocked_for_ai:
            raise ValueError("UEIF AI policy must block AI approval authority")
        if not self.history_mutation_blocked:
            raise ValueError("UEIF AI policy must block platform history mutation")
        if self.policy_hash != _ai_interaction_policy_hash(self):
            raise ValueError("UEIF AI policy hash does not match canonical content")
        return self


class UeifExperienceApiContract(UeifValue):
    schema_version: Literal["ueif-experience-api-contract-0.1"] = (
        "ueif-experience-api-contract-0.1"
    )
    api_contract_id: str = Field(pattern=r"^UEIF-API-[0-9]{4}$")
    supported_clients: tuple[UeifExperienceClient, ...]
    platform_api_refs: tuple[str, ...]
    decoupled_from_platform_logic: bool = True
    shared_manifest_source: bool = True
    contract_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_api_contract(self) -> UeifExperienceApiContract:
        required_clients = set(UeifExperienceClient)
        if not required_clients.issubset(set(self.supported_clients)):
            raise ValueError("UEIF Experience API must support all required client types")
        sorted_clients = tuple(sorted(set(self.supported_clients), key=lambda item: item.value))
        if sorted_clients != self.supported_clients:
            raise ValueError("UEIF Experience API clients must be unique and sorted")
        if tuple(sorted(set(self.platform_api_refs))) != self.platform_api_refs:
            raise ValueError("UEIF Experience API refs must be unique and sorted")
        if not self.platform_api_refs:
            raise ValueError("UEIF Experience API requires platform API refs")
        if not self.decoupled_from_platform_logic:
            raise ValueError("UEIF Experience API must be decoupled from platform logic")
        if not self.shared_manifest_source:
            raise ValueError("UEIF Experience API clients must use the shared Manifest source")
        if self.contract_hash != _experience_api_contract_hash(self):
            raise ValueError("UEIF Experience API hash does not match canonical content")
        return self


def role_workspace(
    *,
    index: int,
    project_id: str,
    manifest_ref: str,
    role: UeifRole,
    components: tuple[str, ...] = (),
) -> UeifRoleWorkspace:
    default_components = (
        "navigation",
        "project_view",
        "knowledge_view",
        "task_view",
        "generation_view",
        "runtime_view",
        "governance_view",
    )
    provisional = UeifRoleWorkspace.model_construct(
        schema_version="ueif-role-workspace-0.1",
        workspace_id=f"UEIF-WS-{index:04d}",
        project_id=project_id,
        manifest_ref=manifest_ref,
        role=role,
        components=tuple(sorted(set(components or default_components))),
        lifecycle_steps=tuple(sorted(UeifInteractionStep, key=lambda item: item.value)),
        owns_project_data=False,
        workspace_hash="0" * 64,
    )
    return UeifRoleWorkspace(
        **provisional.model_dump(exclude={"workspace_hash"}),
        workspace_hash=_role_workspace_hash(provisional),
    )


def manifest_studio_session(
    *,
    index: int,
    manifest_ref: str,
    validation_hash: str,
    approval_workflow_ref: str,
) -> UeifManifestStudioSession:
    capabilities = (
        "approval_workflow",
        "auto_completion",
        "collaboration",
        "dependency_visualization",
        "natural_language_assistance",
        "semantic_validation",
        "structured_editing",
        "version_comparison",
    )
    provisional = UeifManifestStudioSession.model_construct(
        schema_version="ueif-manifest-studio-session-0.1",
        session_id=f"UEIF-STUDIO-{index:04d}",
        manifest_ref=manifest_ref,
        capabilities=capabilities,
        validation_hash=validation_hash,
        approval_workflow_ref=approval_workflow_ref,
        direct_manifest_write=False,
        session_hash="0" * 64,
    )
    return UeifManifestStudioSession(
        **provisional.model_dump(exclude={"session_hash"}),
        session_hash=_manifest_studio_session_hash(provisional),
    )


def visual_model(
    *,
    index: int,
    manifest_object_ref: str,
    object_kind: str,
    nodes: tuple[str, ...],
    edges: tuple[str, ...] = (),
) -> UeifVisualModel:
    provisional = UeifVisualModel.model_construct(
        schema_version="ueif-visual-model-0.1",
        visual_id=f"UEIF-VIS-{index:04d}",
        manifest_object_ref=manifest_object_ref,
        object_kind=object_kind,
        nodes=tuple(sorted(set(nodes))),
        edges=tuple(sorted(set(edges))),
        generated_from_manifest=True,
        independently_editable=False,
        visual_hash="0" * 64,
    )
    return UeifVisualModel(
        **provisional.model_dump(exclude={"visual_hash"}),
        visual_hash=_visual_model_hash(provisional),
    )


def search_index_snapshot(
    *,
    index: int,
    query: str,
    targets: tuple[str, ...],
    result_refs: tuple[str, ...],
) -> UeifSearchIndexSnapshot:
    provisional = UeifSearchIndexSnapshot.model_construct(
        schema_version="ueif-search-index-snapshot-0.1",
        search_id=f"UEIF-SRCH-{index:04d}",
        query=query,
        semantic=True,
        targets=tuple(sorted(set(targets))),
        result_refs=tuple(sorted(set(result_refs))),
        search_hash="0" * 64,
    )
    return UeifSearchIndexSnapshot(
        **provisional.model_dump(exclude={"search_hash"}),
        search_hash=_search_index_hash(provisional),
    )


def ai_interaction_proposal(
    *,
    index: int,
    ai_session_ref: str,
    manifest_ref: str,
    recommendation: str,
    impact_analysis_ref: str,
    validation_ref: str,
) -> UeifAiInteractionProposal:
    provisional = UeifAiInteractionProposal.model_construct(
        schema_version="ueif-ai-interaction-proposal-0.1",
        proposal_id=f"UEIF-AIP-{index:04d}",
        ai_session_ref=ai_session_ref,
        manifest_ref=manifest_ref,
        recommendation=recommendation,
        impact_analysis_ref=impact_analysis_ref,
        validation_ref=validation_ref,
        status=UeifProposalStatus.REVIEW_REQUIRED,
        directly_modifies_manifest=False,
        proposal_hash="0" * 64,
    )
    return UeifAiInteractionProposal(
        **provisional.model_dump(exclude={"proposal_hash"}),
        proposal_hash=_ai_interaction_proposal_hash(provisional),
    )


def approval_workspace(
    *,
    index: int,
    proposal_ref: str,
    affected_object_refs: tuple[str, ...],
    risk_ref: str,
    simulation_ref: str,
    reviewer_comments: tuple[str, ...] = (),
) -> UeifApprovalWorkspace:
    provisional = UeifApprovalWorkspace.model_construct(
        schema_version="ueif-approval-workspace-0.1",
        approval_workspace_id=f"UEIF-APR-{index:04d}",
        proposal_ref=proposal_ref,
        affected_object_refs=tuple(sorted(set(affected_object_refs))),
        risk_ref=risk_ref,
        simulation_ref=simulation_ref,
        reviewer_comments=tuple(sorted(set(reviewer_comments))),
        status=UeifApprovalStatus.PENDING,
        explicit_approval_required=True,
        approval_hash="0" * 64,
    )
    return UeifApprovalWorkspace(
        **provisional.model_dump(exclude={"approval_hash"}),
        approval_hash=_approval_workspace_hash(provisional),
    )


def explainability_view(
    *,
    index: int,
    object_ref: str,
    answers: dict[str, str],
    traceability_refs: tuple[str, ...],
) -> UeifExplainabilityView:
    provisional = UeifExplainabilityView.model_construct(
        schema_version="ueif-explainability-view-0.1",
        explainability_id=f"UEIF-EXP-{index:04d}",
        object_ref=object_ref,
        answers=dict(sorted(answers.items())),
        traceability_refs=tuple(sorted(set(traceability_refs))),
        explainability_hash="0" * 64,
    )
    return UeifExplainabilityView(
        **provisional.model_dump(exclude={"explainability_hash"}),
        explainability_hash=_explainability_view_hash(provisional),
    )


def experience_profile(
    *,
    index: int,
    user_ref: str,
    role: UeifRole,
    device: UeifDevice,
    personalization: dict[str, str],
) -> UeifExperienceProfile:
    accessibility = (
        "color_independent_communication",
        "high_contrast",
        "keyboard_navigation",
        "localization",
        "scalable_typography",
        "screen_readers",
    )
    provisional = UeifExperienceProfile.model_construct(
        schema_version="ueif-experience-profile-0.1",
        profile_id=f"UEIF-PROF-{index:04d}",
        user_ref=user_ref,
        role=role,
        device=device,
        personalization=dict(sorted(personalization.items())),
        accessibility=accessibility,
        changes_project_semantics=False,
        profile_hash="0" * 64,
    )
    return UeifExperienceProfile(
        **provisional.model_dump(exclude={"profile_hash"}),
        profile_hash=_experience_profile_hash(provisional),
    )


def traceability_view(
    *,
    index: int,
    object_ref: str,
    lineage_refs: tuple[str, ...],
) -> UeifTraceabilityView:
    provisional = UeifTraceabilityView.model_construct(
        schema_version="ueif-traceability-view-0.1",
        traceability_view_id=f"UEIF-TRACE-{index:04d}",
        object_ref=object_ref,
        lineage_refs=tuple(sorted(set(lineage_refs))),
        complete_lifecycle_visible=True,
        traceability_hash="0" * 64,
    )
    return UeifTraceabilityView(
        **provisional.model_dump(exclude={"traceability_hash"}),
        traceability_hash=_traceability_view_hash(provisional),
    )


def collaboration_thread(
    *,
    index: int,
    manifest_object_ref: str,
    comments: tuple[str, ...] = (),
    review_refs: tuple[str, ...] = (),
    assignment_refs: tuple[str, ...] = (),
    notification_refs: tuple[str, ...] = (),
) -> UeifCollaborationThread:
    provisional = UeifCollaborationThread.model_construct(
        schema_version="ueif-collaboration-thread-0.1",
        thread_id=f"UEIF-COLL-{index:04d}",
        manifest_object_ref=manifest_object_ref,
        comments=tuple(sorted(set(comments))),
        review_refs=tuple(sorted(set(review_refs))),
        assignment_refs=tuple(sorted(set(assignment_refs))),
        notification_refs=tuple(sorted(set(notification_refs))),
        anchored_to_manifest_object=True,
        collaboration_hash="0" * 64,
    )
    return UeifCollaborationThread(
        **provisional.model_dump(exclude={"collaboration_hash"}),
        collaboration_hash=_collaboration_thread_hash(provisional),
    )


def notification_rule(
    *,
    index: int,
    event_type: str,
    role: UeifRole,
    object_ref: str,
    delivery_channels: tuple[UeifDevice, ...],
) -> UeifNotificationRule:
    provisional = UeifNotificationRule.model_construct(
        schema_version="ueif-notification-rule-0.1",
        notification_id=f"UEIF-NOTIF-{index:04d}",
        event_type=event_type,
        role=role,
        object_ref=object_ref,
        delivery_channels=tuple(sorted(set(delivery_channels), key=lambda item: item.value)),
        contextual=True,
        notification_hash="0" * 64,
    )
    return UeifNotificationRule(
        **provisional.model_dump(exclude={"notification_hash"}),
        notification_hash=_notification_rule_hash(provisional),
    )


def role_dashboard(
    *,
    index: int,
    role: UeifRole,
    widgets: tuple[str, ...],
    source_refs: tuple[str, ...],
) -> UeifRoleDashboard:
    provisional = UeifRoleDashboard.model_construct(
        schema_version="ueif-role-dashboard-0.1",
        dashboard_id=f"UEIF-DASH-{index:04d}",
        role=role,
        widgets=tuple(sorted(set(widgets))),
        source_refs=tuple(sorted(set(source_refs))),
        derived_from_manifest=True,
        dashboard_hash="0" * 64,
    )
    return UeifRoleDashboard(
        **provisional.model_dump(exclude={"dashboard_hash"}),
        dashboard_hash=_role_dashboard_hash(provisional),
    )


def navigation_map(*, index: int) -> UeifNavigationMap:
    hierarchy = (
        "organization",
        "workspace",
        "portfolio",
        "project",
        "manifest",
        "objects",
        "artifacts",
        "runtime",
    )
    provisional = UeifNavigationMap.model_construct(
        schema_version="ueif-navigation-map-0.1",
        navigation_id=f"UEIF-NAV-{index:04d}",
        hierarchy=hierarchy,
        technology_independent=True,
        navigation_hash="0" * 64,
    )
    return UeifNavigationMap(
        **provisional.model_dump(exclude={"navigation_hash"}),
        navigation_hash=_navigation_map_hash(provisional),
    )


def documentation_panel(
    *,
    index: int,
    object_ref: str,
    source_refs: tuple[str, ...],
) -> UeifDocumentationPanel:
    provisional = UeifDocumentationPanel.model_construct(
        schema_version="ueif-documentation-panel-0.1",
        documentation_id=f"UEIF-DOC-{index:04d}",
        object_ref=object_ref,
        source_refs=tuple(sorted(set(source_refs))),
        generated_from_platform_context=True,
        manual_only=False,
        documentation_hash="0" * 64,
    )
    return UeifDocumentationPanel(
        **provisional.model_dump(exclude={"documentation_hash"}),
        documentation_hash=_documentation_panel_hash(provisional),
    )


def workspace_surface(
    *,
    index: int,
    surface_type: UeifWorkspaceSurfaceType,
    role: UeifRole,
    visible_object_refs: tuple[str, ...],
    source_system_refs: tuple[str, ...],
) -> UeifWorkspaceSurface:
    provisional = UeifWorkspaceSurface.model_construct(
        schema_version="ueif-workspace-surface-0.1",
        surface_id=f"UEIF-SURF-{index:04d}",
        surface_type=surface_type,
        role=role,
        visible_object_refs=tuple(sorted(set(visible_object_refs))),
        source_system_refs=tuple(sorted(set(source_system_refs))),
        real_time_status_visible=True,
        derived_from_platform_state=True,
        surface_hash="0" * 64,
    )
    return UeifWorkspaceSurface(
        **provisional.model_dump(exclude={"surface_hash"}),
        surface_hash=_workspace_surface_hash(provisional),
    )


def ai_interaction_policy(*, index: int) -> UeifAiInteractionPolicy:
    allowed_actions = (
        "analyze",
        "answer_questions",
        "explain",
        "generate_proposals",
        "recommend",
        "summarize",
    )
    prohibited_actions = (
        "alter_platform_history",
        "approve_changes",
        "bypass_governance",
        "hide_traceability",
        "modify_approved_manifests",
    )
    provisional = UeifAiInteractionPolicy.model_construct(
        schema_version="ueif-ai-interaction-policy-0.1",
        policy_id=f"UEIF-AIPOL-{index:04d}",
        allowed_actions=allowed_actions,
        prohibited_actions=prohibited_actions,
        proposals_required=True,
        approvals_blocked_for_ai=True,
        history_mutation_blocked=True,
        policy_hash="0" * 64,
    )
    return UeifAiInteractionPolicy(
        **provisional.model_dump(exclude={"policy_hash"}),
        policy_hash=_ai_interaction_policy_hash(provisional),
    )


def experience_api_contract(
    *,
    index: int,
    platform_api_refs: tuple[str, ...],
) -> UeifExperienceApiContract:
    provisional = UeifExperienceApiContract.model_construct(
        schema_version="ueif-experience-api-contract-0.1",
        api_contract_id=f"UEIF-API-{index:04d}",
        supported_clients=tuple(
            sorted(UeifExperienceClient, key=lambda item: item.value)
        ),
        platform_api_refs=tuple(sorted(set(platform_api_refs))),
        decoupled_from_platform_logic=True,
        shared_manifest_source=True,
        contract_hash="0" * 64,
    )
    return UeifExperienceApiContract(
        **provisional.model_dump(exclude={"contract_hash"}),
        contract_hash=_experience_api_contract_hash(provisional),
    )


def _role_workspace_hash(value: UeifRoleWorkspace) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"workspace_hash"}))


def _manifest_studio_session_hash(value: UeifManifestStudioSession) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"session_hash"}))


def _visual_model_hash(value: UeifVisualModel) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"visual_hash"}))


def _search_index_hash(value: UeifSearchIndexSnapshot) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"search_hash"}))


def _ai_interaction_proposal_hash(value: UeifAiInteractionProposal) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"proposal_hash"}))


def _approval_workspace_hash(value: UeifApprovalWorkspace) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"approval_hash"}))


def _explainability_view_hash(value: UeifExplainabilityView) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"explainability_hash"}))


def _experience_profile_hash(value: UeifExperienceProfile) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"profile_hash"}))


def _traceability_view_hash(value: UeifTraceabilityView) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"traceability_hash"}))


def _collaboration_thread_hash(value: UeifCollaborationThread) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"collaboration_hash"}))


def _notification_rule_hash(value: UeifNotificationRule) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"notification_hash"}))


def _role_dashboard_hash(value: UeifRoleDashboard) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"dashboard_hash"}))


def _navigation_map_hash(value: UeifNavigationMap) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"navigation_hash"}))


def _documentation_panel_hash(value: UeifDocumentationPanel) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"documentation_hash"}))


def _workspace_surface_hash(value: UeifWorkspaceSurface) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"surface_hash"}))


def _ai_interaction_policy_hash(value: UeifAiInteractionPolicy) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"policy_hash"}))


def _experience_api_contract_hash(value: UeifExperienceApiContract) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"contract_hash"}))
