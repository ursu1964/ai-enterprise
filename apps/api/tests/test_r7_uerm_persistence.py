from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ai_enterprise.infrastructure.knowledge.models import (
    R7CompatibilityReportModel,
    R7DeploymentRuntimeSyncModel,
    R7DigitalTwinSnapshotModel,
    R7EventDispatchModel,
    R7HealthReportModel,
    R7PluginBindingModel,
    R7PolicyEvaluationModel,
    R7RecoveryActionModel,
    R7RuntimeAiRequestModel,
    R7RuntimeAuditRecordModel,
    R7RuntimeConfigurationSnapshotModel,
    R7RuntimeDeploymentModel,
    R7RuntimeErrorModel,
    R7RuntimeEventModel,
    R7RuntimeGovernanceTraceModel,
    R7RuntimeProviderModel,
    R7RuntimeSynchronizationReportModel,
    R7RuntimeTelemetryBatchModel,
    R7RuntimeUpgradePlanModel,
    R7WorkflowInstanceModel,
)
from ai_enterprise.main import app

ROOT = Path(__file__).resolve().parents[3]


def _has_unique_constraint(model: type, *columns: str) -> bool:
    expected = set(columns)
    return any(
        getattr(constraint, "columns", None) is not None
        and {column.name for column in constraint.columns} == expected
        for constraint in model.__table__.constraints
    )


def test_r7_storage_models_cover_runtime_registry_health_and_events() -> None:
    assert R7RuntimeDeploymentModel.__table__.c.deployment_document.type.__class__.__name__ == (
        "JSONB"
    )
    assert R7RuntimeDeploymentModel.__table__.c.r6_generation_build_id.foreign_keys
    assert R7RuntimeDeploymentModel.__table__.c.template_version.index
    assert R7RuntimeDeploymentModel.__table__.c.deployment_location.index
    assert _has_unique_constraint(
        R7RuntimeDeploymentModel,
        "r6_generation_build_id",
        "environment",
        "service_identity",
    )
    assert _has_unique_constraint(R7RuntimeDeploymentModel, "project_id", "deployment_hash")

    assert R7HealthReportModel.__table__.c.report_document.type.__class__.__name__ == "JSONB"
    assert R7HealthReportModel.__table__.c.runtime_deployment_id.foreign_keys
    assert _has_unique_constraint(R7HealthReportModel, "runtime_deployment_id", "report_hash")

    assert R7RuntimeEventModel.__table__.c.context_document.type.__class__.__name__ == "JSONB"
    assert R7RuntimeEventModel.__table__.c.runtime_deployment_id.foreign_keys
    assert _has_unique_constraint(R7RuntimeEventModel, "runtime_deployment_id", "event_id")
    assert _has_unique_constraint(R7RuntimeEventModel, "project_id", "event_hash")

    assert R7CompatibilityReportModel.__table__.c.report_document.type.__class__.__name__ == (
        "JSONB"
    )
    assert R7CompatibilityReportModel.__table__.c.runtime_deployment_id.foreign_keys
    assert _has_unique_constraint(
        R7CompatibilityReportModel, "runtime_deployment_id", "report_hash"
    )

    assert R7WorkflowInstanceModel.__table__.c.workflow_document.type.__class__.__name__ == (
        "JSONB"
    )
    assert R7WorkflowInstanceModel.__table__.c.runtime_deployment_id.foreign_keys
    assert _has_unique_constraint(
        R7WorkflowInstanceModel,
        "runtime_deployment_id",
        "workflow_instance_id",
        "instance_hash",
    )

    assert R7RuntimeErrorModel.__table__.c.error_document.type.__class__.__name__ == "JSONB"
    assert R7RuntimeErrorModel.__table__.c.runtime_deployment_id.foreign_keys
    assert _has_unique_constraint(R7RuntimeErrorModel, "runtime_deployment_id", "error_id")
    assert _has_unique_constraint(R7RuntimeErrorModel, "project_id", "error_hash")

    assert R7RecoveryActionModel.__table__.c.action_document.type.__class__.__name__ == "JSONB"
    assert R7RecoveryActionModel.__table__.c.runtime_error_id.foreign_keys
    assert _has_unique_constraint(R7RecoveryActionModel, "runtime_error_id", "recovery_id")
    assert _has_unique_constraint(R7RecoveryActionModel, "project_id", "action_hash")

    assert R7DigitalTwinSnapshotModel.__table__.c.snapshot_document.type.__class__.__name__ == (
        "JSONB"
    )
    assert R7DigitalTwinSnapshotModel.__table__.c.runtime_deployment_id.foreign_keys
    assert _has_unique_constraint(
        R7DigitalTwinSnapshotModel, "runtime_deployment_id", "snapshot_hash"
    )

    assert R7RuntimeProviderModel.__table__.c.provider_document.type.__class__.__name__ == (
        "JSONB"
    )
    assert R7RuntimeProviderModel.__table__.c.project_id.foreign_keys
    assert _has_unique_constraint(
        R7RuntimeProviderModel, "project_id", "kind", "name", "version"
    )
    assert _has_unique_constraint(R7RuntimeProviderModel, "project_id", "provider_hash")

    assert R7PolicyEvaluationModel.__table__.c.evaluation_document.type.__class__.__name__ == (
        "JSONB"
    )
    assert R7PolicyEvaluationModel.__table__.c.runtime_deployment_id.foreign_keys
    assert R7PolicyEvaluationModel.__table__.c.runtime_provider_id.foreign_keys
    assert _has_unique_constraint(
        R7PolicyEvaluationModel, "runtime_deployment_id", "evaluation_id"
    )

    assert R7EventDispatchModel.__table__.c.dispatch_document.type.__class__.__name__ == (
        "JSONB"
    )
    assert R7EventDispatchModel.__table__.c.runtime_event_id.foreign_keys
    assert R7EventDispatchModel.__table__.c.runtime_provider_id.foreign_keys
    assert _has_unique_constraint(R7EventDispatchModel, "runtime_event_id", "dispatch_id")

    assert R7DeploymentRuntimeSyncModel.__table__.c.runtime_document.type.__class__.__name__ == (
        "JSONB"
    )
    assert R7DeploymentRuntimeSyncModel.__table__.c.runtime_deployment_id.foreign_keys
    assert R7DeploymentRuntimeSyncModel.__table__.c.runtime_provider_id.foreign_keys
    assert _has_unique_constraint(
        R7DeploymentRuntimeSyncModel, "runtime_deployment_id", "sync_id"
    )

    assert R7RuntimeAiRequestModel.__table__.c.request_document.type.__class__.__name__ == (
        "JSONB"
    )
    assert R7RuntimeAiRequestModel.__table__.c.policy_evaluation_id.foreign_keys
    assert _has_unique_constraint(
        R7RuntimeAiRequestModel, "runtime_deployment_id", "ai_request_id"
    )

    assert R7PluginBindingModel.__table__.c.binding_document.type.__class__.__name__ == (
        "JSONB"
    )
    assert R7PluginBindingModel.__table__.c.runtime_provider_id.foreign_keys
    assert _has_unique_constraint(R7PluginBindingModel, "runtime_deployment_id", "binding_id")

    assert (
        R7RuntimeConfigurationSnapshotModel.__table__.c.configuration_document.type.__class__.__name__
        == "JSONB"
    )
    assert R7RuntimeConfigurationSnapshotModel.__table__.c.runtime_deployment_id.foreign_keys
    assert _has_unique_constraint(
        R7RuntimeConfigurationSnapshotModel, "runtime_deployment_id", "configuration_id"
    )

    assert R7RuntimeAuditRecordModel.__table__.c.audit_document.type.__class__.__name__ == (
        "JSONB"
    )
    assert R7RuntimeAuditRecordModel.__table__.c.runtime_deployment_id.foreign_keys
    assert _has_unique_constraint(
        R7RuntimeAuditRecordModel, "runtime_deployment_id", "audit_id"
    )

    assert R7RuntimeTelemetryBatchModel.__table__.c.telemetry_document.type.__class__.__name__ == (
        "JSONB"
    )
    assert R7RuntimeTelemetryBatchModel.__table__.c.runtime_deployment_id.foreign_keys
    assert _has_unique_constraint(
        R7RuntimeTelemetryBatchModel, "runtime_deployment_id", "telemetry_id"
    )

    assert R7RuntimeGovernanceTraceModel.__table__.c.trace_document.type.__class__.__name__ == (
        "JSONB"
    )
    assert R7RuntimeGovernanceTraceModel.__table__.c.runtime_deployment_id.foreign_keys
    assert _has_unique_constraint(
        R7RuntimeGovernanceTraceModel,
        "runtime_deployment_id",
        "governance_trace_id",
    )

    assert (
        R7RuntimeSynchronizationReportModel.__table__.c.report_document.type.__class__.__name__
        == "JSONB"
    )
    assert R7RuntimeSynchronizationReportModel.__table__.c.runtime_deployment_id.foreign_keys
    assert _has_unique_constraint(
        R7RuntimeSynchronizationReportModel,
        "runtime_deployment_id",
        "synchronization_id",
    )

    assert R7RuntimeUpgradePlanModel.__table__.c.plan_document.type.__class__.__name__ == (
        "JSONB"
    )
    assert R7RuntimeUpgradePlanModel.__table__.c.runtime_deployment_id.foreign_keys
    assert R7RuntimeUpgradePlanModel.__table__.c.synchronization_report_id.foreign_keys
    assert _has_unique_constraint(
        R7RuntimeUpgradePlanModel,
        "runtime_deployment_id",
        "upgrade_plan_id",
    )


def test_r7_migration_is_linear_and_declares_append_only_runtime_records() -> None:
    migration = (
        ROOT / "migrations/versions/8d2f6a1c9b3e_add_r7_uerm_records.py"
    ).read_text(encoding="utf-8")
    registry_migration = (
        ROOT / "migrations/versions/d1f4a7c9e2b6_add_r7_runtime_registry_location.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: str | None = "7c4e2a9b8d1f"' in migration
    for table in ("r7_runtime_deployments", "r7_health_reports", "r7_runtime_events"):
        assert f'"{table}"' in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "postgresql.JSONB" in migration
    assert 'down_revision: str | None = "c8d3e7f1a9b2"' in registry_migration
    assert '"template_version"' in registry_migration
    assert '"deployment_location"' in registry_migration
    assert "DROP TRIGGER IF EXISTS prevent_r7_runtime_deployments_mutation_trigger" in (
        registry_migration
    )
    assert "jsonb_build_object" in registry_migration
    production_runtime_migration = (
        ROOT / "migrations/versions/e2a9c4f7b1d3_add_r7_production_runtime_integration.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "d1f4a7c9e2b6"' in production_runtime_migration
    for table in (
        "r7_runtime_synchronization_reports",
        "r7_runtime_upgrade_plans",
    ):
        assert f'"{table}"' in production_runtime_migration
    assert "BEFORE UPDATE OR DELETE" in production_runtime_migration

    operations_migration = (
        ROOT / "migrations/versions/9e4a7c2d5f6b_add_r7_runtime_operations.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: str | None = "8d2f6a1c9b3e"' in operations_migration
    for table in (
        "r7_compatibility_reports",
        "r7_workflow_instances",
        "r7_runtime_errors",
        "r7_recovery_actions",
        "r7_digital_twin_snapshots",
    ):
        assert f'"{table}"' in operations_migration
    assert "BEFORE UPDATE OR DELETE" in operations_migration
    assert "postgresql.JSONB" in operations_migration

    realization_migration = (
        ROOT / "migrations/versions/a6f1b8c3d9e2_add_r7_runtime_realization.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: str | None = "9e4a7c2d5f6b"' in realization_migration
    for table in (
        "r7_runtime_providers",
        "r7_policy_evaluations",
        "r7_event_dispatches",
        "r7_deployment_runtime_syncs",
        "r7_runtime_ai_requests",
        "r7_plugin_bindings",
    ):
        assert f'"{table}"' in realization_migration
    assert "BEFORE UPDATE OR DELETE" in realization_migration
    assert "postgresql.JSONB" in realization_migration

    observability_migration = (
        ROOT
        / "migrations/versions/b7c2d9e4f1a6_add_r7_runtime_observability_governance.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: str | None = "a6f1b8c3d9e2"' in observability_migration
    for table in (
        "r7_runtime_configuration_snapshots",
        "r7_runtime_audit_records",
        "r7_runtime_telemetry_batches",
        "r7_runtime_governance_traces",
    ):
        assert f'"{table}"' in observability_migration
    assert "BEFORE UPDATE OR DELETE" in observability_migration
    assert "postgresql.JSONB" in observability_migration


def test_r7_uerm_routes_are_exposed_in_openapi() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert "/api/v1/projects/{project_id}/uerm/deployments" in paths
    assert "/api/v1/projects/{project_id}/uerm/deployments/{deployment_id}" in paths
    assert (
        "/api/v1/projects/{project_id}/uerm/deployments/from-uagf-build/{build_id}"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/uerm/deployments/{deployment_id}/health-reports"
        in paths
    )
    assert "/api/v1/projects/{project_id}/uerm/deployments/{deployment_id}/events" in paths
    assert (
        paths["/api/v1/projects/{project_id}/uerm/deployments/from-uagf-build/{build_id}"][
            "post"
        ]["tags"]
        == ["r7-uerm"]
    )
    assert (
        "/api/v1/projects/{project_id}/uerm/deployments/{deployment_id}/compatibility-reports"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/uerm/deployments/{deployment_id}/workflow-instances"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/uerm/deployments/{deployment_id}/workflow-instances/{workflow_instance_id}/transitions"
        in paths
    )
    assert "/api/v1/projects/{project_id}/uerm/deployments/{deployment_id}/errors" in paths
    assert "/api/v1/projects/{project_id}/uerm/errors/{runtime_error_id}/recovery-actions" in paths
    assert (
        "/api/v1/projects/{project_id}/uerm/deployments/{deployment_id}/digital-twin-snapshots"
        in paths
    )
    assert "/api/v1/projects/{project_id}/uerm/providers" in paths
    assert (
        "/api/v1/projects/{project_id}/uerm/deployments/{deployment_id}/runtime-syncs"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/uerm/deployments/{deployment_id}/policy-evaluations"
        in paths
    )
    assert "/api/v1/projects/{project_id}/uerm/events/{runtime_event_id}/dispatches" in paths
    assert (
        "/api/v1/projects/{project_id}/uerm/deployments/{deployment_id}/ai-requests"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/uerm/deployments/{deployment_id}/plugin-bindings"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/uerm/deployments/{deployment_id}/configuration-snapshots"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/uerm/deployments/{deployment_id}/audit-records"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/uerm/deployments/{deployment_id}/telemetry-batches"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/uerm/deployments/{deployment_id}/governance-traces"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/uerm/providers/{provider_id}/readiness"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/uerm/deployments/{deployment_id}/synchronization-reports"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/uerm/synchronization-reports/{synchronization_report_id}/upgrade-plans"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/uerm/deployments/{deployment_id}/upgrade-plans"
        in paths
    )
