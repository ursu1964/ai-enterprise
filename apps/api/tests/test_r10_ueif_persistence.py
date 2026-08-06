from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ai_enterprise.api.r10_ueif_schemas import R10ExperienceDashboardResponse
from ai_enterprise.infrastructure.knowledge.models import R10ExperienceRecordModel
from ai_enterprise.main import app

ROOT = Path(__file__).resolve().parents[3]


def _has_unique_constraint(model: type, *columns: str) -> bool:
    expected = set(columns)
    return any(
        getattr(constraint, "columns", None) is not None
        and {column.name for column in constraint.columns} == expected
        for constraint in model.__table__.constraints
    )


def test_r10_storage_model_is_append_only_project_experience_record_store() -> None:
    assert R10ExperienceRecordModel.__table__.c.record_document.type.__class__.__name__ == "JSONB"
    assert R10ExperienceRecordModel.__table__.c.project_id.foreign_keys
    assert R10ExperienceRecordModel.__table__.c.role.index
    assert R10ExperienceRecordModel.__table__.c.object_ref.index
    assert _has_unique_constraint(
        R10ExperienceRecordModel,
        "project_id",
        "record_type",
        "record_id",
        "record_hash",
    )
    assert _has_unique_constraint(R10ExperienceRecordModel, "project_id", "record_hash")


def test_r10_migration_is_linear_and_declares_append_only_records() -> None:
    migration = (
        ROOT / "migrations/versions/b3e6f9a1c4d7_add_r10_experience_records.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: str | None = "a9c1e4f6b8d2"' in migration
    assert '"r10_experience_records"' in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "postgresql.JSONB" in migration


def test_r10_ueif_routes_are_exposed_in_openapi() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert "/api/v1/projects/{project_id}/ueif/role-workspaces" in paths
    assert "/api/v1/projects/{project_id}/ueif/manifest-studio-sessions" in paths
    assert "/api/v1/projects/{project_id}/ueif/visual-models" in paths
    assert "/api/v1/projects/{project_id}/ueif/search-snapshots" in paths
    assert "/api/v1/projects/{project_id}/ueif/ai-proposals" in paths
    assert "/api/v1/projects/{project_id}/ueif/approval-workspaces" in paths
    assert "/api/v1/projects/{project_id}/ueif/explainability-views" in paths
    assert "/api/v1/projects/{project_id}/ueif/experience-profiles" in paths
    assert "/api/v1/projects/{project_id}/ueif/traceability-views" in paths
    assert "/api/v1/projects/{project_id}/ueif/collaboration-threads" in paths
    assert "/api/v1/projects/{project_id}/ueif/notification-rules" in paths
    assert "/api/v1/projects/{project_id}/ueif/role-dashboards" in paths
    assert "/api/v1/projects/{project_id}/ueif/navigation-maps" in paths
    assert "/api/v1/projects/{project_id}/ueif/documentation-panels" in paths
    assert "/api/v1/projects/{project_id}/ueif/workspace-surfaces" in paths
    assert "/api/v1/projects/{project_id}/ueif/ai-interaction-policies" in paths
    assert "/api/v1/projects/{project_id}/ueif/experience-api-contracts" in paths
    assert "/api/v1/projects/{project_id}/ueif/records" in paths
    assert "/api/v1/projects/{project_id}/ueif/events" in paths
    assert "/api/v1/projects/{project_id}/ueif/dashboard" in paths
    assert paths["/api/v1/projects/{project_id}/ueif/role-workspaces"]["post"]["tags"] == [
        "r10-ueif"
    ]


def test_r10_dashboard_response_exposes_experience_operating_metrics() -> None:
    schema = R10ExperienceDashboardResponse(
        project_id="00000000-0000-0000-0000-000000000001",
        workspace_count=1,
        manifest_studio_session_count=2,
        visual_model_count=3,
        search_snapshot_count=4,
        ai_proposal_count=5,
        pending_ai_proposal_count=6,
        approval_workspace_count=7,
        explainability_view_count=8,
        experience_profile_count=9,
        traceability_view_count=10,
        collaboration_thread_count=11,
        notification_rule_count=12,
        role_dashboard_count=13,
        navigation_map_count=14,
        documentation_panel_count=15,
        workspace_surface_count=16,
        ai_interaction_policy_count=17,
        experience_api_contract_count=18,
    )

    assert schema.workspace_count == 1
    assert schema.pending_ai_proposal_count == 6
    assert schema.documentation_panel_count == 15
    assert schema.workspace_surface_count == 16
    assert schema.ai_interaction_policy_count == 17
    assert schema.experience_api_contract_count == 18
