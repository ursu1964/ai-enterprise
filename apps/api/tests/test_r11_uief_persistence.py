from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ai_enterprise.api.r11_uief_schemas import R11IntegrationDashboardResponse
from ai_enterprise.infrastructure.knowledge.models import R11IntegrationRecordModel
from ai_enterprise.main import app

ROOT = Path(__file__).resolve().parents[3]


def _has_unique_constraint(model: type, *columns: str) -> bool:
    expected = set(columns)
    return any(
        getattr(constraint, "columns", None) is not None
        and {column.name for column in constraint.columns} == expected
        for constraint in model.__table__.constraints
    )


def test_r11_storage_model_is_append_only_project_integration_record_store() -> None:
    assert R11IntegrationRecordModel.__table__.c.record_document.type.__class__.__name__ == "JSONB"
    assert R11IntegrationRecordModel.__table__.c.project_id.foreign_keys
    assert R11IntegrationRecordModel.__table__.c.integration_ref.index
    assert R11IntegrationRecordModel.__table__.c.lifecycle_state.index
    assert R11IntegrationRecordModel.__table__.c.health_status.index
    assert _has_unique_constraint(
        R11IntegrationRecordModel,
        "project_id",
        "record_type",
        "record_id",
        "record_hash",
    )
    assert _has_unique_constraint(R11IntegrationRecordModel, "project_id", "record_hash")


def test_r11_migration_is_linear_and_declares_append_only_records() -> None:
    migration = (
        ROOT / "migrations/versions/c4f7a9e2b6d1_add_r11_integration_records.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: str | None = "b3e6f9a1c4d7"' in migration
    assert '"r11_integration_records"' in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "postgresql.JSONB" in migration


def test_r11_uief_routes_are_exposed_in_openapi() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert "/api/v1/projects/{project_id}/uief/integrations" in paths
    assert "/api/v1/projects/{project_id}/uief/connectors" in paths
    assert "/api/v1/projects/{project_id}/uief/contracts" in paths
    assert "/api/v1/projects/{project_id}/uief/data-mappings" in paths
    assert "/api/v1/projects/{project_id}/uief/events" in paths
    assert "/api/v1/projects/{project_id}/uief/retry-policies" in paths
    assert "/api/v1/projects/{project_id}/uief/security-policies" in paths
    assert "/api/v1/projects/{project_id}/uief/digital-twins" in paths
    assert "/api/v1/projects/{project_id}/uief/marketplace-assets" in paths
    assert "/api/v1/projects/{project_id}/uief/provider-abstractions" in paths
    assert "/api/v1/projects/{project_id}/uief/ai-boundaries" in paths
    assert "/api/v1/projects/{project_id}/uief/records" in paths
    assert "/api/v1/projects/{project_id}/uief/dashboard" in paths
    assert "/api/v1/projects/{project_id}/uief/runtime/compatibility" in paths
    assert "/api/v1/projects/{project_id}/uief/runtime/generation-plan" in paths
    assert "/api/v1/projects/{project_id}/uief/runtime/test-plan" in paths
    assert "/api/v1/projects/{project_id}/uief/runtime/reconciliation" in paths
    assert "/api/v1/projects/{project_id}/uief/runtime/observability" in paths
    assert "/api/v1/projects/{project_id}/uief/runtime/topology" in paths
    assert "/api/v1/projects/{project_id}/uief/runtime/documentation" in paths
    assert "/api/v1/projects/{project_id}/uief/runtime/sandbox-plan" in paths
    assert "/api/v1/projects/{project_id}/uief/runtime/security-readiness" in paths
    assert "/api/v1/projects/{project_id}/uief/runtime/impact-analysis" in paths
    assert "/api/v1/projects/{project_id}/uief/runtime/migration-plan" in paths
    assert "/api/v1/projects/{project_id}/uief/runtime/ecosystem-readiness" in paths
    assert "/api/v1/projects/{project_id}/uief/runtime/developer-surface" in paths
    assert "/api/v1/projects/{project_id}/uief/runtime/deployment-preflight" in paths
    assert paths["/api/v1/projects/{project_id}/uief/integrations"]["post"]["tags"] == [
        "r11-uief"
    ]


def test_r11_dashboard_response_exposes_integration_operating_metrics() -> None:
    schema = R11IntegrationDashboardResponse(
        project_id="00000000-0000-0000-0000-000000000001",
        integration_count=1,
        connector_count=2,
        contract_count=3,
        mapping_count=4,
        event_count=5,
        retry_policy_count=6,
        security_policy_count=7,
        digital_twin_count=8,
        active_integration_count=9,
        unhealthy_twin_count=10,
        marketplace_asset_count=11,
        provider_abstraction_count=12,
        ai_boundary_count=13,
    )

    assert schema.integration_count == 1
    assert schema.active_integration_count == 9
    assert schema.ai_boundary_count == 13
