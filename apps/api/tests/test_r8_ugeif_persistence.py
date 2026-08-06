from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ai_enterprise.api.r8_ugeif_schemas import R8GovernanceDashboardResponse
from ai_enterprise.api.routes.r8_ugeif import _maximum_predictive_risk_score
from ai_enterprise.infrastructure.knowledge.models import R8GovernanceEvolutionRecordModel
from ai_enterprise.main import app

ROOT = Path(__file__).resolve().parents[3]


def _has_unique_constraint(model: type, *columns: str) -> bool:
    expected = set(columns)
    return any(
        getattr(constraint, "columns", None) is not None
        and {column.name for column in constraint.columns} == expected
        for constraint in model.__table__.constraints
    )


def test_r8_storage_model_is_append_only_typed_governance_record_store() -> None:
    assert (
        R8GovernanceEvolutionRecordModel.__table__.c.record_document.type.__class__.__name__
        == "JSONB"
    )
    assert R8GovernanceEvolutionRecordModel.__table__.c.project_id.foreign_keys
    assert R8GovernanceEvolutionRecordModel.__table__.c.record_type.index
    assert R8GovernanceEvolutionRecordModel.__table__.c.parent_record_hash.index
    assert _has_unique_constraint(
        R8GovernanceEvolutionRecordModel,
        "project_id",
        "record_type",
        "record_id",
        "record_hash",
    )
    assert _has_unique_constraint(
        R8GovernanceEvolutionRecordModel,
        "project_id",
        "record_hash",
    )


def test_r8_migration_is_linear_and_declares_append_only_records() -> None:
    migration = (ROOT / "migrations/versions/f4b8d2a6c9e1_add_r8_ugeif_records.py").read_text(
        encoding="utf-8"
    )

    assert 'down_revision: str | None = "e2a9c4f7b1d3"' in migration
    assert '"r8_governance_evolution_records"' in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "postgresql.JSONB" in migration


def test_r8_ugeif_routes_are_exposed_in_openapi() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert "/api/v1/projects/{project_id}/ugeif/governance-assessments" in paths
    assert "/api/v1/projects/{project_id}/ugeif/validation-reports" in paths
    assert "/api/v1/projects/{project_id}/ugeif/change-proposals" in paths
    assert (
        "/api/v1/projects/{project_id}/ugeif/change-proposals/{proposal_record_id}/decisions"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/ugeif/change-proposals/{proposal_record_id}/impact-analyses"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/ugeif/change-proposals/{proposal_record_id}/simulations"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/ugeif/change-proposals/{proposal_record_id}/risk-profiles"
        in paths
    )
    assert "/api/v1/projects/{project_id}/ugeif/quality-scorecards" in paths
    assert "/api/v1/projects/{project_id}/ugeif/recommendations" in paths
    assert "/api/v1/projects/{project_id}/ugeif/feedback-loop-records" in paths
    assert "/api/v1/projects/{project_id}/ugeif/version-graph-snapshots" in paths
    assert "/api/v1/projects/{project_id}/ugeif/timeline-entries" in paths
    assert "/api/v1/projects/{project_id}/ugeif/certifications" in paths
    assert "/api/v1/projects/{project_id}/ugeif/reusable-patterns" in paths
    assert "/api/v1/projects/{project_id}/ugeif/knowledge-generalizations" in paths
    assert "/api/v1/projects/{project_id}/ugeif/industry-framework-packs" in paths
    assert "/api/v1/projects/{project_id}/ugeif/compliance-framework-packs" in paths
    assert "/api/v1/projects/{project_id}/ugeif/marketplace-certifications" in paths
    assert "/api/v1/projects/{project_id}/ugeif/predictive-analyses" in paths
    assert "/api/v1/projects/{project_id}/ugeif/ai-learning-boundaries" in paths
    assert "/api/v1/projects/{project_id}/ugeif/federated-governance-syncs" in paths
    assert "/api/v1/projects/{project_id}/ugeif/technology-evolution-plans" in paths
    assert "/api/v1/projects/{project_id}/ugeif/records" in paths
    assert "/api/v1/projects/{project_id}/ugeif/dashboard" in paths
    assert (
        paths["/api/v1/projects/{project_id}/ugeif/change-proposals"]["post"]["tags"]
        == ["r8-ugeif"]
    )


def test_r8_dashboard_response_exposes_deeper_governance_metrics() -> None:
    schema = R8GovernanceDashboardResponse(
        project_id="00000000-0000-0000-0000-000000000001",
        latest_governance_status="passing",
        latest_validation_status="passing",
        latest_quality_status="needs_attention",
        latest_certification_status="certified",
        open_recommendation_count=2,
        feedback_loop_count=3,
        pending_approval_count=1,
        timeline_entry_count=3,
        reusable_pattern_count=4,
        knowledge_generalization_count=5,
        industry_framework_pack_count=6,
        compliance_framework_pack_count=7,
        certified_marketplace_asset_count=8,
        predictive_analysis_count=9,
        maximum_predictive_risk_score=72.5,
        approved_ai_learning_source_count=10,
        denied_ai_learning_source_count=11,
        federated_governance_sync_count=12,
        federated_sync_attention_required_count=1,
        technology_evolution_plan_count=13,
    )

    assert schema.maximum_predictive_risk_score == 72.5
    assert schema.feedback_loop_count == 3
    assert schema.certified_marketplace_asset_count == 8
    assert schema.approved_ai_learning_source_count == 10
    assert schema.federated_sync_attention_required_count == 1
    assert schema.technology_evolution_plan_count == 13


def test_r8_dashboard_derives_maximum_predictive_risk_score() -> None:
    rows = [
        R8GovernanceEvolutionRecordModel(
            id="00000000-0000-0000-0000-000000000001",
            project_id="00000000-0000-0000-0000-000000000010",
            record_type="predictive_analysis",
            record_id="UGEIF-PRED-0001",
            status="recorded",
            lifecycle_state=None,
            approval_status=None,
            parent_record_hash=None,
            record_document={"risk_score": 45.0},
            record_hash="a" * 64,
            created_by="tester",
        ),
        R8GovernanceEvolutionRecordModel(
            id="00000000-0000-0000-0000-000000000002",
            project_id="00000000-0000-0000-0000-000000000010",
            record_type="predictive_analysis",
            record_id="UGEIF-PRED-0002",
            status="recorded",
            lifecycle_state=None,
            approval_status=None,
            parent_record_hash=None,
            record_document={"risk_score": 81.0},
            record_hash="b" * 64,
            created_by="tester",
        ),
    ]

    assert _maximum_predictive_risk_score(rows) == 81.0
