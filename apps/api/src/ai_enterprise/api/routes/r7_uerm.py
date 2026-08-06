from __future__ import annotations

import os
import shutil
import subprocess
import urllib.error
import urllib.request
import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ai_enterprise.api.dependencies import ActorDependency, SessionDependency
from ai_enterprise.api.r7_uerm_schemas import (
    R7CompatibilityReportRequest,
    R7CompatibilityReportResponse,
    R7DeploymentRuntimeSyncRequest,
    R7DeploymentRuntimeSyncResponse,
    R7DigitalTwinSnapshotRequest,
    R7DigitalTwinSnapshotResponse,
    R7EventDispatchRequest,
    R7EventDispatchResponse,
    R7HealthReportRequest,
    R7HealthReportResponse,
    R7PluginBindingRequest,
    R7PluginBindingResponse,
    R7PolicyEvaluationRequest,
    R7PolicyEvaluationResponse,
    R7RecoveryActionRequest,
    R7RecoveryActionResponse,
    R7RuntimeAiRequest,
    R7RuntimeAiRequestResponse,
    R7RuntimeAuditRecordRequest,
    R7RuntimeAuditRecordResponse,
    R7RuntimeConfigurationRequest,
    R7RuntimeConfigurationResponse,
    R7RuntimeDeploymentRequest,
    R7RuntimeDeploymentResponse,
    R7RuntimeErrorRequest,
    R7RuntimeErrorResponse,
    R7RuntimeEventRequest,
    R7RuntimeEventResponse,
    R7RuntimeGovernanceTraceRequest,
    R7RuntimeGovernanceTraceResponse,
    R7RuntimeProviderReadinessResponse,
    R7RuntimeProviderRequest,
    R7RuntimeProviderResponse,
    R7RuntimeSynchronizationRequest,
    R7RuntimeSynchronizationResponse,
    R7RuntimeTelemetryBatchRequest,
    R7RuntimeTelemetryBatchResponse,
    R7RuntimeUpgradePlanResponse,
    R7WorkflowInstanceResponse,
    R7WorkflowStartRequest,
    R7WorkflowTransitionRequest,
)
from ai_enterprise.config import get_settings
from ai_enterprise.domain.r6_uagf import (
    UagfFileLifecycle,
    UagfLifecycleEvent,
    UagfLifecycleEventType,
    current_uagf_lifecycle_status,
)
from ai_enterprise.domain.r7_uerm import (
    UermErrorCategory,
    UermErrorSeverity,
    UermHealthStatus,
    UermPolicyEvaluation,
    UermRecoveryStatus,
    UermRecoveryStrategy,
    UermRuntimeContext,
    UermRuntimeDeployment,
    UermRuntimeEvent,
    UermRuntimeProvider,
    UermRuntimeProviderKind,
    UermRuntimeProviderStatus,
    UermRuntimeSynchronizationReport,
    UermWorkflowInstance,
    assess_runtime_compatibility,
    bind_runtime_plugin,
    digital_twin_snapshot,
    dispatch_runtime_event,
    evaluate_runtime_policy,
    recovery_action,
    register_runtime_deployment,
    register_runtime_provider,
    runtime_ai_request,
    runtime_audit_record,
    runtime_configuration_snapshot,
    runtime_context,
    runtime_error,
    runtime_event,
    runtime_governance_trace,
    runtime_health_report,
    runtime_synchronization_report,
    runtime_telemetry_batch,
    runtime_upgrade_plan,
    start_workflow_instance,
    sync_runtime_deployment,
    transition_workflow_instance,
)
from ai_enterprise.infrastructure.database.models import ProjectModel
from ai_enterprise.infrastructure.knowledge.models import (
    R6GenerationBuildModel,
    R6LifecycleEventModel,
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

router = APIRouter(prefix="/projects", tags=["r7-uerm"])


def _require_human(actor: object) -> None:
    if getattr(actor, "actor_type", None) != "human":
        raise HTTPException(status_code=403, detail="Human runtime authority is required")


@router.post(
    "/{project_id}/uerm/deployments/from-uagf-build/{build_id}",
    response_model=R7RuntimeDeploymentResponse,
    status_code=201,
)
async def register_uerm_deployment(
    project_id: uuid.UUID,
    build_id: uuid.UUID,
    request: R7RuntimeDeploymentRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7RuntimeDeploymentResponse:
    _require_human(actor)
    build = await _published_r6_build(session, project_id, build_id)
    existing = await session.scalar(
        select(R7RuntimeDeploymentModel).where(
            R7RuntimeDeploymentModel.r6_generation_build_id == build.id,
            R7RuntimeDeploymentModel.environment == request.environment,
            R7RuntimeDeploymentModel.service_identity == request.service_identity,
        )
    )
    if existing is not None:
        return R7RuntimeDeploymentResponse.model_validate(existing)
    deployment_count = len(
        (
            await session.scalars(
                select(R7RuntimeDeploymentModel).where(
                    R7RuntimeDeploymentModel.project_id == project_id
                )
            )
        ).all()
    )
    deployment = register_runtime_deployment(
        index=deployment_count + 1,
        project_id=str(project_id),
        r6_build_hash=build.build_hash,
        r6_manifest_hash=build.manifest_hash,
        service_identity=request.service_identity,
        environment=request.environment,
        manifest_version=request.manifest_version,
        application_version=request.application_version,
        generator_pack_id=build.generator_pack_id,
        generator_pack_version=build.generator_pack_version,
        artifact_count=build.artifact_count,
        template_version=request.template_version,
        deployment_location=request.deployment_location,
        endpoint_urls=tuple(request.endpoint_urls),
        dependency_service_ids=tuple(request.dependency_service_ids),
    )
    row = R7RuntimeDeploymentModel(
        id=uuid.uuid4(),
        project_id=project_id,
        r6_generation_build_id=build.id,
        deployment_id=deployment.deployment_id,
        service_identity=deployment.service_identity,
        environment=deployment.environment,
        status=deployment.status.value,
        manifest_version=deployment.manifest_version,
        application_version=deployment.application_version,
        template_version=deployment.template_version,
        generator_pack_id=deployment.generator_pack_id,
        generator_pack_version=deployment.generator_pack_version,
        deployment_location=deployment.deployment_location,
        endpoint_urls=list(deployment.endpoint_urls),
        dependency_service_ids=list(deployment.dependency_service_ids),
        deployment_document=deployment.model_dump(mode="json"),
        deployment_hash=deployment.deployment_hash,
        created_by=actor.subject,
    )
    session.add(row)
    await session.commit()
    return R7RuntimeDeploymentResponse.model_validate(row)


@router.get(
    "/{project_id}/uerm/deployments",
    response_model=list[R7RuntimeDeploymentResponse],
)
async def list_uerm_deployments(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> list[R7RuntimeDeploymentResponse]:
    _require_human(actor)
    await _project(session, project_id)
    rows = (
        await session.scalars(
            select(R7RuntimeDeploymentModel)
            .where(R7RuntimeDeploymentModel.project_id == project_id)
            .order_by(R7RuntimeDeploymentModel.created_at.desc())
        )
    ).all()
    return [R7RuntimeDeploymentResponse.model_validate(row) for row in rows]


@router.get(
    "/{project_id}/uerm/deployments/{deployment_id}",
    response_model=R7RuntimeDeploymentResponse,
)
async def get_uerm_deployment(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7RuntimeDeploymentResponse:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    return R7RuntimeDeploymentResponse.model_validate(deployment)


@router.post(
    "/{project_id}/uerm/providers",
    response_model=R7RuntimeProviderResponse,
    status_code=201,
)
async def register_uerm_runtime_provider(
    project_id: uuid.UUID,
    request: R7RuntimeProviderRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7RuntimeProviderResponse:
    _require_human(actor)
    await _project(session, project_id)
    existing = await session.scalar(
        select(R7RuntimeProviderModel).where(
            R7RuntimeProviderModel.project_id == project_id,
            R7RuntimeProviderModel.kind == request.kind,
            R7RuntimeProviderModel.name == request.name,
            R7RuntimeProviderModel.version == request.version,
        )
    )
    if existing is not None:
        return R7RuntimeProviderResponse.model_validate(existing)
    count = len(
        (
            await session.scalars(
                select(R7RuntimeProviderModel).where(
                    R7RuntimeProviderModel.project_id == project_id
                )
            )
        ).all()
    )
    provider = register_runtime_provider(
        index=count + 1,
        project_id=str(project_id),
        kind=UermRuntimeProviderKind(request.kind),
        name=request.name,
        version=request.version,
        status=UermRuntimeProviderStatus(request.status),
        capabilities=tuple(request.capabilities),
        endpoint_ref=request.endpoint_ref,
        configuration=request.configuration,
    )
    row = R7RuntimeProviderModel(
        id=uuid.uuid4(),
        project_id=project_id,
        provider_id=provider.provider_id,
        kind=provider.kind.value,
        name=provider.name,
        version=provider.version,
        status=provider.status.value,
        capabilities=list(provider.capabilities),
        endpoint_ref=provider.endpoint_ref,
        configuration_document=provider.configuration,
        provider_document=provider.model_dump(mode="json"),
        provider_hash=provider.provider_hash,
        created_by=actor.subject,
    )
    session.add(row)
    await session.commit()
    return R7RuntimeProviderResponse.model_validate(row)


@router.get(
    "/{project_id}/uerm/providers",
    response_model=list[R7RuntimeProviderResponse],
)
async def list_uerm_runtime_providers(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> list[R7RuntimeProviderResponse]:
    _require_human(actor)
    await _project(session, project_id)
    rows = (
        await session.scalars(
            select(R7RuntimeProviderModel)
            .where(R7RuntimeProviderModel.project_id == project_id)
            .order_by(R7RuntimeProviderModel.created_at.desc())
        )
    ).all()
    return [R7RuntimeProviderResponse.model_validate(row) for row in rows]


@router.get(
    "/{project_id}/uerm/providers/{provider_id}/readiness",
    response_model=R7RuntimeProviderReadinessResponse,
)
async def uerm_runtime_provider_readiness(
    project_id: uuid.UUID,
    provider_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7RuntimeProviderReadinessResponse:
    _require_human(actor)
    provider = await _provider(session, project_id, provider_id)
    report = _runtime_provider_readiness(provider)
    return R7RuntimeProviderReadinessResponse(
        provider_id=provider.id,
        provider_kind=provider.kind,
        provider_name=provider.name,
        ready=bool(report["ready"]),
        checks=report["checks"],
        required_configuration=report["required_configuration"],
    )


@router.post(
    "/{project_id}/uerm/deployments/{deployment_id}/health-reports",
    response_model=R7HealthReportResponse,
    status_code=201,
)
async def record_uerm_health_report(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    request: R7HealthReportRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7HealthReportResponse:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    try:
        checks = {
            name: UermHealthStatus(status)
            for name, status in sorted(request.checks.items())
        }
        report = runtime_health_report(
            deployment_hash=deployment.deployment_hash,
            checks=checks,
            metrics=request.metrics,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = R7HealthReportModel(
        id=uuid.uuid4(),
        project_id=project_id,
        runtime_deployment_id=deployment.id,
        status=report.status.value,
        checks_document={key: value.value for key, value in report.checks.items()},
        metrics_document=report.metrics,
        report_document=report.model_dump(mode="json"),
        report_hash=report.report_hash,
    )
    session.add(row)
    await session.commit()
    return R7HealthReportResponse.model_validate(row)


@router.get(
    "/{project_id}/uerm/deployments/{deployment_id}/health-reports",
    response_model=list[R7HealthReportResponse],
)
async def list_uerm_health_reports(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> list[R7HealthReportResponse]:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    rows = (
        await session.scalars(
            select(R7HealthReportModel)
            .where(R7HealthReportModel.runtime_deployment_id == deployment.id)
            .order_by(R7HealthReportModel.created_at.desc())
        )
    ).all()
    return [R7HealthReportResponse.model_validate(row) for row in rows]


@router.post(
    "/{project_id}/uerm/deployments/{deployment_id}/runtime-syncs",
    response_model=R7DeploymentRuntimeSyncResponse,
    status_code=201,
)
async def sync_uerm_runtime_deployment(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    request: R7DeploymentRuntimeSyncRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7DeploymentRuntimeSyncResponse:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    provider = await _provider(session, project_id, request.provider_id)
    count = len(
        (
            await session.scalars(
                select(R7DeploymentRuntimeSyncModel).where(
                    R7DeploymentRuntimeSyncModel.runtime_deployment_id == deployment.id
                )
            )
        ).all()
    )
    try:
        sync = sync_runtime_deployment(
            index=count + 1,
            deployment=_deployment_domain(deployment),
            provider=_provider_domain(provider),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = R7DeploymentRuntimeSyncModel(
        id=uuid.uuid4(),
        project_id=project_id,
        runtime_deployment_id=deployment.id,
        runtime_provider_id=provider.id,
        sync_id=sync.sync_id,
        status=sync.status.value,
        runtime_document=sync.runtime_document,
        sync_hash=sync.sync_hash,
    )
    session.add(row)
    await session.commit()
    return R7DeploymentRuntimeSyncResponse.model_validate(row)


@router.post(
    "/{project_id}/uerm/deployments/{deployment_id}/policy-evaluations",
    response_model=R7PolicyEvaluationResponse,
    status_code=201,
)
async def evaluate_uerm_runtime_policy(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    request: R7PolicyEvaluationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7PolicyEvaluationResponse:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    provider = (
        await _provider(session, project_id, request.provider_id)
        if request.provider_id is not None
        else None
    )
    context = _context_from_request(request.context)
    count = await _policy_evaluation_count(session, deployment)
    evaluation = evaluate_runtime_policy(
        index=count + 1,
        deployment_hash=deployment.deployment_hash,
        context=context,
        action=request.action,
        resource=request.resource,
        provider_hash=provider.provider_hash if provider is not None else None,
        policy_refs=tuple(request.policy_refs),
    )
    row = _policy_evaluation_row(project_id, deployment.id, provider, context, evaluation)
    session.add(row)
    await session.commit()
    return R7PolicyEvaluationResponse.model_validate(row)


@router.get(
    "/{project_id}/uerm/deployments/{deployment_id}/policy-evaluations",
    response_model=list[R7PolicyEvaluationResponse],
)
async def list_uerm_runtime_policy_evaluations(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> list[R7PolicyEvaluationResponse]:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    rows = (
        await session.scalars(
            select(R7PolicyEvaluationModel)
            .where(R7PolicyEvaluationModel.runtime_deployment_id == deployment.id)
            .order_by(R7PolicyEvaluationModel.created_at.desc())
        )
    ).all()
    return [R7PolicyEvaluationResponse.model_validate(row) for row in rows]


@router.post(
    "/{project_id}/uerm/deployments/{deployment_id}/events",
    response_model=R7RuntimeEventResponse,
    status_code=201,
)
async def record_uerm_runtime_event(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    request: R7RuntimeEventRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7RuntimeEventResponse:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    event_count = len(
        (
            await session.scalars(
                select(R7RuntimeEventModel).where(
                    R7RuntimeEventModel.runtime_deployment_id == deployment.id
                )
            )
        ).all()
    )
    context = runtime_context(
        request_id=request.context.request_id,
        correlation_id=request.context.correlation_id,
        tenant=request.context.tenant,
        user=request.context.user,
        role=request.context.role,
        permissions=tuple(request.context.permissions),
        session_id=request.context.session_id,
        locale=request.context.locale,
        time_zone=request.context.time_zone,
        manifest_version=request.context.manifest_version,
        application_version=request.context.application_version,
    )
    event = runtime_event(
        index=event_count + 1,
        deployment_hash=deployment.deployment_hash,
        event_type=request.event_type,
        context=context,
        payload=request.payload,
        manifest_rule_ref=request.manifest_rule_ref,
    )
    row = R7RuntimeEventModel(
        id=uuid.uuid4(),
        project_id=project_id,
        runtime_deployment_id=deployment.id,
        event_id=event.event_id,
        event_type=event.event_type,
        context_document=event.context.model_dump(mode="json"),
        payload_document=event.payload,
        manifest_rule_ref=event.manifest_rule_ref,
        event_hash=event.event_hash,
    )
    session.add(row)
    await session.commit()
    return R7RuntimeEventResponse.model_validate(row)


@router.get(
    "/{project_id}/uerm/deployments/{deployment_id}/events",
    response_model=list[R7RuntimeEventResponse],
)
async def list_uerm_runtime_events(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> list[R7RuntimeEventResponse]:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    rows = (
        await session.scalars(
            select(R7RuntimeEventModel)
            .where(R7RuntimeEventModel.runtime_deployment_id == deployment.id)
            .order_by(R7RuntimeEventModel.created_at)
        )
    ).all()
    return [R7RuntimeEventResponse.model_validate(row) for row in rows]


@router.post(
    "/{project_id}/uerm/events/{runtime_event_id}/dispatches",
    response_model=R7EventDispatchResponse,
    status_code=201,
)
async def dispatch_uerm_runtime_event(
    project_id: uuid.UUID,
    runtime_event_id: uuid.UUID,
    request: R7EventDispatchRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7EventDispatchResponse:
    _require_human(actor)
    event_row = await session.get(R7RuntimeEventModel, runtime_event_id)
    if event_row is None or event_row.project_id != project_id:
        raise HTTPException(status_code=404, detail="Runtime event not found")
    provider = await _provider(session, project_id, request.provider_id)
    count = len(
        (
            await session.scalars(
                select(R7EventDispatchModel).where(
                    R7EventDispatchModel.runtime_event_id == event_row.id
                )
            )
        ).all()
    )
    try:
        dispatch = dispatch_runtime_event(
            index=count + 1,
            event=_runtime_event_domain(event_row),
            provider=_provider_domain(provider),
            subscriber_refs=tuple(request.subscriber_refs),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = R7EventDispatchModel(
        id=uuid.uuid4(),
        project_id=project_id,
        runtime_event_id=event_row.id,
        runtime_provider_id=provider.id,
        dispatch_id=dispatch.dispatch_id,
        status=dispatch.status.value,
        subscriber_refs=list(dispatch.subscriber_refs),
        dispatch_document=dispatch.model_dump(mode="json"),
        dispatch_hash=dispatch.dispatch_hash,
    )
    session.add(row)
    await session.commit()
    return R7EventDispatchResponse.model_validate(row)


@router.post(
    "/{project_id}/uerm/deployments/{deployment_id}/compatibility-reports",
    response_model=R7CompatibilityReportResponse,
    status_code=201,
)
async def record_uerm_compatibility_report(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    request: R7CompatibilityReportRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7CompatibilityReportResponse:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    report = assess_runtime_compatibility(
        deployment=_deployment_domain(deployment),
        current_manifest_version=request.current_manifest_version,
        current_application_version=request.current_application_version,
    )
    row = R7CompatibilityReportModel(
        id=uuid.uuid4(),
        project_id=project_id,
        runtime_deployment_id=deployment.id,
        status=report.status.value,
        report_document=report.model_dump(mode="json"),
        report_hash=report.report_hash,
    )
    session.add(row)
    await session.commit()
    return R7CompatibilityReportResponse.model_validate(row)


@router.get(
    "/{project_id}/uerm/deployments/{deployment_id}/compatibility-reports",
    response_model=list[R7CompatibilityReportResponse],
)
async def list_uerm_compatibility_reports(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> list[R7CompatibilityReportResponse]:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    rows = (
        await session.scalars(
            select(R7CompatibilityReportModel)
            .where(R7CompatibilityReportModel.runtime_deployment_id == deployment.id)
            .order_by(R7CompatibilityReportModel.created_at.desc())
        )
    ).all()
    return [R7CompatibilityReportResponse.model_validate(row) for row in rows]


@router.post(
    "/{project_id}/uerm/deployments/{deployment_id}/synchronization-reports",
    response_model=R7RuntimeSynchronizationResponse,
    status_code=201,
)
async def record_uerm_runtime_synchronization(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    request: R7RuntimeSynchronizationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7RuntimeSynchronizationResponse:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    count = len(await _synchronization_rows(session, deployment))
    report = runtime_synchronization_report(
        index=count + 1,
        deployment=_deployment_domain(deployment),
        current_manifest_version=request.current_manifest_version,
        current_application_version=request.current_application_version,
        observed_runtime=request.observed_runtime,
    )
    row = _synchronization_row(project_id, deployment.id, report)
    session.add(row)
    await session.commit()
    return R7RuntimeSynchronizationResponse.model_validate(row)


@router.get(
    "/{project_id}/uerm/deployments/{deployment_id}/synchronization-reports",
    response_model=list[R7RuntimeSynchronizationResponse],
)
async def list_uerm_runtime_synchronization_reports(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> list[R7RuntimeSynchronizationResponse]:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    return [
        R7RuntimeSynchronizationResponse.model_validate(row)
        for row in await _synchronization_rows(session, deployment)
    ]


@router.post(
    "/{project_id}/uerm/synchronization-reports/{synchronization_report_id}/upgrade-plans",
    response_model=R7RuntimeUpgradePlanResponse,
    status_code=201,
)
async def plan_uerm_runtime_upgrade(
    project_id: uuid.UUID,
    synchronization_report_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7RuntimeUpgradePlanResponse:
    _require_human(actor)
    report_row = await session.get(R7RuntimeSynchronizationReportModel, synchronization_report_id)
    if report_row is None or report_row.project_id != project_id:
        raise HTTPException(status_code=404, detail="Runtime synchronization report not found")
    deployment = await _deployment(session, project_id, report_row.runtime_deployment_id)
    count = len(
        (
            await session.scalars(
                select(R7RuntimeUpgradePlanModel).where(
                    R7RuntimeUpgradePlanModel.runtime_deployment_id == deployment.id
                )
            )
        ).all()
    )
    plan = runtime_upgrade_plan(
        index=count + 1,
        deployment=_deployment_domain(deployment),
        synchronization_report=UermRuntimeSynchronizationReport.model_validate(
            report_row.report_document
        ),
    )
    row = R7RuntimeUpgradePlanModel(
        id=uuid.uuid4(),
        project_id=project_id,
        runtime_deployment_id=deployment.id,
        synchronization_report_id=report_row.id,
        upgrade_plan_id=plan.upgrade_plan_id,
        status=plan.status.value,
        blocked_by=list(plan.blocked_by),
        steps_document=list(plan.steps),
        plan_document=plan.model_dump(mode="json"),
        plan_hash=plan.plan_hash,
    )
    session.add(row)
    await session.commit()
    return R7RuntimeUpgradePlanResponse.model_validate(row)


@router.get(
    "/{project_id}/uerm/deployments/{deployment_id}/upgrade-plans",
    response_model=list[R7RuntimeUpgradePlanResponse],
)
async def list_uerm_runtime_upgrade_plans(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> list[R7RuntimeUpgradePlanResponse]:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    rows = (
        await session.scalars(
            select(R7RuntimeUpgradePlanModel)
            .where(R7RuntimeUpgradePlanModel.runtime_deployment_id == deployment.id)
            .order_by(R7RuntimeUpgradePlanModel.created_at.desc())
        )
    ).all()
    return [R7RuntimeUpgradePlanResponse.model_validate(row) for row in rows]


@router.post(
    "/{project_id}/uerm/deployments/{deployment_id}/workflow-instances",
    response_model=R7WorkflowInstanceResponse,
    status_code=201,
)
async def start_uerm_workflow_instance(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    request: R7WorkflowStartRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7WorkflowInstanceResponse:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    count = len(await _workflow_rows(session, deployment))
    context = _context_from_request(request.context)
    instance = start_workflow_instance(
        index=count + 1,
        deployment_hash=deployment.deployment_hash,
        workflow_key=request.workflow_key,
        initial_state=request.initial_state,
        allowed_transitions={
            key: tuple(values) for key, values in request.allowed_transitions.items()
        },
        responsible_actor=request.responsible_actor,
        context=context,
        pending_actions=tuple(request.pending_actions),
    )
    row = _workflow_row(project_id, deployment.id, instance)
    session.add(row)
    await session.commit()
    return R7WorkflowInstanceResponse.model_validate(row)


@router.get(
    "/{project_id}/uerm/deployments/{deployment_id}/workflow-instances",
    response_model=list[R7WorkflowInstanceResponse],
)
async def list_uerm_workflow_instances(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> list[R7WorkflowInstanceResponse]:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    return [
        R7WorkflowInstanceResponse.model_validate(row)
        for row in await _workflow_rows(session, deployment)
    ]


@router.post(
    "/{project_id}/uerm/deployments/{deployment_id}/workflow-instances/{workflow_instance_id}/transitions",
    response_model=R7WorkflowInstanceResponse,
    status_code=201,
)
async def transition_uerm_workflow_instance(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    workflow_instance_id: str,
    request: R7WorkflowTransitionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7WorkflowInstanceResponse:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    current = await _latest_workflow_row(session, deployment, workflow_instance_id)
    try:
        instance = transition_workflow_instance(
            _workflow_domain(current),
            next_state=request.next_state,
            actor=request.actor,
            reason=request.reason,
            pending_actions=tuple(request.pending_actions),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    row = _workflow_row(project_id, deployment.id, instance)
    session.add(row)
    await session.commit()
    return R7WorkflowInstanceResponse.model_validate(row)


@router.post(
    "/{project_id}/uerm/deployments/{deployment_id}/ai-requests",
    response_model=R7RuntimeAiRequestResponse,
    status_code=201,
)
async def request_uerm_runtime_ai(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    request: R7RuntimeAiRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7RuntimeAiRequestResponse:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    provider = await _provider(session, project_id, request.provider_id)
    context = _context_from_request(request.context)
    policy_evaluation = evaluate_runtime_policy(
        index=(await _policy_evaluation_count(session, deployment)) + 1,
        deployment_hash=deployment.deployment_hash,
        context=context,
        action=request.action,
        resource=request.resource,
        provider_hash=provider.provider_hash,
        policy_refs=tuple(request.policy_refs),
    )
    policy_row = _policy_evaluation_row(
        project_id, deployment.id, provider, context, policy_evaluation
    )
    count = len(
        (
            await session.scalars(
                select(R7RuntimeAiRequestModel).where(
                    R7RuntimeAiRequestModel.runtime_deployment_id == deployment.id
                )
            )
        ).all()
    )
    try:
        ai_request = runtime_ai_request(
            index=count + 1,
            deployment_hash=deployment.deployment_hash,
            provider=_provider_domain(provider),
            context=context,
            policy_evaluation=policy_evaluation,
            capability=request.capability,
            prompt=request.prompt,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    ai_row = R7RuntimeAiRequestModel(
        id=uuid.uuid4(),
        project_id=project_id,
        runtime_deployment_id=deployment.id,
        runtime_provider_id=provider.id,
        policy_evaluation_id=policy_row.id,
        ai_request_id=ai_request.ai_request_id,
        capability=ai_request.capability,
        status=ai_request.status.value,
        prompt=ai_request.prompt,
        context_document=context.model_dump(mode="json"),
        response_document=ai_request.response_document,
        request_document=ai_request.model_dump(mode="json"),
        request_hash=ai_request.request_hash,
    )
    session.add(policy_row)
    session.add(ai_row)
    await session.commit()
    return R7RuntimeAiRequestResponse.model_validate(ai_row)


@router.post(
    "/{project_id}/uerm/deployments/{deployment_id}/plugin-bindings",
    response_model=R7PluginBindingResponse,
    status_code=201,
)
async def bind_uerm_runtime_plugin(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    request: R7PluginBindingRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7PluginBindingResponse:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    provider = await _provider(session, project_id, request.provider_id)
    count = len(
        (
            await session.scalars(
                select(R7PluginBindingModel).where(
                    R7PluginBindingModel.runtime_deployment_id == deployment.id
                )
            )
        ).all()
    )
    binding = bind_runtime_plugin(
        index=count + 1,
        deployment_hash=deployment.deployment_hash,
        provider=_provider_domain(provider),
        plugin_name=request.plugin_name,
        plugin_version=request.plugin_version,
        requested_capabilities=tuple(request.requested_capabilities),
    )
    row = R7PluginBindingModel(
        id=uuid.uuid4(),
        project_id=project_id,
        runtime_deployment_id=deployment.id,
        runtime_provider_id=provider.id,
        binding_id=binding.binding_id,
        plugin_name=binding.plugin_name,
        plugin_version=binding.plugin_version,
        compatibility_status=binding.compatibility_status.value,
        requested_capabilities=list(binding.requested_capabilities),
        findings=list(binding.findings),
        binding_document=binding.model_dump(mode="json"),
        binding_hash=binding.binding_hash,
    )
    session.add(row)
    await session.commit()
    return R7PluginBindingResponse.model_validate(row)


@router.post(
    "/{project_id}/uerm/deployments/{deployment_id}/configuration-snapshots",
    response_model=R7RuntimeConfigurationResponse,
    status_code=201,
)
async def record_uerm_runtime_configuration(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    request: R7RuntimeConfigurationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7RuntimeConfigurationResponse:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    count = len(
        (
            await session.scalars(
                select(R7RuntimeConfigurationSnapshotModel).where(
                    R7RuntimeConfigurationSnapshotModel.runtime_deployment_id
                    == deployment.id
                )
            )
        ).all()
    )
    snapshot = runtime_configuration_snapshot(
        index=count + 1,
        deployment_hash=deployment.deployment_hash,
        manifest_version=deployment.manifest_version,
        configuration=request.configuration,
        feature_flags=request.feature_flags,
    )
    row = R7RuntimeConfigurationSnapshotModel(
        id=uuid.uuid4(),
        project_id=project_id,
        runtime_deployment_id=deployment.id,
        configuration_id=snapshot.configuration_id,
        manifest_version=snapshot.manifest_version,
        configuration_document=snapshot.configuration_document,
        feature_flags=snapshot.feature_flags,
        sensitive_keys=list(snapshot.sensitive_keys),
        configuration_hash=snapshot.configuration_hash,
    )
    session.add(row)
    await session.commit()
    return R7RuntimeConfigurationResponse.model_validate(row)


@router.post(
    "/{project_id}/uerm/deployments/{deployment_id}/audit-records",
    response_model=R7RuntimeAuditRecordResponse,
    status_code=201,
)
async def record_uerm_runtime_audit(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    request: R7RuntimeAuditRecordRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7RuntimeAuditRecordResponse:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    count = len(
        (
            await session.scalars(
                select(R7RuntimeAuditRecordModel).where(
                    R7RuntimeAuditRecordModel.runtime_deployment_id == deployment.id
                )
            )
        ).all()
    )
    audit = runtime_audit_record(
        index=count + 1,
        deployment_hash=deployment.deployment_hash,
        actor=request.actor,
        action=request.action,
        affected_object=request.affected_object,
        correlation_id=request.correlation_id,
        manifest_rule_ref=request.manifest_rule_ref,
        previous_value=request.previous_value,
        new_value=request.new_value,
    )
    row = R7RuntimeAuditRecordModel(
        id=uuid.uuid4(),
        project_id=project_id,
        runtime_deployment_id=deployment.id,
        audit_id=audit.audit_id,
        actor=audit.actor,
        action=audit.action,
        affected_object=audit.affected_object,
        previous_value_hash=audit.previous_value_hash,
        new_value_hash=audit.new_value_hash,
        correlation_id=audit.correlation_id,
        manifest_rule_ref=audit.manifest_rule_ref,
        audit_document=audit.model_dump(mode="json"),
        audit_hash=audit.audit_hash,
    )
    session.add(row)
    await session.commit()
    return R7RuntimeAuditRecordResponse.model_validate(row)


@router.post(
    "/{project_id}/uerm/deployments/{deployment_id}/telemetry-batches",
    response_model=R7RuntimeTelemetryBatchResponse,
    status_code=201,
)
async def record_uerm_runtime_telemetry(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    request: R7RuntimeTelemetryBatchRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7RuntimeTelemetryBatchResponse:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    count = len(
        (
            await session.scalars(
                select(R7RuntimeTelemetryBatchModel).where(
                    R7RuntimeTelemetryBatchModel.runtime_deployment_id == deployment.id
                )
            )
        ).all()
    )
    telemetry = runtime_telemetry_batch(
        index=count + 1,
        deployment_hash=deployment.deployment_hash,
        metrics=request.metrics,
        trace_ids=tuple(request.trace_ids),
        log_signatures=tuple(request.log_signatures),
        performance_indicators=request.performance_indicators,
    )
    row = R7RuntimeTelemetryBatchModel(
        id=uuid.uuid4(),
        project_id=project_id,
        runtime_deployment_id=deployment.id,
        telemetry_id=telemetry.telemetry_id,
        metrics_document=telemetry.metrics,
        trace_ids=list(telemetry.trace_ids),
        log_signatures=list(telemetry.log_signatures),
        performance_indicators=telemetry.performance_indicators,
        telemetry_document=telemetry.model_dump(mode="json"),
        telemetry_hash=telemetry.telemetry_hash,
    )
    session.add(row)
    await session.commit()
    return R7RuntimeTelemetryBatchResponse.model_validate(row)


@router.post(
    "/{project_id}/uerm/deployments/{deployment_id}/governance-traces",
    response_model=R7RuntimeGovernanceTraceResponse,
    status_code=201,
)
async def record_uerm_runtime_governance_trace(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    request: R7RuntimeGovernanceTraceRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7RuntimeGovernanceTraceResponse:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    count = len(
        (
            await session.scalars(
                select(R7RuntimeGovernanceTraceModel).where(
                    R7RuntimeGovernanceTraceModel.runtime_deployment_id == deployment.id
                )
            )
        ).all()
    )
    trace = runtime_governance_trace(
        index=count + 1,
        deployment_hash=deployment.deployment_hash,
        runtime_action_hash=request.runtime_action_hash,
        business_rule_ref=request.business_rule_ref,
        registry_rule_ref=request.registry_rule_ref,
        manifest_object_ref=request.manifest_object_ref,
        requirement_ref=request.requirement_ref,
    )
    row = R7RuntimeGovernanceTraceModel(
        id=uuid.uuid4(),
        project_id=project_id,
        runtime_deployment_id=deployment.id,
        governance_trace_id=trace.governance_trace_id,
        runtime_action_hash=trace.runtime_action_hash,
        business_rule_ref=trace.business_rule_ref,
        registry_rule_ref=trace.registry_rule_ref,
        manifest_object_ref=trace.manifest_object_ref,
        requirement_ref=trace.requirement_ref,
        trace_document=trace.model_dump(mode="json"),
        trace_hash=trace.trace_hash,
    )
    session.add(row)
    await session.commit()
    return R7RuntimeGovernanceTraceResponse.model_validate(row)


@router.post(
    "/{project_id}/uerm/deployments/{deployment_id}/errors",
    response_model=R7RuntimeErrorResponse,
    status_code=201,
)
async def record_uerm_runtime_error(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    request: R7RuntimeErrorRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7RuntimeErrorResponse:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    count = len(
        (
            await session.scalars(
                select(R7RuntimeErrorModel).where(
                    R7RuntimeErrorModel.runtime_deployment_id == deployment.id
                )
            )
        ).all()
    )
    context = _context_from_request(request.context)
    error = runtime_error(
        index=count + 1,
        deployment_hash=deployment.deployment_hash,
        severity=UermErrorSeverity(request.severity),
        category=UermErrorCategory(request.category),
        source=request.source,
        correlation_id=context.correlation_id,
        message=request.message,
        code=request.code,
        recovery_guidance=request.recovery_guidance,
        context_hash=context.context_hash,
    )
    row = R7RuntimeErrorModel(
        id=uuid.uuid4(),
        project_id=project_id,
        runtime_deployment_id=deployment.id,
        error_id=error.error_id,
        severity=error.severity.value,
        category=error.category.value,
        source=error.source,
        correlation_id=error.correlation_id,
        code=error.code,
        message=error.message,
        recovery_guidance=error.recovery_guidance,
        context_document=context.model_dump(mode="json"),
        error_document=error.model_dump(mode="json"),
        error_hash=error.error_hash,
    )
    session.add(row)
    await session.commit()
    return R7RuntimeErrorResponse.model_validate(row)


@router.get(
    "/{project_id}/uerm/deployments/{deployment_id}/errors",
    response_model=list[R7RuntimeErrorResponse],
)
async def list_uerm_runtime_errors(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> list[R7RuntimeErrorResponse]:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    rows = (
        await session.scalars(
            select(R7RuntimeErrorModel)
            .where(R7RuntimeErrorModel.runtime_deployment_id == deployment.id)
            .order_by(R7RuntimeErrorModel.created_at.desc())
        )
    ).all()
    return [R7RuntimeErrorResponse.model_validate(row) for row in rows]


@router.post(
    "/{project_id}/uerm/errors/{runtime_error_id}/recovery-actions",
    response_model=R7RecoveryActionResponse,
    status_code=201,
)
async def record_uerm_recovery_action(
    project_id: uuid.UUID,
    runtime_error_id: uuid.UUID,
    request: R7RecoveryActionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7RecoveryActionResponse:
    _require_human(actor)
    error = await session.get(R7RuntimeErrorModel, runtime_error_id)
    if error is None or error.project_id != project_id:
        raise HTTPException(status_code=404, detail="Runtime error not found")
    count = len(
        (
            await session.scalars(
                select(R7RecoveryActionModel).where(
                    R7RecoveryActionModel.runtime_error_id == error.id
                )
            )
        ).all()
    )
    action = recovery_action(
        index=count + 1,
        error_hash=error.error_hash,
        strategy=UermRecoveryStrategy(request.strategy),
        status=UermRecoveryStatus(request.status),
        policy_document=request.policy_document,
    )
    row = R7RecoveryActionModel(
        id=uuid.uuid4(),
        project_id=project_id,
        runtime_error_id=error.id,
        recovery_id=action.recovery_id,
        strategy=action.strategy.value,
        status=action.status.value,
        policy_document=action.policy_document,
        action_document=action.model_dump(mode="json"),
        action_hash=action.action_hash,
    )
    session.add(row)
    await session.commit()
    return R7RecoveryActionResponse.model_validate(row)


@router.post(
    "/{project_id}/uerm/deployments/{deployment_id}/digital-twin-snapshots",
    response_model=R7DigitalTwinSnapshotResponse,
    status_code=201,
)
async def record_uerm_digital_twin_snapshot(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    request: R7DigitalTwinSnapshotRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R7DigitalTwinSnapshotResponse:
    _require_human(actor)
    deployment = await _deployment(session, project_id, deployment_id)
    count = len(
        (
            await session.scalars(
                select(R7DigitalTwinSnapshotModel).where(
                    R7DigitalTwinSnapshotModel.runtime_deployment_id == deployment.id
                )
            )
        ).all()
    )
    snapshot = digital_twin_snapshot(
        index=count + 1,
        deployment=_deployment_domain(deployment),
        health_status=UermHealthStatus(request.health_status),
        metrics=request.metrics,
        configuration=request.configuration,
        active_workflows=tuple(request.active_workflows),
        event_flows=tuple(request.event_flows),
    )
    row = R7DigitalTwinSnapshotModel(
        id=uuid.uuid4(),
        project_id=project_id,
        runtime_deployment_id=deployment.id,
        snapshot_id=snapshot.snapshot_id,
        health_status=snapshot.health_status.value,
        topology_document=snapshot.topology,
        metrics_document=snapshot.metrics,
        configuration_document=snapshot.configuration,
        snapshot_document=snapshot.model_dump(mode="json"),
        snapshot_hash=snapshot.snapshot_hash,
    )
    session.add(row)
    await session.commit()
    return R7DigitalTwinSnapshotResponse.model_validate(row)


async def _published_r6_build(
    session: object, project_id: uuid.UUID, build_id: uuid.UUID
) -> R6GenerationBuildModel:
    await _project(session, project_id)
    build = await session.get(R6GenerationBuildModel, build_id)
    if build is None or build.project_id != project_id:
        raise HTTPException(status_code=404, detail="UAGF build not found")
    rows = (
        await session.scalars(
            select(R6LifecycleEventModel)
            .where(
                R6LifecycleEventModel.generation_build_id == build.id,
                R6LifecycleEventModel.file_id.is_(None),
            )
            .order_by(R6LifecycleEventModel.event_id)
        )
    ).all()
    try:
        status = current_uagf_lifecycle_status(
            tuple(_r6_lifecycle_event_from_row(row) for row in rows)
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if status is not UagfFileLifecycle.PUBLISHED:
        raise HTTPException(status_code=409, detail="R6 build must be published before runtime")
    return build


async def _project(session: object, project_id: uuid.UUID) -> ProjectModel:
    project = await session.get(ProjectModel, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _deployment(
    session: object, project_id: uuid.UUID, deployment_id: uuid.UUID
) -> R7RuntimeDeploymentModel:
    await _project(session, project_id)
    deployment = await session.get(R7RuntimeDeploymentModel, deployment_id)
    if deployment is None or deployment.project_id != project_id:
        raise HTTPException(status_code=404, detail="Runtime deployment not found")
    return deployment


async def _provider(
    session: object, project_id: uuid.UUID, provider_id: uuid.UUID
) -> R7RuntimeProviderModel:
    await _project(session, project_id)
    provider = await session.get(R7RuntimeProviderModel, provider_id)
    if provider is None or provider.project_id != project_id:
        raise HTTPException(status_code=404, detail="Runtime provider not found")
    return provider


def _deployment_domain(row: R7RuntimeDeploymentModel) -> UermRuntimeDeployment:
    return UermRuntimeDeployment.model_validate(row.deployment_document)


def _provider_domain(row: R7RuntimeProviderModel) -> UermRuntimeProvider:
    return UermRuntimeProvider.model_validate(row.provider_document)


def _runtime_event_domain(row: R7RuntimeEventModel) -> UermRuntimeEvent:
    return UermRuntimeEvent.model_construct(
        schema_version="uerm-runtime-event-0.1",
        event_id=row.event_id,
        deployment_hash="0" * 64,
        event_type=row.event_type,
        context=UermRuntimeContext.model_validate(row.context_document),
        payload=row.payload_document,
        manifest_rule_ref=row.manifest_rule_ref,
        event_hash=row.event_hash,
    )


def _context_from_request(request: object) -> UermRuntimeContext:
    return runtime_context(
        request_id=request.request_id,
        correlation_id=request.correlation_id,
        tenant=request.tenant,
        user=request.user,
        role=request.role,
        permissions=tuple(request.permissions),
        session_id=request.session_id,
        locale=request.locale,
        time_zone=request.time_zone,
        manifest_version=request.manifest_version,
        application_version=request.application_version,
    )


async def _policy_evaluation_count(
    session: object, deployment: R7RuntimeDeploymentModel
) -> int:
    return len(
        (
            await session.scalars(
                select(R7PolicyEvaluationModel).where(
                    R7PolicyEvaluationModel.runtime_deployment_id == deployment.id
                )
            )
        ).all()
    )


def _policy_evaluation_row(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    provider: R7RuntimeProviderModel | None,
    context: UermRuntimeContext,
    evaluation: UermPolicyEvaluation,
) -> R7PolicyEvaluationModel:
    return R7PolicyEvaluationModel(
        id=uuid.uuid4(),
        project_id=project_id,
        runtime_deployment_id=deployment_id,
        runtime_provider_id=provider.id if provider is not None else None,
        evaluation_id=evaluation.evaluation_id,
        action=evaluation.action,
        resource=evaluation.resource,
        decision=evaluation.decision.value,
        matched_policies=list(evaluation.matched_policies),
        reason=evaluation.reason,
        context_document=context.model_dump(mode="json"),
        evaluation_document=evaluation.model_dump(mode="json"),
        evaluation_hash=evaluation.evaluation_hash,
    )


async def _workflow_rows(
    session: object, deployment: R7RuntimeDeploymentModel
) -> list[R7WorkflowInstanceModel]:
    return list(
        (
            await session.scalars(
                select(R7WorkflowInstanceModel)
                .where(R7WorkflowInstanceModel.runtime_deployment_id == deployment.id)
                .order_by(R7WorkflowInstanceModel.created_at)
            )
        ).all()
    )


async def _synchronization_rows(
    session: object, deployment: R7RuntimeDeploymentModel
) -> list[R7RuntimeSynchronizationReportModel]:
    return list(
        (
            await session.scalars(
                select(R7RuntimeSynchronizationReportModel)
                .where(
                    R7RuntimeSynchronizationReportModel.runtime_deployment_id
                    == deployment.id
                )
                .order_by(R7RuntimeSynchronizationReportModel.created_at.desc())
            )
        ).all()
    )


def _synchronization_row(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    report: UermRuntimeSynchronizationReport,
) -> R7RuntimeSynchronizationReportModel:
    return R7RuntimeSynchronizationReportModel(
        id=uuid.uuid4(),
        project_id=project_id,
        runtime_deployment_id=deployment_id,
        synchronization_id=report.synchronization_id,
        status=report.status.value,
        findings=list(report.findings),
        observed_runtime_document=report.observed_runtime_document,
        report_document=report.model_dump(mode="json"),
        report_hash=report.report_hash,
    )


async def _latest_workflow_row(
    session: object,
    deployment: R7RuntimeDeploymentModel,
    workflow_instance_id: str,
) -> R7WorkflowInstanceModel:
    row = await session.scalar(
        select(R7WorkflowInstanceModel)
        .where(
            R7WorkflowInstanceModel.runtime_deployment_id == deployment.id,
            R7WorkflowInstanceModel.workflow_instance_id == workflow_instance_id,
        )
        .order_by(R7WorkflowInstanceModel.created_at.desc())
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Workflow instance not found")
    return row


def _workflow_domain(row: R7WorkflowInstanceModel) -> UermWorkflowInstance:
    return UermWorkflowInstance.model_validate(row.workflow_document)


def _workflow_row(
    project_id: uuid.UUID,
    deployment_id: uuid.UUID,
    instance: UermWorkflowInstance,
) -> R7WorkflowInstanceModel:
    return R7WorkflowInstanceModel(
        id=uuid.uuid4(),
        project_id=project_id,
        runtime_deployment_id=deployment_id,
        workflow_instance_id=instance.workflow_instance_id,
        workflow_key=instance.workflow_key,
        previous_state=instance.previous_state,
        current_state=instance.current_state,
        status=instance.status.value,
        context_document=instance.context.model_dump(mode="json"),
        workflow_document=instance.model_dump(mode="json"),
        instance_hash=instance.instance_hash,
    )


def _r6_lifecycle_event_from_row(row: R6LifecycleEventModel) -> UagfLifecycleEvent:
    return UagfLifecycleEvent(
        event_id=row.event_id,
        build_hash=row.build_hash,
        file_id=row.file_id,
        event_type=UagfLifecycleEventType(row.event_type),
        from_status=UagfFileLifecycle(row.from_status),
        to_status=UagfFileLifecycle(row.to_status),
        actor=row.actor,
        reason=row.reason,
        policy_document=row.policy_document,
        event_hash=row.event_hash,
    )


def _runtime_provider_readiness(provider: R7RuntimeProviderModel) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    required: list[str] = []
    configuration = provider.configuration_document
    endpoint_ref = provider.endpoint_ref
    kind = UermRuntimeProviderKind(provider.kind)

    _readiness_check(
        checks,
        "provider_status",
        provider.status == UermRuntimeProviderStatus.AVAILABLE.value,
        f"Provider status is {provider.status}.",
        "Set provider status to available only after runtime credentials/config are mounted.",
    )
    _readiness_check(
        checks,
        "provider_configuration",
        bool(configuration) or bool(endpoint_ref),
        "Provider has endpoint_ref or configuration document.",
        "Register endpoint_ref and non-secret adapter configuration for the provider.",
    )

    if kind is UermRuntimeProviderKind.EVENT_BUS:
        required.extend(["event bus endpoint", "publisher credentials", "topic/exchange policy"])
        adapter = str(configuration.get("adapter", "generic"))
        if adapter == "kafka":
            bootstrap = str(configuration.get("bootstrap_servers") or endpoint_ref or "")
            _readiness_check(
                checks,
                "kafka_bootstrap",
                bool(bootstrap),
                "Kafka bootstrap servers are configured.",
                "Set provider.configuration.bootstrap_servers or endpoint_ref.",
            )
            if bootstrap and shutil.which("kafka-topics"):
                ok, detail = _probe_command(
                    ("kafka-topics", "--bootstrap-server", bootstrap, "--list"),
                    timeout=20,
                )
                _readiness_check(
                    checks,
                    "kafka_metadata_probe",
                    ok,
                    detail,
                    "Grant metadata/list access to the Kafka cluster.",
                )
        elif adapter == "rabbitmq":
            _readiness_check(
                checks,
                "rabbitmq_endpoint",
                bool(endpoint_ref and endpoint_ref.startswith(("amqp://", "amqps://"))),
                "RabbitMQ endpoint uses amqp:// or amqps://.",
                "Set provider.endpoint_ref to an AMQP broker URL.",
            )
        else:
            _readiness_check(
                checks,
                "event_bus_endpoint",
                bool(endpoint_ref),
                "Generic event bus endpoint is configured.",
                "Set provider.endpoint_ref or provider.configuration adapter-specific settings.",
            )
    elif kind is UermRuntimeProviderKind.DEPLOYMENT_RUNTIME:
        required.extend(["kubectl", "cluster credentials", "deployment namespace"])
        _readiness_check(
            checks,
            "kubectl_executable",
            shutil.which("kubectl") is not None,
            "kubectl executable is available.",
            "Install kubectl in the API runtime image.",
        )
        kubeconfig_path = get_settings().r7_runtime_kubeconfig_path
        if kubeconfig_path is not None:
            _readiness_check(
                checks,
                "kubeconfig",
                kubeconfig_path.exists(),
                "Configured kubeconfig path exists.",
                "Mount R7_RUNTIME_KUBECONFIG_PATH into the API runtime.",
            )
        if shutil.which("kubectl"):
            ok, detail = _probe_command(
                ("kubectl", "version", "--client=true"),
                timeout=10,
                env=_runtime_probe_environment(),
            )
            _readiness_check(
                checks,
                "kubectl_client_probe",
                ok,
                detail,
                "Ensure kubectl can run inside the API runtime.",
            )
    elif kind is UermRuntimeProviderKind.POLICY_ENGINE:
        required.extend(["policy endpoint or OPA binary", "policy bundle", "decision path"])
        opa_url = str(configuration.get("opa_url") or get_settings().r7_runtime_opa_url or "")
        _readiness_check(
            checks,
            "policy_endpoint",
            bool(endpoint_ref or opa_url or shutil.which("opa")),
            "Policy engine endpoint or OPA executable is configured.",
            "Set provider.endpoint_ref, R7_RUNTIME_OPA_URL, or install opa.",
        )
        if opa_url:
            ok, detail = _probe_http(opa_url.rstrip("/") + "/health", timeout=10)
            _readiness_check(
                checks,
                "opa_health_probe",
                ok,
                detail,
                "Expose OPA /health to the API runtime network.",
            )
    elif kind is UermRuntimeProviderKind.AI_SERVICE:
        required.extend(
            ["AI provider endpoint", "AI provider credentials", "model/capability mapping"]
        )
        adapter = str(configuration.get("adapter", "generic"))
        if adapter == "ollama":
            base_url = str(endpoint_ref or configuration.get("base_url") or "")
            _readiness_check(
                checks,
                "ollama_endpoint",
                bool(base_url),
                "Ollama endpoint is configured.",
                "Set provider.endpoint_ref or configuration.base_url.",
            )
            if base_url:
                ok, detail = _probe_http(base_url.rstrip("/") + "/api/tags", timeout=10)
                _readiness_check(
                    checks,
                    "ollama_probe",
                    ok,
                    detail,
                    "Ensure Ollama is reachable from the API runtime.",
                )
        elif adapter == "openai":
            has_key = bool(
                get_settings().r7_runtime_openai_api_key or os.environ.get("OPENAI_API_KEY")
            )
            _readiness_check(
                checks,
                "openai_credentials",
                has_key,
                "OpenAI credentials are configured.",
                "Set R7_RUNTIME_OPENAI_API_KEY or OPENAI_API_KEY.",
            )
        else:
            _readiness_check(
                checks,
                "ai_endpoint",
                bool(endpoint_ref),
                "AI service endpoint is configured.",
                "Set provider.endpoint_ref and provider credentials through environment.",
            )
    elif kind is UermRuntimeProviderKind.PLUGIN_RUNTIME:
        required.extend(["plugin runtime root", "plugin command", "capability manifest"])
        plugin_root = get_settings().r7_runtime_plugin_root
        plugin_command = configuration.get("plugin_command")
        if plugin_root is not None:
            _readiness_check(
                checks,
                "plugin_root",
                plugin_root.exists(),
                "Configured plugin root exists.",
                "Mount R7_RUNTIME_PLUGIN_ROOT into the API runtime.",
            )
        _readiness_check(
            checks,
            "plugin_command",
            bool(plugin_command and shutil.which(str(plugin_command))),
            "Plugin command executable is available.",
            "Set provider.configuration.plugin_command to an installed executable.",
        )

    return {
        "ready": all(bool(item["ok"]) for item in checks),
        "checks": checks,
        "required_configuration": required,
    }


def _readiness_check(
    checks: list[dict[str, object]],
    name: str,
    ok: bool,
    detail: str,
    action: str,
) -> None:
    checks.append({"name": name, "ok": ok, "detail": detail, "action": action})


def _probe_command(
    command: tuple[str, ...],
    *,
    timeout: int,
    env: dict[str, str] | None = None,
) -> tuple[bool, str]:
    if shutil.which(command[0]) is None:
        return False, f"Executable is not installed: {command[0]}"
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return False, f"Readiness probe timed out: {' '.join(command[:2])}"
    if completed.returncode == 0:
        return True, "Readiness probe succeeded."
    output = (completed.stderr or completed.stdout).strip()
    return False, output[:500] or "Readiness probe failed."


def _probe_http(url: str, *, timeout: int) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            if 200 <= response.status < 300:
                return True, "HTTP readiness probe succeeded."
            return False, f"HTTP readiness probe returned status {response.status}."
    except (urllib.error.URLError, TimeoutError) as exc:
        return False, str(exc)[:500]


def _runtime_probe_environment() -> dict[str, str]:
    env = dict(os.environ)
    kubeconfig_path = get_settings().r7_runtime_kubeconfig_path
    if kubeconfig_path is not None:
        env["KUBECONFIG"] = str(kubeconfig_path)
    return env
