from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ai_enterprise.infrastructure.knowledge.models import (
    R5ArtifactSpecModel,
    R5ExportBundleModel,
    R5GeneratedArtifactModel,
    R5TransformationRunModel,
    R5VerificationReportModel,
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


def test_r5_storage_models_cover_umte_run_artifacts_and_verification() -> None:
    assert R5TransformationRunModel.__table__.c.plan_document.type.__class__.__name__ == "JSONB"
    assert R5TransformationRunModel.__table__.c.result_document.type.__class__.__name__ == "JSONB"
    assert R5TransformationRunModel.__table__.c.model_version_id.foreign_keys
    assert R5TransformationRunModel.__table__.c.snapshot_row_id.foreign_keys
    assert _has_unique_constraint(R5TransformationRunModel, "project_id", "run_hash")
    assert _has_unique_constraint(R5TransformationRunModel, "project_id", "plan_hash")

    assert R5ArtifactSpecModel.__table__.c.artifact_document.type.__class__.__name__ == "JSONB"
    assert R5ArtifactSpecModel.__table__.c.provenance_document.type.__class__.__name__ == "JSONB"
    assert R5ArtifactSpecModel.__table__.c.transformation_run_id.foreign_keys
    assert _has_unique_constraint(R5ArtifactSpecModel, "transformation_run_id", "artifact_key")
    assert _has_unique_constraint(R5ArtifactSpecModel, "project_id", "artifact_spec_hash")

    assert R5GeneratedArtifactModel.__table__.c.content_document.type.__class__.__name__ == "JSONB"
    assert R5GeneratedArtifactModel.__table__.c.transformation_run_id.foreign_keys
    assert _has_unique_constraint(R5GeneratedArtifactModel, "transformation_run_id", "artifact_key")
    assert _has_unique_constraint(R5GeneratedArtifactModel, "project_id", "generated_hash")

    assert R5ExportBundleModel.__table__.c.bundle_document.type.__class__.__name__ == "JSONB"
    assert R5ExportBundleModel.__table__.c.transformation_run_id.foreign_keys
    assert _has_unique_constraint(R5ExportBundleModel, "transformation_run_id")
    assert _has_unique_constraint(R5ExportBundleModel, "project_id", "bundle_hash")

    assert R5VerificationReportModel.__table__.c.report_document.type.__class__.__name__ == "JSONB"
    assert R5VerificationReportModel.__table__.c.report_hash.unique
    assert R5VerificationReportModel.__table__.c.transformation_run_id.foreign_keys
    assert _has_unique_constraint(R5VerificationReportModel, "transformation_run_id")


def test_r5_migration_is_linear_and_declares_append_only_umte_records() -> None:
    migration = (
        ROOT / "migrations/versions/3c8d1e4f6a7b_add_r5_umte_records.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: str | None = "2b7e9f0a1c3d"' in migration
    for table in (
        "r5_transformation_runs",
        "r5_artifact_specs",
        "r5_verification_reports",
    ):
        assert f'"{table}"' in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "postgresql.JSONB" in migration

    generated_migration = (
        ROOT / "migrations/versions/4d9e2f7a6b1c_add_r5_generated_artifacts.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "3c8d1e4f6a7b"' in generated_migration
    assert '"r5_generated_artifacts"' in generated_migration
    assert "BEFORE UPDATE OR DELETE" in generated_migration
    assert "postgresql.JSONB" in generated_migration

    export_migration = (
        ROOT / "migrations/versions/5e1a9c8d2f4b_add_r5_export_bundles.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "4d9e2f7a6b1c"' in export_migration
    assert '"r5_export_bundles"' in export_migration
    assert "BEFORE UPDATE OR DELETE" in export_migration
    assert "postgresql.JSONB" in export_migration


def test_r5_umte_routes_are_exposed_in_openapi() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert "/api/v1/projects/{project_id}/umte/transformations" in paths
    assert "/api/v1/projects/{project_id}/umte/transformations/{run_id}" in paths
    assert (
        "/api/v1/projects/{project_id}/umte/transformations/{run_id}/export-bundle"
        in paths
    )
    assert (
        paths["/api/v1/projects/{project_id}/umte/transformations"]["post"]["tags"]
        == ["r5-umte"]
    )
