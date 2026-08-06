from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from ai_enterprise.api.dependencies import ActorDependency, SessionDependency
from ai_enterprise.api.r8_ugeif_schemas import (
    R8AiLearningBoundaryRequest,
    R8CertificationRequest,
    R8ChangeProposalRequest,
    R8ComplianceFrameworkPackRequest,
    R8FederatedGovernanceSyncRequest,
    R8FeedbackLoopRecordRequest,
    R8GovernanceAssessmentRequest,
    R8GovernanceDashboardResponse,
    R8HumanDecisionRequest,
    R8ImpactAnalysisRequest,
    R8IndustryFrameworkPackRequest,
    R8KnowledgeGeneralizationRequest,
    R8MarketplaceAssetCertificationRequest,
    R8OperationalRecommendationRequest,
    R8PredictiveAnalysisRequest,
    R8QualityScorecardRequest,
    R8RecordResponse,
    R8ReusablePatternRequest,
    R8RiskProfileRequest,
    R8SimulationReportRequest,
    R8TechnologyEvolutionPlanRequest,
    R8TimelineEntryRequest,
    R8ValidationReportRequest,
    R8VersionGraphRequest,
)
from ai_enterprise.domain.r8_ugeif import (
    UgeifAssetKind,
    UgeifChangeProposal,
    UgeifChangeType,
    UgeifLearningSourceStatus,
    ai_learning_boundary,
    certification,
    change_proposal,
    compliance_framework_pack,
    decide_change_proposal,
    federated_governance_sync,
    feedback_loop_record,
    governance_assessment,
    impact_analysis,
    industry_framework_pack,
    knowledge_generalization,
    marketplace_asset_certification,
    operational_recommendation,
    predictive_analysis,
    quality_scorecard,
    reusable_pattern,
    risk_profile,
    simulation_report,
    technology_evolution_plan,
    timeline_entry,
    validation_report,
    version_graph_snapshot,
)
from ai_enterprise.infrastructure.database.models import ProjectModel
from ai_enterprise.infrastructure.knowledge.models import R8GovernanceEvolutionRecordModel

router = APIRouter(prefix="/projects", tags=["r8-ugeif"])


def _require_human(actor: object) -> None:
    if getattr(actor, "actor_type", None) != "human":
        raise HTTPException(status_code=403, detail="Human governance authority is required")


@router.post(
    "/{project_id}/ugeif/governance-assessments",
    response_model=R8RecordResponse,
    status_code=201,
)
async def record_ugeif_governance_assessment(
    project_id: uuid.UUID,
    request: R8GovernanceAssessmentRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = governance_assessment(
        index=(await _record_count(session, project_id, "governance_assessment")) + 1,
        project_id=str(project_id),
        manifest_version=request.manifest_version,
        scores=request.scores,
        recommendations=tuple(request.recommendations),
    )
    row = _row(project_id, "governance_assessment", value, actor.subject)
    session.add(row)
    await session.commit()
    return R8RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ugeif/validation-reports",
    response_model=R8RecordResponse,
    status_code=201,
)
async def record_ugeif_validation_report(
    project_id: uuid.UUID,
    request: R8ValidationReportRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = validation_report(
        index=(await _record_count(session, project_id, "validation_report")) + 1,
        project_id=str(project_id),
        manifest_version=request.manifest_version,
        findings_by_category={
            category: tuple(findings)
            for category, findings in request.findings_by_category.items()
        },
    )
    row = _row(project_id, "validation_report", value, actor.subject)
    session.add(row)
    await session.commit()
    return R8RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ugeif/change-proposals",
    response_model=R8RecordResponse,
    status_code=201,
)
async def propose_ugeif_change(
    project_id: uuid.UUID,
    request: R8ChangeProposalRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = change_proposal(
        index=(await _record_count(session, project_id, "change_proposal")) + 1,
        project_id=str(project_id),
        change_type=UgeifChangeType(request.change_type),
        title=request.title,
        intent_ref=request.intent_ref,
        current_manifest_version=request.current_manifest_version,
        proposed_manifest_version=request.proposed_manifest_version,
        evidence_hashes=tuple(request.evidence_hashes),
    )
    row = _row(project_id, "change_proposal", value, actor.subject)
    session.add(row)
    await session.commit()
    return R8RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ugeif/change-proposals/{proposal_record_id}/decisions",
    response_model=R8RecordResponse,
    status_code=201,
)
async def decide_ugeif_change(
    project_id: uuid.UUID,
    proposal_record_id: uuid.UUID,
    request: R8HumanDecisionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8RecordResponse:
    _require_human(actor)
    current = await _record(session, project_id, proposal_record_id, "change_proposal")
    value = decide_change_proposal(
        UgeifChangeProposal.model_validate(current.record_document),
        approved=request.decision == "approve",
    )
    document = value.model_dump(mode="json") | {
        "human_decision": {
            "decision": request.decision,
            "rationale": request.rationale,
            "decided_by": actor.subject,
        }
    }
    row = _row(
        project_id,
        "change_proposal",
        value,
        actor.subject,
        parent_record_hash=current.record_hash,
        document_override=document,
    )
    session.add(row)
    await session.commit()
    return R8RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ugeif/change-proposals/{proposal_record_id}/impact-analyses",
    response_model=R8RecordResponse,
    status_code=201,
)
async def record_ugeif_impact_analysis(
    project_id: uuid.UUID,
    proposal_record_id: uuid.UUID,
    request: R8ImpactAnalysisRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8RecordResponse:
    _require_human(actor)
    proposal = await _record(session, project_id, proposal_record_id, "change_proposal")
    value = impact_analysis(
        index=(await _record_count(session, project_id, "impact_analysis")) + 1,
        proposal_hash=proposal.record_hash,
        affected_artifacts=tuple(request.affected_artifacts),
        affected_dependencies=tuple(request.affected_dependencies),
        affected_workflows=tuple(request.affected_workflows),
        affected_permissions=tuple(request.affected_permissions),
        affected_documentation=tuple(request.affected_documentation),
    )
    row = _row(project_id, "impact_analysis", value, actor.subject, proposal.record_hash)
    session.add(row)
    await session.commit()
    return R8RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ugeif/change-proposals/{proposal_record_id}/simulations",
    response_model=R8RecordResponse,
    status_code=201,
)
async def record_ugeif_simulation(
    project_id: uuid.UUID,
    proposal_record_id: uuid.UUID,
    request: R8SimulationReportRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8RecordResponse:
    _require_human(actor)
    proposal = await _record(session, project_id, proposal_record_id, "change_proposal")
    impact = await _record(session, project_id, request.impact_analysis_id, "impact_analysis")
    if impact.parent_record_hash != proposal.record_hash:
        raise HTTPException(status_code=409, detail="Impact analysis does not belong to proposal")
    value = simulation_report(
        index=(await _record_count(session, project_id, "simulation_report")) + 1,
        proposal_hash=proposal.record_hash,
        impact_hash=impact.record_hash,
        checks=request.checks,
    )
    row = _row(project_id, "simulation_report", value, actor.subject, proposal.record_hash)
    session.add(row)
    await session.commit()
    return R8RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ugeif/change-proposals/{proposal_record_id}/risk-profiles",
    response_model=R8RecordResponse,
    status_code=201,
)
async def record_ugeif_risk_profile(
    project_id: uuid.UUID,
    proposal_record_id: uuid.UUID,
    request: R8RiskProfileRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8RecordResponse:
    _require_human(actor)
    proposal = await _record(session, project_id, proposal_record_id, "change_proposal")
    value = risk_profile(
        index=(await _record_count(session, project_id, "risk_profile")) + 1,
        proposal_hash=proposal.record_hash,
        dimensions=request.dimensions,
    )
    row = _row(project_id, "risk_profile", value, actor.subject, proposal.record_hash)
    session.add(row)
    await session.commit()
    return R8RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ugeif/quality-scorecards",
    response_model=R8RecordResponse,
    status_code=201,
)
async def record_ugeif_quality_scorecard(
    project_id: uuid.UUID,
    request: R8QualityScorecardRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = quality_scorecard(
        index=(await _record_count(session, project_id, "quality_scorecard")) + 1,
        project_id=str(project_id),
        scores=request.scores,
        deployment_hash=request.deployment_hash,
    )
    row = _row(project_id, "quality_scorecard", value, actor.subject)
    session.add(row)
    await session.commit()
    return R8RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ugeif/recommendations",
    response_model=R8RecordResponse,
    status_code=201,
)
async def record_ugeif_operational_recommendation(
    project_id: uuid.UUID,
    request: R8OperationalRecommendationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = operational_recommendation(
        index=(await _record_count(session, project_id, "operational_recommendation")) + 1,
        project_id=str(project_id),
        source_hash=request.source_hash,
        category=request.category,
        recommendation=request.recommendation,
    )
    row = _row(project_id, "operational_recommendation", value, actor.subject)
    session.add(row)
    await session.commit()
    return R8RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ugeif/feedback-loop-records",
    response_model=R8RecordResponse,
    status_code=201,
)
async def record_ugeif_feedback_loop(
    project_id: uuid.UUID,
    request: R8FeedbackLoopRecordRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = feedback_loop_record(
        index=(await _record_count(session, project_id, "feedback_loop_record")) + 1,
        project_id=str(project_id),
        runtime_source_hash=request.runtime_source_hash,
        metrics=request.metrics,
        analytics=tuple(request.analytics),
        recommendation_refs=tuple(request.recommendation_refs),
    )
    row = _row(project_id, "feedback_loop_record", value, actor.subject)
    session.add(row)
    await session.commit()
    return R8RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ugeif/version-graph-snapshots",
    response_model=R8RecordResponse,
    status_code=201,
)
async def record_ugeif_version_graph(
    project_id: uuid.UUID,
    request: R8VersionGraphRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = version_graph_snapshot(
        index=(await _record_count(session, project_id, "version_graph_snapshot")) + 1,
        project_id=str(project_id),
        nodes=tuple(request.nodes),
        edges=tuple(request.edges),
    )
    row = _row(project_id, "version_graph_snapshot", value, actor.subject)
    session.add(row)
    await session.commit()
    return R8RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ugeif/timeline-entries",
    response_model=R8RecordResponse,
    status_code=201,
)
async def record_ugeif_timeline_entry(
    project_id: uuid.UUID,
    request: R8TimelineEntryRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = timeline_entry(
        index=(await _record_count(session, project_id, "timeline_entry")) + 1,
        project_id=str(project_id),
        sequence=(await _record_count(session, project_id, "timeline_entry")) + 1,
        event_type=request.event_type,
        object_ref=request.object_ref,
        object_hash=request.object_hash,
    )
    row = _row(project_id, "timeline_entry", value, actor.subject)
    session.add(row)
    await session.commit()
    return R8RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ugeif/certifications",
    response_model=R8RecordResponse,
    status_code=201,
)
async def record_ugeif_certification(
    project_id: uuid.UUID,
    request: R8CertificationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = certification(
        index=(await _record_count(session, project_id, "certification")) + 1,
        project_id=str(project_id),
        deployment_hash=request.deployment_hash,
        checks=request.checks,
        evidence_hashes=tuple(request.evidence_hashes),
    )
    row = _row(project_id, "certification", value, actor.subject)
    session.add(row)
    await session.commit()
    return R8RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ugeif/reusable-patterns",
    response_model=R8RecordResponse,
    status_code=201,
)
async def record_ugeif_reusable_pattern(
    project_id: uuid.UUID,
    request: R8ReusablePatternRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = reusable_pattern(
        index=(await _record_count(session, project_id, "reusable_pattern")) + 1,
        organization_id=request.organization_id,
        pattern_name=request.pattern_name,
        pattern_type=request.pattern_type,
        occurrence_refs=tuple(request.occurrence_refs),
        evidence_hashes=tuple(request.evidence_hashes),
        generalized_document=request.generalized_document,
    )
    row = _row(project_id, "reusable_pattern", value, actor.subject)
    session.add(row)
    await session.commit()
    return R8RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ugeif/knowledge-generalizations",
    response_model=R8RecordResponse,
    status_code=201,
)
async def record_ugeif_knowledge_generalization(
    project_id: uuid.UUID,
    request: R8KnowledgeGeneralizationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = knowledge_generalization(
        index=(await _record_count(session, project_id, "knowledge_generalization")) + 1,
        organization_id=request.organization_id,
        source_project_ids=tuple(request.source_project_ids),
        category=request.category,
        reusable_asset_ref=request.reusable_asset_ref,
        source_evidence_hashes=tuple(request.source_evidence_hashes),
        generalized_document=request.generalized_document,
        redaction_policy=request.redaction_policy,
        client_isolation_verified=request.client_isolation_verified,
    )
    row = _row(project_id, "knowledge_generalization", value, actor.subject)
    session.add(row)
    await session.commit()
    return R8RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ugeif/industry-framework-packs",
    response_model=R8RecordResponse,
    status_code=201,
)
async def record_ugeif_industry_framework_pack(
    project_id: uuid.UUID,
    request: R8IndustryFrameworkPackRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = industry_framework_pack(
        index=(await _record_count(session, project_id, "industry_framework_pack")) + 1,
        industry=request.industry,
        version=request.version,
        manifest_templates=tuple(request.manifest_templates),
        registry_extensions=tuple(request.registry_extensions),
        governance_policies=tuple(request.governance_policies),
        compliance_mappings=tuple(request.compliance_mappings),
        artifact_templates=tuple(request.artifact_templates),
    )
    row = _row(project_id, "industry_framework_pack", value, actor.subject)
    session.add(row)
    await session.commit()
    return R8RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ugeif/compliance-framework-packs",
    response_model=R8RecordResponse,
    status_code=201,
)
async def record_ugeif_compliance_framework_pack(
    project_id: uuid.UUID,
    request: R8ComplianceFrameworkPackRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = compliance_framework_pack(
        index=(await _record_count(session, project_id, "compliance_framework_pack")) + 1,
        framework=request.framework,
        version=request.version,
        controls=tuple(request.controls),
        audit_evidence_mappings=tuple(request.audit_evidence_mappings),
        validation_rules=tuple(request.validation_rules),
        documentation_templates=tuple(request.documentation_templates),
    )
    row = _row(project_id, "compliance_framework_pack", value, actor.subject)
    session.add(row)
    await session.commit()
    return R8RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ugeif/marketplace-certifications",
    response_model=R8RecordResponse,
    status_code=201,
)
async def record_ugeif_marketplace_certification(
    project_id: uuid.UUID,
    request: R8MarketplaceAssetCertificationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = marketplace_asset_certification(
        index=(await _record_count(session, project_id, "marketplace_certification")) + 1,
        asset_kind=UgeifAssetKind(request.asset_kind),
        asset_ref=request.asset_ref,
        asset_version=request.asset_version,
        asset_hash=request.asset_hash,
        signer_ref=request.signer_ref,
        signature_ref=request.signature_ref,
        signature_algorithm=request.signature_algorithm,
        checks=request.checks,
    )
    row = _row(project_id, "marketplace_certification", value, actor.subject)
    session.add(row)
    await session.commit()
    return R8RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ugeif/predictive-analyses",
    response_model=R8RecordResponse,
    status_code=201,
)
async def record_ugeif_predictive_analysis(
    project_id: uuid.UUID,
    request: R8PredictiveAnalysisRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = predictive_analysis(
        index=(await _record_count(session, project_id, "predictive_analysis")) + 1,
        project_id=str(project_id),
        prediction_type=request.prediction_type,
        signals=request.signals,
        planning_recommendation=request.planning_recommendation,
    )
    row = _row(project_id, "predictive_analysis", value, actor.subject)
    session.add(row)
    await session.commit()
    return R8RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ugeif/ai-learning-boundaries",
    response_model=R8RecordResponse,
    status_code=201,
)
async def record_ugeif_ai_learning_boundary(
    project_id: uuid.UUID,
    request: R8AiLearningBoundaryRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = ai_learning_boundary(
        index=(await _record_count(session, project_id, "ai_learning_boundary")) + 1,
        source_ref=request.source_ref,
        source_type=request.source_type,
        status=UgeifLearningSourceStatus(request.status),
        allowed_uses=tuple(request.allowed_uses),
        prohibited_uses=tuple(request.prohibited_uses),
        evidence_hashes=tuple(request.evidence_hashes),
    )
    row = _row(project_id, "ai_learning_boundary", value, actor.subject)
    session.add(row)
    await session.commit()
    return R8RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ugeif/federated-governance-syncs",
    response_model=R8RecordResponse,
    status_code=201,
)
async def record_ugeif_federated_governance_sync(
    project_id: uuid.UUID,
    request: R8FederatedGovernanceSyncRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = federated_governance_sync(
        index=(await _record_count(session, project_id, "federated_governance_sync")) + 1,
        organization_id=request.organization_id,
        portfolio_ref=request.portfolio_ref,
        project_refs=tuple(request.project_refs),
        shared_asset_refs=tuple(request.shared_asset_refs),
        governance_policy_refs=tuple(request.governance_policy_refs),
        checks=request.checks,
    )
    row = _row(project_id, "federated_governance_sync", value, actor.subject)
    session.add(row)
    await session.commit()
    return R8RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ugeif/technology-evolution-plans",
    response_model=R8RecordResponse,
    status_code=201,
)
async def record_ugeif_technology_evolution_plan(
    project_id: uuid.UUID,
    request: R8TechnologyEvolutionPlanRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = technology_evolution_plan(
        index=(await _record_count(session, project_id, "technology_evolution_plan")) + 1,
        project_id=str(project_id),
        manifest_version=request.manifest_version,
        approved_proposal_hash=request.approved_proposal_hash,
        current_technology=request.current_technology,
        target_technology=request.target_technology,
        migration_plan_refs=tuple(request.migration_plan_refs),
        business_intent_ref=request.business_intent_ref,
        simulation_hashes=tuple(request.simulation_hashes),
        certification_hashes=tuple(request.certification_hashes),
    )
    row = _row(project_id, "technology_evolution_plan", value, actor.subject)
    session.add(row)
    await session.commit()
    return R8RecordResponse.model_validate(row)


@router.get("/{project_id}/ugeif/records", response_model=list[R8RecordResponse])
async def list_ugeif_records(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
    record_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[R8RecordResponse]:
    _require_human(actor)
    await _project(session, project_id)
    query = select(R8GovernanceEvolutionRecordModel).where(
        R8GovernanceEvolutionRecordModel.project_id == project_id
    )
    if record_type is not None:
        query = query.where(R8GovernanceEvolutionRecordModel.record_type == record_type)
    rows = (
        await session.scalars(
            query.order_by(R8GovernanceEvolutionRecordModel.created_at.desc()).limit(limit)
        )
    ).all()
    return [R8RecordResponse.model_validate(row) for row in rows]


@router.get("/{project_id}/ugeif/dashboard", response_model=R8GovernanceDashboardResponse)
async def ugeif_governance_dashboard(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R8GovernanceDashboardResponse:
    _require_human(actor)
    await _project(session, project_id)
    rows = (
        await session.scalars(
            select(R8GovernanceEvolutionRecordModel)
            .where(R8GovernanceEvolutionRecordModel.project_id == project_id)
            .order_by(R8GovernanceEvolutionRecordModel.created_at.desc())
        )
    ).all()
    return R8GovernanceDashboardResponse(
        project_id=project_id,
        latest_governance_status=_latest_status(rows, "governance_assessment"),
        latest_validation_status=_latest_status(rows, "validation_report"),
        latest_quality_status=_latest_status(rows, "quality_scorecard"),
        latest_certification_status=_latest_status(rows, "certification"),
        open_recommendation_count=sum(
            1 for row in rows if row.record_type == "operational_recommendation"
        ),
        feedback_loop_count=sum(1 for row in rows if row.record_type == "feedback_loop_record"),
        pending_approval_count=sum(
            1 for row in rows if row.approval_status == "required"
        ),
        timeline_entry_count=sum(1 for row in rows if row.record_type == "timeline_entry"),
        reusable_pattern_count=sum(1 for row in rows if row.record_type == "reusable_pattern"),
        knowledge_generalization_count=sum(
            1 for row in rows if row.record_type == "knowledge_generalization"
        ),
        industry_framework_pack_count=sum(
            1 for row in rows if row.record_type == "industry_framework_pack"
        ),
        compliance_framework_pack_count=sum(
            1 for row in rows if row.record_type == "compliance_framework_pack"
        ),
        certified_marketplace_asset_count=sum(
            1
            for row in rows
            if row.record_type == "marketplace_certification" and row.status == "certified"
        ),
        predictive_analysis_count=sum(
            1 for row in rows if row.record_type == "predictive_analysis"
        ),
        maximum_predictive_risk_score=_maximum_predictive_risk_score(rows),
        approved_ai_learning_source_count=sum(
            1
            for row in rows
            if row.record_type == "ai_learning_boundary" and row.status == "approved"
        ),
        denied_ai_learning_source_count=sum(
            1
            for row in rows
            if row.record_type == "ai_learning_boundary" and row.status == "denied"
        ),
        federated_governance_sync_count=sum(
            1 for row in rows if row.record_type == "federated_governance_sync"
        ),
        federated_sync_attention_required_count=sum(
            1
            for row in rows
            if row.record_type == "federated_governance_sync"
            and row.status == "attention_required"
        ),
        technology_evolution_plan_count=sum(
            1 for row in rows if row.record_type == "technology_evolution_plan"
        ),
    )


async def _project(session: object, project_id: uuid.UUID) -> ProjectModel:
    project = await session.get(ProjectModel, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _record_count(session: object, project_id: uuid.UUID, record_type: str) -> int:
    return len(
        (
            await session.scalars(
                select(R8GovernanceEvolutionRecordModel).where(
                    R8GovernanceEvolutionRecordModel.project_id == project_id,
                    R8GovernanceEvolutionRecordModel.record_type == record_type,
                )
            )
        ).all()
    )


async def _record(
    session: object,
    project_id: uuid.UUID,
    record_id: uuid.UUID,
    record_type: str,
) -> R8GovernanceEvolutionRecordModel:
    await _project(session, project_id)
    row = await session.get(R8GovernanceEvolutionRecordModel, record_id)
    if row is None or row.project_id != project_id or row.record_type != record_type:
        raise HTTPException(status_code=404, detail="UGEIF record not found")
    return row


def _row(
    project_id: uuid.UUID,
    record_type: str,
    value: object,
    created_by: str,
    parent_record_hash: str | None = None,
    document_override: dict[str, Any] | None = None,
) -> R8GovernanceEvolutionRecordModel:
    document = (
        document_override
        if document_override is not None
        else value.model_dump(mode="json")  # type: ignore[attr-defined]
    )
    return R8GovernanceEvolutionRecordModel(
        id=uuid.uuid4(),
        project_id=project_id,
        record_type=record_type,
        record_id=_document_record_id(document),
        status=_document_status(document),
        lifecycle_state=document.get("lifecycle_state"),
        approval_status=document.get("approval_status"),
        parent_record_hash=parent_record_hash,
        record_document=document,
        record_hash=_document_hash(document),
        created_by=created_by,
    )


def _document_record_id(document: dict[str, Any]) -> str:
    for key in (
        "assessment_id",
        "validation_id",
        "proposal_id",
        "impact_id",
        "simulation_id",
        "risk_id",
        "scorecard_id",
        "recommendation_id",
        "feedback_id",
        "graph_id",
        "timeline_id",
        "certification_id",
        "pattern_id",
        "knowledge_id",
        "framework_id",
        "compliance_id",
        "marketplace_certification_id",
        "prediction_id",
        "boundary_id",
        "sync_id",
        "technology_evolution_id",
    ):
        if key in document:
            return str(document[key])
    raise HTTPException(status_code=422, detail="UGEIF record id missing")


def _document_hash(document: dict[str, Any]) -> str:
    for key in (
        "assessment_hash",
        "report_hash",
        "proposal_hash",
        "impact_hash",
        "simulation_hash",
        "risk_hash",
        "scorecard_hash",
        "recommendation_hash",
        "feedback_hash",
        "plan_hash",
        "graph_hash",
        "entry_hash",
        "certification_hash",
        "pattern_hash",
        "knowledge_hash",
        "framework_hash",
        "compliance_hash",
        "prediction_hash",
        "boundary_hash",
        "sync_hash",
    ):
        if key in document:
            return str(document[key])
    raise HTTPException(status_code=422, detail="UGEIF record hash missing")


def _document_status(document: dict[str, Any]) -> str:
    return str(
        document.get("status")
        or document.get("approval_status")
        or document.get("lifecycle_state")
        or "recorded"
    )


def _latest_status(rows: list[R8GovernanceEvolutionRecordModel], record_type: str) -> str | None:
    return next((row.status for row in rows if row.record_type == record_type), None)


def _maximum_predictive_risk_score(
    rows: list[R8GovernanceEvolutionRecordModel],
) -> float | None:
    scores = [
        float(row.record_document["risk_score"])
        for row in rows
        if row.record_type == "predictive_analysis" and "risk_score" in row.record_document
    ]
    return max(scores) if scores else None
