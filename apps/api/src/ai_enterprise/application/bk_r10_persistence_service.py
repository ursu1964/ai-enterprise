from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.audit.writer import AuditWriter
from ai_enterprise.application.bk_r10_verification_runtime import BKR10VerificationCampaign
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
from ai_enterprise.observability import increment_metric


class BKR10PersistenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_campaign(
        self,
        campaign: BKR10VerificationCampaign,
        *,
        actor_type: str,
        actor_id: str,
        action: str,
    ) -> None:
        self.session.add(_campaign_row(campaign, actor_id))
        self.session.add_all(_projection_rows(campaign, actor_id))
        _increment_metrics(campaign, action)
        await self._audit(
            f"bk_r10.verification_campaign.{action}",
            campaign.project_id,
            actor_type,
            actor_id,
            {
                "campaign_id": campaign.verification_campaign_id,
                "status": campaign.status,
                "content_hash": campaign.content_hash,
                "obligations": len(campaign.obligations),
                "results": len(campaign.results),
                "findings": len(campaign.findings),
            },
        )

    async def flush(self) -> None:
        await self.session.flush()

    async def _audit(
        self,
        event_type: str,
        project_key: str,
        actor_type: str,
        actor_id: str,
        payload: dict[str, object],
    ) -> None:
        await AuditWriter(self.session).append_event(
            stream_id=f"bk-r10:{project_key}",
            project_id=None,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            payload={"project_key": project_key, **payload},
        )


def _campaign_row(
    campaign: BKR10VerificationCampaign, actor_id: str
) -> BKR10VerificationCampaignModel:
    return BKR10VerificationCampaignModel(
        organization_key=campaign.organization_id,
        project_key=campaign.project_id,
        campaign_id=campaign.verification_campaign_id,
        implementation_result_id=campaign.implementation_result_id,
        verification_handoff_id=campaign.verification_handoff.verification_handoff_id,
        repository_revision=campaign.verification_handoff.repository_revision,
        status=campaign.status,
        criticality=campaign.criticality,
        content_hash=campaign.content_hash,
        document=campaign.model_dump(mode="json"),
        created_by=actor_id,
    )


def _projection_rows(campaign: BKR10VerificationCampaign, actor_id: str) -> list[object]:
    rows: list[object] = []
    for obligation in campaign.obligations:
        rows.append(
            BKR10VerificationObligationModel(
                organization_key=campaign.organization_id,
                project_key=campaign.project_id,
                campaign_id=campaign.verification_campaign_id,
                obligation_id=obligation.verification_obligation_id,
                requirement_id=obligation.requirement_id,
                obligation_type=obligation.obligation_type,
                method=obligation.method,
                criticality=obligation.criticality,
                mandatory=obligation.mandatory,
                status=obligation.status,
                document=obligation.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
    for procedure in campaign.procedures:
        rows.append(
            BKR10VerificationProcedureModel(
                organization_key=campaign.organization_id,
                project_key=campaign.project_id,
                campaign_id=campaign.verification_campaign_id,
                procedure_id=procedure.verification_procedure_id,
                procedure_type=procedure.procedure_type,
                content_hash=procedure.content_hash,
                document=procedure.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
    for environment in campaign.environments:
        rows.append(
            BKR10VerificationEnvironmentModel(
                organization_key=campaign.organization_id,
                project_key=campaign.project_id,
                campaign_id=campaign.verification_campaign_id,
                environment_id=environment.verification_environment_id,
                environment_type=environment.environment_type,
                environment_profile=environment.environment_profile,
                repository_revision=environment.repository_revision,
                integrity_status=environment.integrity_status,
                environment_hash=environment.environment_hash,
                document=environment.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
    for execution in campaign.executions:
        rows.append(
            BKR10VerificationExecutionModel(
                organization_key=campaign.organization_id,
                project_key=campaign.project_id,
                campaign_id=campaign.verification_campaign_id,
                execution_id=execution.verification_execution_id,
                procedure_id=execution.procedure_id,
                environment_id=execution.environment_id,
                status=execution.status,
                execution_hash=execution.execution_hash,
                document=execution.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
    for result in campaign.results:
        rows.append(
            BKR10VerificationResultModel(
                organization_key=campaign.organization_id,
                project_key=campaign.project_id,
                campaign_id=campaign.verification_campaign_id,
                result_id=result.verification_result_id,
                execution_id=result.verification_execution_id,
                verdict=result.verdict,
                content_hash=result.content_hash,
                document=result.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
    for finding in campaign.findings:
        rows.append(
            BKR10VerificationFindingModel(
                organization_key=campaign.organization_id,
                project_key=campaign.project_id,
                campaign_id=campaign.verification_campaign_id,
                finding_id=finding.finding_id,
                finding_type=finding.finding_type,
                severity=finding.severity,
                status=finding.status,
                finding_hash=finding.finding_hash,
                document=finding.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
    for waiver in campaign.waivers:
        rows.append(
            BKR10VerificationWaiverModel(
                organization_key=campaign.organization_id,
                project_key=campaign.project_id,
                campaign_id=campaign.verification_campaign_id,
                waiver_id=waiver.waiver_id,
                obligation_id=waiver.obligation_id,
                status=waiver.status,
                waiver_hash=waiver.waiver_hash,
                document=waiver.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
    if campaign.coverage is not None:
        rows.append(
            BKR10CoverageAssessmentModel(
                organization_key=campaign.organization_id,
                project_key=campaign.project_id,
                campaign_id=campaign.verification_campaign_id,
                coverage_assessment_id=campaign.coverage.coverage_assessment_id,
                coverage_hash=campaign.coverage.coverage_hash,
                document=campaign.coverage.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
    if campaign.verdict is not None:
        rows.append(
            BKR10CampaignVerdictModel(
                organization_key=campaign.organization_id,
                project_key=campaign.project_id,
                campaign_id=campaign.verification_campaign_id,
                verdict_id=campaign.verdict.verdict_id,
                final_verdict=campaign.verdict.final_verdict,
                verdict_hash=campaign.verdict.verdict_hash,
                document=campaign.verdict.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
    for recommendation in campaign.satisfaction_recommendations:
        rows.append(
            BKR10SatisfactionRecommendationModel(
                organization_key=campaign.organization_id,
                project_key=campaign.project_id,
                campaign_id=campaign.verification_campaign_id,
                recommendation_id=recommendation.satisfaction_recommendation_id,
                requirement_id=recommendation.requirement_id,
                recommendation=recommendation.recommendation,
                recommendation_hash=recommendation.recommendation_hash,
                document=recommendation.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
    for event in campaign.events:
        rows.append(
            BKR10DomainEventModel(
                organization_key=campaign.organization_id,
                project_key=campaign.project_id,
                campaign_id=campaign.verification_campaign_id,
                event_id=event.event_id,
                event_type=event.event_type,
                event_hash=event.event_hash,
                document=event.model_dump(mode="json"),
                created_by=actor_id,
            )
        )
    return rows


def _increment_metrics(campaign: BKR10VerificationCampaign, action: str) -> None:
    increment_metric(f"bk_r10_verification_campaigns_{action}_total")
    increment_metric("bk_r10_verification_obligations_total", len(campaign.obligations))
    increment_metric("bk_r10_verification_results_total", len(campaign.results))
    increment_metric("bk_r10_verification_findings_total", len(campaign.findings))
    if campaign.verdict is not None:
        increment_metric(f"bk_r10_campaign_verdict_{campaign.verdict.final_verdict.lower()}_total")
