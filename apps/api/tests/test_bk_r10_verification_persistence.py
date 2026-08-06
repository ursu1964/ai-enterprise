from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.dialects.postgresql import JSONB

from ai_enterprise.application.bk_r10_persistence_service import BKR10PersistenceService
from ai_enterprise.application.bk_r10_verification_runtime import (
    bk_r10_generate_satisfaction_recommendations,
    bk_r10_generate_verdict,
    bk_r10_perform_coverage_assessment,
    bk_r10_record_result,
    bk_r10_start_campaign,
)
from ai_enterprise.infrastructure.bk_r10.models import (
    BKR10CampaignVerdictModel,
    BKR10CoverageAssessmentModel,
    BKR10DomainEventModel,
    BKR10SatisfactionRecommendationModel,
    BKR10VerificationCampaignModel,
    BKR10VerificationEnvironmentModel,
    BKR10VerificationExecutionModel,
    BKR10VerificationFindingModel,
    BKR10VerificationObligationModel,
    BKR10VerificationProcedureModel,
    BKR10VerificationResultModel,
    BKR10VerificationWaiverModel,
)
from ai_enterprise.observability import metrics_snapshot
from tests.test_bk_r10_verification_runtime import _actor, _qualified

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "migrations" / "versions" / "f8a6c2d4e9b1_add_bk_r10_verification_records.py"


def test_bk_r10_persistence_models_use_jsonb_documents_and_query_indexes() -> None:
    models = (
        BKR10VerificationCampaignModel,
        BKR10VerificationObligationModel,
        BKR10VerificationProcedureModel,
        BKR10VerificationEnvironmentModel,
        BKR10VerificationExecutionModel,
        BKR10VerificationResultModel,
        BKR10VerificationFindingModel,
        BKR10VerificationWaiverModel,
        BKR10CoverageAssessmentModel,
        BKR10CampaignVerdictModel,
        BKR10SatisfactionRecommendationModel,
        BKR10DomainEventModel,
    )

    for model in models:
        assert isinstance(model.__table__.c.document.type, JSONB)
        assert any(index.name.endswith("project_key") for index in model.__table__.indexes)


def test_bk_r10_migration_chains_after_r22_and_creates_append_only_tables() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'down_revision: str | None = "e7f9a3b2d1c5"' in source
    assert "bk_r10_verification_campaigns" in source
    assert "bk_r10_satisfaction_recommendations" in source
    assert "CREATE TRIGGER prevent_{table_name}_mutation_trigger" in source


class BKR10PersistenceSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.audit_records: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)

    def add_all(self, values: list[object]) -> None:
        self.added.extend(values)
        if len(values) == 2 and values[1].__class__.__name__ == "AuditChainRecordModel":
            self.audit_records.append(values[1])

    async def scalar(self, _statement: object) -> object | None:
        return self.audit_records[-1] if self.audit_records else None

    async def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_bk_r10_persistence_service_records_projection_audit_and_metrics() -> None:
    campaign = bk_r10_start_campaign(_qualified(), actor=_actor("verification-owner"))
    campaign = bk_r10_record_result(
        campaign,
        procedure_id="proc-api-contract",
        environment_id="env-ci",
        executor=_actor("independent-verifier"),
        obligation_results=(
            {
                "verification_obligation_id": "obl-req-api-001",
                "status": "PASSED",
                "evidence_references": ("evidence://test-report/api-contract",),
            },
        ),
        raw_evidence_references=("evidence://raw/pytest",),
    )
    campaign = bk_r10_perform_coverage_assessment(campaign, actor=_actor("verification-owner"))
    campaign = bk_r10_generate_verdict(campaign, actor=_actor("verification-owner"))
    campaign = bk_r10_generate_satisfaction_recommendations(
        campaign,
        actor=_actor("verification-owner"),
    )
    session = BKR10PersistenceSession()
    before = metrics_snapshot()

    service = BKR10PersistenceService(session)  # type: ignore[arg-type]
    await service.record_campaign(
        campaign,
        actor_type="human",
        actor_id="verification-owner",
        action="completed",
    )

    assert any(isinstance(item, BKR10VerificationCampaignModel) for item in session.added)
    assert any(isinstance(item, BKR10VerificationObligationModel) for item in session.added)
    assert any(isinstance(item, BKR10VerificationEnvironmentModel) for item in session.added)
    assert any(isinstance(item, BKR10VerificationExecutionModel) for item in session.added)
    assert any(isinstance(item, BKR10VerificationResultModel) for item in session.added)
    assert any(isinstance(item, BKR10CoverageAssessmentModel) for item in session.added)
    assert any(isinstance(item, BKR10CampaignVerdictModel) for item in session.added)
    assert any(isinstance(item, BKR10SatisfactionRecommendationModel) for item in session.added)
    assert any(isinstance(item, BKR10DomainEventModel) for item in session.added)
    assert any(
        item.event_type == "bk_r10.verification_campaign.completed"
        for item in session.added
        if item.__class__.__name__ == "AuditEventModel"
    )
    after = metrics_snapshot()
    assert after["bk_r10_verification_campaigns_completed_total"] >= (
        before.get("bk_r10_verification_campaigns_completed_total", 0) + 1
    )
