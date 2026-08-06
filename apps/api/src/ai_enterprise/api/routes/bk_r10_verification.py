from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from ai_enterprise.api.bk_r10_verification_schemas import (
    BKR10ActorRequest,
    BKR10CampaignResponse,
    BKR10ContractResponse,
    BKR10CreateCampaignRequest,
    BKR10CreateHandoffRequest,
    BKR10EnvironmentRequest,
    BKR10ExternalExecutionRequestSchema,
    BKR10ExternalReadinessRequest,
    BKR10RecordResponse,
    BKR10RecordResultRequest,
    BKR10StartCampaignRequest,
    BKR10VerdictRequest,
    BKR10WaiverRequest,
)
from ai_enterprise.api.dependencies import ActorDependency, SessionDependency
from ai_enterprise.application.bk_r10_persistence_service import BKR10PersistenceService
from ai_enterprise.application.bk_r10_verification_runtime import (
    BK_R10_VERSION,
    CAMPAIGN_STATES,
    FINAL_OBLIGATION_STATES,
    TEST_TYPES,
    VERIFICATION_METHODS,
    bk_r10_conformance_report,
    bk_r10_create_campaign,
    bk_r10_create_handoff,
    bk_r10_execute_external_verification,
    bk_r10_external_readiness,
    bk_r10_generate_satisfaction_recommendations,
    bk_r10_generate_verdict,
    bk_r10_perform_coverage_assessment,
    bk_r10_qualify_environment,
    bk_r10_read_campaign,
    bk_r10_record_result,
    bk_r10_start_campaign,
    bk_r10_submit_waiver,
    bk_r10_write_campaign,
)
from ai_enterprise.config import get_settings

router = APIRouter(prefix="/bk/r10-verification", tags=["bk-r10-verification"])


@router.get("/contract", response_model=BKR10ContractResponse)
async def contract(actor: ActorDependency) -> BKR10ContractResponse:
    _require_verification_authority(actor, "read")
    return BKR10ContractResponse(
        version=BK_R10_VERSION,
        campaign_states=list(CAMPAIGN_STATES),
        verification_methods=list(VERIFICATION_METHODS),
        test_types=list(TEST_TYPES),
        final_obligation_states=list(FINAL_OBLIGATION_STATES),
        principles=[
            "exact-baseline-binding",
            "independent-verdict",
            "no-evidence-no-pass",
            "no-silent-omission",
            "environment-integrity",
            "failed-results-remain-visible",
            "verification-and-validation-are-separate",
        ],
    )


@router.get("/conformance", response_model=BKR10RecordResponse)
async def conformance(actor: ActorDependency) -> BKR10RecordResponse:
    _require_verification_authority(actor, "read")
    report = bk_r10_conformance_report(_repo_root())
    return BKR10RecordResponse(record=report.model_dump(mode="json"))


@router.post("/handoffs", response_model=BKR10RecordResponse)
async def create_handoff(
    request: BKR10CreateHandoffRequest,
    actor: ActorDependency,
) -> BKR10RecordResponse:
    _require_verification_authority(actor, "write")
    handoff = bk_r10_create_handoff(**request.model_dump())
    return BKR10RecordResponse(record=handoff.model_dump(mode="json"))


@router.post("/external-readiness", response_model=BKR10RecordResponse)
async def external_readiness(
    request: BKR10ExternalReadinessRequest,
    actor: ActorDependency,
) -> BKR10RecordResponse:
    _require_verification_authority(actor, "read")
    configs = _external_backend_configs(request.backend_configs)
    report = bk_r10_external_readiness(
        configs,
        environment=request.environment,
        required_backends=request.required_backends
        if request.required_backends is not None
        else None,
    )
    return BKR10RecordResponse(record=report.model_dump(mode="json"))


@router.post("/external-executions/mock", response_model=BKR10RecordResponse)
async def external_mock_execution(
    request: BKR10ExternalExecutionRequestSchema,
    actor: ActorDependency,
) -> BKR10RecordResponse:
    _require_verification_authority(actor, "write")
    backend_config = {
        **_external_backend_config_by_type(request.backend_config.get("backend_type", "")),
        **request.backend_config,
    }
    try:
        result = bk_r10_execute_external_verification(
            request.execution_request,
            backend_config,
            environment=request.environment,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return BKR10RecordResponse(record=result.model_dump(mode="json"))


@router.post("/projects/{project_id}/campaigns", response_model=BKR10CampaignResponse)
async def create_campaign(
    project_id: str,
    request: BKR10CreateCampaignRequest,
    actor: ActorDependency,
    session: SessionDependency,
) -> BKR10CampaignResponse:
    _require_verification_authority(actor, "write")
    campaign = bk_r10_create_campaign(
        organization_id=request.organization_id,
        project_id=project_id,
        handoff=request.handoff,
        owner=request.owner,
        obligations=request.obligations,
        procedures=request.procedures,
        criticality=request.criticality,
        risk_classification=request.risk_classification,
    )
    if request.persist:
        bk_r10_write_campaign(
            campaign, _campaign_path(project_id, campaign.verification_campaign_id)
        )
        await _record_campaign(session, campaign, actor, "created")
    return BKR10CampaignResponse(campaign=campaign.model_dump(mode="json"))


@router.get("/projects/{project_id}/campaigns/{campaign_id}", response_model=BKR10CampaignResponse)
async def get_campaign(
    project_id: str,
    campaign_id: str,
    actor: ActorDependency,
) -> BKR10CampaignResponse:
    _require_verification_authority(actor, "read")
    campaign = bk_r10_read_campaign(_campaign_path(project_id, campaign_id))
    if campaign is None:
        raise HTTPException(status_code=404, detail="BK/R10 verification campaign is not present")
    return BKR10CampaignResponse(campaign=campaign.model_dump(mode="json"))


@router.post(
    "/projects/{project_id}/campaigns/{campaign_id}/environment",
    response_model=BKR10CampaignResponse,
)
async def qualify_environment(
    project_id: str,
    campaign_id: str,
    request: BKR10EnvironmentRequest,
    actor: ActorDependency,
    session: SessionDependency,
) -> BKR10CampaignResponse:
    _require_verification_authority(actor, "write")
    campaign = _read_campaign(project_id, campaign_id)
    campaign = bk_r10_qualify_environment(campaign, request.environment, actor=request.actor)
    if request.persist:
        bk_r10_write_campaign(campaign, _campaign_path(project_id, campaign_id))
        await _record_campaign(session, campaign, actor, "environment_qualified")
    return BKR10CampaignResponse(campaign=campaign.model_dump(mode="json"))


@router.post(
    "/projects/{project_id}/campaigns/{campaign_id}/start",
    response_model=BKR10CampaignResponse,
)
async def start_campaign(
    project_id: str,
    campaign_id: str,
    request: BKR10StartCampaignRequest,
    actor: ActorDependency,
    session: SessionDependency,
) -> BKR10CampaignResponse:
    _require_verification_authority(actor, "write")
    campaign = bk_r10_start_campaign(_read_campaign(project_id, campaign_id), actor=request.actor)
    if request.persist:
        bk_r10_write_campaign(campaign, _campaign_path(project_id, campaign_id))
        await _record_campaign(session, campaign, actor, "started")
    return BKR10CampaignResponse(campaign=campaign.model_dump(mode="json"))


@router.post(
    "/projects/{project_id}/campaigns/{campaign_id}/results",
    response_model=BKR10CampaignResponse,
)
async def record_result(
    project_id: str,
    campaign_id: str,
    request: BKR10RecordResultRequest,
    actor: ActorDependency,
    session: SessionDependency,
) -> BKR10CampaignResponse:
    _require_verification_authority(actor, "write")
    campaign = bk_r10_record_result(
        _read_campaign(project_id, campaign_id),
        procedure_id=request.procedure_id,
        environment_id=request.environment_id,
        executor=request.executor,
        obligation_results=request.obligation_results,
        raw_evidence_references=request.raw_evidence_references,
        normalized_evidence_references=request.normalized_evidence_references,
        observed_outputs=request.observed_outputs,
        defects_detected=request.defects_detected,
        warnings=request.warnings,
    )
    if request.persist:
        bk_r10_write_campaign(campaign, _campaign_path(project_id, campaign_id))
        await _record_campaign(session, campaign, actor, "result_recorded")
    return BKR10CampaignResponse(campaign=campaign.model_dump(mode="json"))


@router.post(
    "/projects/{project_id}/campaigns/{campaign_id}/waivers",
    response_model=BKR10CampaignResponse,
)
async def submit_waiver(
    project_id: str,
    campaign_id: str,
    request: BKR10WaiverRequest,
    actor: ActorDependency,
    session: SessionDependency,
) -> BKR10CampaignResponse:
    _require_verification_authority(actor, "write")
    campaign = bk_r10_submit_waiver(
        _read_campaign(project_id, campaign_id),
        obligation_id=request.obligation_id,
        authority=request.authority,
        justification=request.justification,
        risk_acceptance=request.risk_acceptance,
        scope=request.scope,
        expires_at=request.expires_at,
        compensating_controls=request.compensating_controls,
    )
    if request.persist:
        bk_r10_write_campaign(campaign, _campaign_path(project_id, campaign_id))
        await _record_campaign(session, campaign, actor, "waiver_submitted")
    return BKR10CampaignResponse(campaign=campaign.model_dump(mode="json"))


@router.post(
    "/projects/{project_id}/campaigns/{campaign_id}/coverage",
    response_model=BKR10CampaignResponse,
)
async def coverage(
    project_id: str,
    campaign_id: str,
    request: BKR10ActorRequest,
    actor: ActorDependency,
    session: SessionDependency,
) -> BKR10CampaignResponse:
    _require_verification_authority(actor, "write")
    campaign = bk_r10_perform_coverage_assessment(
        _read_campaign(project_id, campaign_id),
        actor=request.actor,
    )
    if request.persist:
        bk_r10_write_campaign(campaign, _campaign_path(project_id, campaign_id))
        await _record_campaign(session, campaign, actor, "coverage_assessed")
    return BKR10CampaignResponse(campaign=campaign.model_dump(mode="json"))


@router.post(
    "/projects/{project_id}/campaigns/{campaign_id}/verdict",
    response_model=BKR10CampaignResponse,
)
async def verdict(
    project_id: str,
    campaign_id: str,
    request: BKR10VerdictRequest,
    actor: ActorDependency,
    session: SessionDependency,
) -> BKR10CampaignResponse:
    _require_verification_authority(actor, "write")
    campaign = bk_r10_generate_verdict(
        _read_campaign(project_id, campaign_id),
        actor=request.actor,
        validation_status=request.validation_status,
    )
    if request.persist:
        bk_r10_write_campaign(campaign, _campaign_path(project_id, campaign_id))
        await _record_campaign(session, campaign, actor, "verdict_generated")
    return BKR10CampaignResponse(campaign=campaign.model_dump(mode="json"))


@router.post(
    "/projects/{project_id}/campaigns/{campaign_id}/satisfaction-recommendations",
    response_model=BKR10CampaignResponse,
)
async def satisfaction_recommendations(
    project_id: str,
    campaign_id: str,
    request: BKR10VerdictRequest,
    actor: ActorDependency,
    session: SessionDependency,
) -> BKR10CampaignResponse:
    _require_verification_authority(actor, "write")
    campaign = bk_r10_generate_satisfaction_recommendations(
        _read_campaign(project_id, campaign_id),
        actor=request.actor,
        validation_status=request.validation_status,
    )
    if request.persist:
        bk_r10_write_campaign(campaign, _campaign_path(project_id, campaign_id))
        await _record_campaign(session, campaign, actor, "satisfaction_recommended")
    return BKR10CampaignResponse(campaign=campaign.model_dump(mode="json"))


def _read_campaign(project_id: str, campaign_id: str):
    campaign = bk_r10_read_campaign(_campaign_path(project_id, campaign_id))
    if campaign is None:
        raise HTTPException(status_code=404, detail="BK/R10 verification campaign is not present")
    return campaign


def _campaign_path(project_id: str, campaign_id: str) -> Path:
    return _repo_root() / "runtime" / "bk-r10-verification" / project_id / f"{campaign_id}.json"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[6]


def _external_backend_configs(
    overrides: tuple[dict[str, object], ...],
) -> tuple[dict[str, object], ...]:
    by_type = {str(item.get("backend_type")): item for item in overrides}
    return tuple(
        {
            **_external_backend_config_by_type(backend_type),
            **by_type.get(backend_type, {}),
        }
        for backend_type in (
            "ci_runner",
            "scanner",
            "evidence_store",
            "policy_engine",
            "lab_environment",
        )
    )


def _external_backend_config_by_type(backend_type: str) -> dict[str, object]:
    settings = get_settings()
    timeout = settings.bk_r10_backend_timeout_seconds
    mock_mode = settings.bk_r10_mock_backends_enabled
    configs: dict[str, dict[str, object]] = {
        "ci_runner": {
            "backend_type": "ci_runner",
            "provider": settings.bk_r10_ci_runner_provider,
            "enabled": settings.bk_r10_ci_runner_enabled,
            "endpoint_reference": settings.bk_r10_ci_runner_endpoint_ref,
            "credential_reference": settings.bk_r10_ci_runner_credentials_ref,
            "timeout_seconds": timeout,
            "mock_mode": mock_mode and settings.bk_r10_ci_runner_provider == "mock",
        },
        "scanner": {
            "backend_type": "scanner",
            "provider": settings.bk_r10_scanner_provider,
            "enabled": settings.bk_r10_scanner_enabled,
            "endpoint_reference": settings.bk_r10_scanner_endpoint_ref,
            "credential_reference": settings.bk_r10_scanner_credentials_ref,
            "timeout_seconds": timeout,
            "mock_mode": mock_mode and settings.bk_r10_scanner_provider == "mock",
        },
        "evidence_store": {
            "backend_type": "evidence_store",
            "provider": settings.bk_r10_evidence_store_provider,
            "enabled": settings.bk_r10_evidence_store_enabled,
            "endpoint_reference": settings.bk_r10_evidence_store_endpoint_ref,
            "credential_reference": settings.bk_r10_evidence_store_credentials_ref,
            "evidence_reference": settings.bk_r10_evidence_store_ref,
            "timeout_seconds": timeout,
            "mock_mode": mock_mode and settings.bk_r10_evidence_store_provider == "mock",
        },
        "policy_engine": {
            "backend_type": "policy_engine",
            "provider": settings.bk_r10_policy_engine_provider,
            "enabled": settings.bk_r10_policy_engine_enabled,
            "endpoint_reference": settings.bk_r10_policy_engine_endpoint_ref,
            "credential_reference": settings.bk_r10_policy_engine_credentials_ref,
            "policy_reference": settings.bk_r10_policy_engine_policy_ref,
            "timeout_seconds": timeout,
            "mock_mode": mock_mode and settings.bk_r10_policy_engine_provider == "mock",
        },
        "lab_environment": {
            "backend_type": "lab_environment",
            "provider": settings.bk_r10_lab_environment_provider,
            "enabled": settings.bk_r10_lab_environment_enabled,
            "endpoint_reference": settings.bk_r10_lab_environment_endpoint_ref,
            "credential_reference": settings.bk_r10_lab_environment_credentials_ref,
            "timeout_seconds": timeout,
            "mock_mode": mock_mode and settings.bk_r10_lab_environment_provider == "mock",
        },
    }
    return {key: value for key, value in configs.get(backend_type, {}).items() if value is not None}


def _require_verification_authority(actor: ActorDependency, action: str) -> None:
    role = getattr(actor, "role", "")
    if role in {"platform-admin", "admin", "owner", "architect", "reviewer", "operator"}:
        return
    if action == "read" and role in {"developer", "viewer", "analyst"}:
        return
    raise HTTPException(status_code=403, detail="Actor lacks BK/R10 verification authority")


async def _record_campaign(
    session: SessionDependency,
    campaign,
    actor: ActorDependency,
    action: str,
) -> None:
    try:
        service = BKR10PersistenceService(session)
        await service.record_campaign(
            campaign,
            actor_type=actor.actor_type,
            actor_id=actor.subject,
            action=action,
        )
        await service.flush()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"BK/R10 persistence failed for action {action}",
        ) from exc
