from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_enterprise.domain.r10_ueif import (
    UeifDevice,
    UeifExperienceClient,
    UeifRole,
    UeifWorkspaceSurfaceType,
    ai_interaction_policy,
    ai_interaction_proposal,
    approval_workspace,
    collaboration_thread,
    documentation_panel,
    experience_api_contract,
    experience_profile,
    explainability_view,
    manifest_studio_session,
    navigation_map,
    notification_rule,
    role_dashboard,
    role_workspace,
    search_index_snapshot,
    traceability_view,
    visual_model,
    workspace_surface,
)


def test_r10_role_workspace_preserves_manifest_ownership_boundary() -> None:
    workspace = role_workspace(
        index=1,
        project_id="project-1",
        manifest_ref="manifest:orders:v1",
        role=UeifRole.DEVELOPER,
    )

    assert workspace.workspace_id == "UEIF-WS-0001"
    assert workspace.owns_project_data is False
    assert "knowledge_view" in workspace.components
    assert workspace.workspace_hash

    with pytest.raises(ValidationError, match="may not own project data"):
        workspace.__class__.model_validate(
            workspace.model_dump(mode="json") | {"owns_project_data": True}
        )


def test_r10_manifest_studio_and_visual_model_are_controlled_manifest_interfaces() -> None:
    session = manifest_studio_session(
        index=1,
        manifest_ref="manifest:orders:v1",
        validation_hash="a" * 64,
        approval_workflow_ref="approval:orders:v1",
    )
    visual = visual_model(
        index=1,
        manifest_object_ref="entity:order",
        object_kind="entity",
        nodes=("order", "customer"),
        edges=("customer:owns:order",),
    )

    assert session.direct_manifest_write is False
    assert "approval_workflow" in session.capabilities
    assert visual.generated_from_manifest is True
    assert visual.independently_editable is False


def test_r10_ai_proposals_and_approvals_require_human_review() -> None:
    proposal = ai_interaction_proposal(
        index=1,
        ai_session_ref="ai-session:1",
        manifest_ref="manifest:orders:v1",
        recommendation="Add an order cancellation policy.",
        impact_analysis_ref="impact:1",
        validation_ref="validation:1",
    )
    approval = approval_workspace(
        index=1,
        proposal_ref=proposal.proposal_id,
        affected_object_refs=("entity:order", "workflow:cancel-order"),
        risk_ref="risk:1",
        simulation_ref="simulation:1",
    )

    assert proposal.status.value == "review_required"
    assert proposal.directly_modifies_manifest is False
    assert approval.explicit_approval_required is True
    assert approval.status.value == "pending"


def test_r10_search_explainability_profile_traceability_and_collaboration() -> None:
    search = search_index_snapshot(
        index=1,
        query="order cancellation",
        targets=("artifacts", "manifest_objects", "runtime_events"),
        result_refs=("artifact:api", "manifest:order", "runtime:event"),
    )
    explainability = explainability_view(
        index=1,
        object_ref="entity:order",
        answers={
            "what_am_i": "Order entity",
            "why_do_i_exist": "Supports order management",
            "who_requested_me": "product-owner",
            "which_manifest_defines_me": "manifest:orders:v1",
            "which_artifacts_depend_on_me": "artifact:api",
            "which_runtime_services_use_me": "service:orders",
            "which_ai_sessions_referenced_me": "ai-session:1",
        },
        traceability_refs=("artifact:api", "manifest:order"),
    )
    profile = experience_profile(
        index=1,
        user_ref="user:developer",
        role=UeifRole.DEVELOPER,
        device=UeifDevice.BROWSER,
        personalization={"theme": "dark"},
    )
    trace = traceability_view(
        index=1,
        object_ref="entity:order",
        lineage_refs=(
            "artifact:api",
            "audit:approval",
            "deployment:orders",
            "knowledge_node:order",
            "manifest_object:order",
            "requirement:cancel-order",
            "runtime:orders",
            "transformation:manifest-to-api",
        ),
    )
    collaboration = collaboration_thread(
        index=1,
        manifest_object_ref="entity:order",
        comments=("comment:1",),
        review_refs=("review:1",),
    )

    assert search.semantic is True
    assert explainability.explainability_hash
    assert "screen_readers" in profile.accessibility
    assert trace.complete_lifecycle_visible is True
    assert collaboration.anchored_to_manifest_object is True


def test_r10_notifications_dashboards_navigation_and_docs_are_platform_derived() -> None:
    notification = notification_rule(
        index=1,
        event_type="approval.requested",
        role=UeifRole.PRODUCT_OWNER,
        object_ref="proposal:1",
        delivery_channels=(UeifDevice.BROWSER, UeifDevice.MOBILE),
    )
    dashboard = role_dashboard(
        index=1,
        role=UeifRole.OPERATOR,
        widgets=("deployments", "incidents", "runtime_health"),
        source_refs=("manifest:orders", "runtime:orders"),
    )
    navigation = navigation_map(index=1)
    docs = documentation_panel(
        index=1,
        object_ref="entity:order",
        source_refs=(
            "governance:approval",
            "knowledge_graph:order",
            "manifest:orders",
            "registry:objects",
            "runtime:orders",
        ),
    )

    assert notification.contextual is True
    assert dashboard.derived_from_manifest is True
    assert navigation.technology_independent is True
    assert docs.generated_from_platform_context is True
    assert docs.manual_only is False


def test_r10_workspace_surfaces_ai_constraints_and_experience_api_are_explicit() -> None:
    surface = workspace_surface(
        index=1,
        surface_type=UeifWorkspaceSurfaceType.RUNTIME,
        role=UeifRole.OPERATOR,
        visible_object_refs=("deployment:orders", "incident:late-payment"),
        source_system_refs=("manifest:orders", "runtime:orders"),
    )
    policy = ai_interaction_policy(index=1)
    api_contract = experience_api_contract(
        index=1,
        platform_api_refs=(
            "/api/v1/projects/{project_id}/ueif/records",
            "/api/v1/projects/{project_id}/ueif/dashboard",
        ),
    )

    assert surface.surface_type is UeifWorkspaceSurfaceType.RUNTIME
    assert surface.real_time_status_visible is True
    assert "approve_changes" in policy.prohibited_actions
    assert policy.approvals_blocked_for_ai is True
    assert UeifExperienceClient.IDE_EXTENSION in api_contract.supported_clients
    assert api_contract.decoupled_from_platform_logic is True
