from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ai_enterprise.api.r9_uak_schemas import R9KernelDashboardResponse
from ai_enterprise.infrastructure.knowledge.models import R9KernelRecordModel
from ai_enterprise.main import app

ROOT = Path(__file__).resolve().parents[3]


def _has_unique_constraint(model: type, *columns: str) -> bool:
    expected = set(columns)
    return any(
        getattr(constraint, "columns", None) is not None
        and {column.name for column in constraint.columns} == expected
        for constraint in model.__table__.constraints
    )


def test_r9_storage_model_is_append_only_typed_kernel_record_store() -> None:
    assert R9KernelRecordModel.__table__.c.record_document.type.__class__.__name__ == "JSONB"
    assert R9KernelRecordModel.__table__.c.organization_id.foreign_keys
    assert R9KernelRecordModel.__table__.c.project_id.foreign_keys
    assert R9KernelRecordModel.__table__.c.scope_type.index
    assert R9KernelRecordModel.__table__.c.object_identity.index
    assert _has_unique_constraint(
        R9KernelRecordModel,
        "scope_type",
        "scope_id",
        "record_type",
        "record_id",
        "record_hash",
    )
    assert _has_unique_constraint(R9KernelRecordModel, "record_hash")


def test_r9_migration_is_linear_and_declares_append_only_records() -> None:
    migration = (
        ROOT / "migrations/versions/a9c1e4f6b8d2_add_r9_kernel_records.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: str | None = "f4b8d2a6c9e1"' in migration
    assert '"r9_kernel_records"' in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "postgresql.JSONB" in migration


def test_r9_uak_routes_are_exposed_in_openapi() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert "/api/v1/kernel/subsystems" in paths
    assert "/api/v1/kernel/events" in paths
    assert "/api/v1/kernel/lifecycle-states" in paths
    assert "/api/v1/kernel/transactions" in paths
    assert "/api/v1/kernel/checkpoints" in paths
    assert "/api/v1/kernel/plugins" in paths
    assert "/api/v1/kernel/ai-session-boundaries" in paths
    assert "/api/v1/kernel/workspace-hierarchies" in paths
    assert "/api/v1/kernel/schedules" in paths
    assert "/api/v1/kernel/resource-allocations" in paths
    assert "/api/v1/kernel/sdk-contracts" in paths
    assert "/api/v1/kernel/registry-snapshots" in paths
    assert "/api/v1/kernel/security-envelopes" in paths
    assert "/api/v1/kernel/deployment-coordinations" in paths
    assert "/api/v1/kernel/monitoring-aggregates" in paths
    assert "/api/v1/kernel/runtime/replay" in paths
    assert "/api/v1/kernel/runtime/dispatch-schedules" in paths
    assert "/api/v1/kernel/runtime/operational-readiness" in paths
    assert "/api/v1/kernel/sdk-contracts/{record_id}/materialize" in paths
    assert "/api/v1/kernel/sdk-contracts/{record_id}/publish" in paths
    assert "/api/v1/kernel/records" in paths
    assert "/api/v1/kernel/dashboard" in paths
    assert paths["/api/v1/kernel/subsystems"]["post"]["tags"] == ["r9-uak"]


def test_r9_dashboard_response_exposes_kernel_operating_metrics() -> None:
    schema = R9KernelDashboardResponse(
        scope_type="platform",
        scope_id="default",
        subsystem_count=12,
        event_count=40,
        latest_lifecycle_state="running",
        committed_transaction_count=31,
        rolled_back_transaction_count=2,
        ready_checkpoint_count=3,
        blocked_checkpoint_count=1,
        plugin_count=4,
        ai_session_boundary_count=5,
        workspace_hierarchy_count=6,
        dispatchable_schedule_count=7,
        blocked_schedule_count=8,
        allocated_resource_count=9,
        insufficient_resource_count=10,
        sdk_contract_count=11,
        registry_snapshot_count=12,
        security_envelope_count=13,
        deployment_coordination_count=14,
        monitoring_aggregate_count=15,
    )

    assert schema.subsystem_count == 12
    assert schema.latest_lifecycle_state == "running"
    assert schema.rolled_back_transaction_count == 2
    assert schema.plugin_count == 4
    assert schema.ai_session_boundary_count == 5
    assert schema.blocked_schedule_count == 8
    assert schema.insufficient_resource_count == 10
    assert schema.sdk_contract_count == 11
    assert schema.registry_snapshot_count == 12
    assert schema.security_envelope_count == 13
    assert schema.deployment_coordination_count == 14
    assert schema.monitoring_aggregate_count == 15
