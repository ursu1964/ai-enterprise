from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from ai_enterprise.api.dependencies import ActorDependency, SessionDependency, SettingsDependency
from ai_enterprise.api.r9_uak_schemas import (
    R9AiSessionBoundaryRequest,
    R9DeploymentCoordinationRequest,
    R9KernelDashboardResponse,
    R9KernelEventRequest,
    R9KernelRecordResponse,
    R9KernelReplayResponse,
    R9KernelTransactionRequest,
    R9LifecycleSnapshotRequest,
    R9MonitoringAggregateRequest,
    R9OperationalReadinessResponse,
    R9PlatformCheckpointRequest,
    R9PluginRegistrationRequest,
    R9RegistrySnapshotRequest,
    R9ResourceAllocationRequest,
    R9ScheduleDispatchResponse,
    R9SchedulePlanRequest,
    R9SdkContractRequest,
    R9SdkPackageMaterializationResponse,
    R9SdkRegistryPublicationRequest,
    R9SdkRegistryPublicationResponse,
    R9SecurityEnvelopeRequest,
    R9SubsystemRegistrationRequest,
    R9WorkspaceHierarchyRequest,
)
from ai_enterprise.application.r9_uak_runtime import (
    KernelRecordView,
    KernelRuntimeError,
    dispatch_ready_schedules,
    materialize_sdk_package,
    publish_sdk_package_to_registry,
    r9_operational_readiness,
    replay_kernel_events,
)
from ai_enterprise.domain.r9_uak import (
    UakCheckpointKind,
    UakDeploymentEnvironment,
    UakLifecycleState,
    UakPluginCategory,
    UakSdkContract,
    UakSdkLanguage,
    UakSubsystem,
    ai_session_boundary,
    deployment_coordination,
    kernel_event,
    kernel_transaction,
    lifecycle_snapshot,
    monitoring_aggregate,
    platform_checkpoint,
    plugin_registration,
    registry_snapshot,
    resource_allocation,
    schedule_plan,
    sdk_contract,
    security_envelope,
    subsystem_registration,
    workspace_hierarchy,
)
from ai_enterprise.infrastructure.database.models import ProjectModel
from ai_enterprise.infrastructure.knowledge.models import R9KernelRecordModel
from ai_enterprise.infrastructure.organization.models import OrganizationModel

router = APIRouter(prefix="/kernel", tags=["r9-uak"])


def _require_kernel_actor(actor: object) -> None:
    if getattr(actor, "actor_type", None) != "human":
        raise HTTPException(status_code=403, detail="Kernel orchestration requires a human actor")


@router.post(
    "/subsystems",
    response_model=R9KernelRecordResponse,
    status_code=201,
)
async def register_uak_subsystem(
    request: R9SubsystemRegistrationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R9KernelRecordResponse:
    _require_kernel_actor(actor)
    await _validate_scope(session, request)
    value = subsystem_registration(
        index=(await _record_count(session, request.scope_type, request.scope_id, "subsystem")) + 1,
        subsystem=UakSubsystem(request.subsystem),
        implementation_ref=request.implementation_ref,
        capabilities=tuple(request.capabilities),
        dependencies=tuple(UakSubsystem(item) for item in request.dependencies),
    )
    row = _row(request, "subsystem", value, actor.subject)
    session.add(row)
    await session.commit()
    return R9KernelRecordResponse.model_validate(row)


@router.post("/events", response_model=R9KernelRecordResponse, status_code=201)
async def record_uak_event(
    request: R9KernelEventRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R9KernelRecordResponse:
    _require_kernel_actor(actor)
    await _validate_scope(session, request)
    value = kernel_event(
        index=(await _record_count(session, request.scope_type, request.scope_id, "event")) + 1,
        event_type=request.event_type,
        source_subsystem=UakSubsystem(request.source_subsystem),
        target_subsystem=UakSubsystem(request.target_subsystem),
        object_identity=request.object_identity,
        payload_hash=request.payload_hash,
        causation_hash=request.causation_hash,
    )
    row = _row(request, "event", value, actor.subject)
    session.add(row)
    await session.commit()
    return R9KernelRecordResponse.model_validate(row)


@router.post("/lifecycle-states", response_model=R9KernelRecordResponse, status_code=201)
async def record_uak_lifecycle_state(
    request: R9LifecycleSnapshotRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R9KernelRecordResponse:
    _require_kernel_actor(actor)
    await _validate_scope(session, request)
    if request.project_id is None:
        raise HTTPException(status_code=422, detail="Lifecycle snapshots require project_id")
    value = lifecycle_snapshot(
        index=(
            await _record_count(session, request.scope_type, request.scope_id, "lifecycle_snapshot")
        )
        + 1,
        project_id=str(request.project_id),
        object_identity=request.object_identity,
        state=UakLifecycleState(request.state),
        triggering_event_hash=request.triggering_event_hash,
    )
    row = _row(request, "lifecycle_snapshot", value, actor.subject)
    session.add(row)
    await session.commit()
    return R9KernelRecordResponse.model_validate(row)


@router.post("/transactions", response_model=R9KernelRecordResponse, status_code=201)
async def record_uak_transaction(
    request: R9KernelTransactionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R9KernelRecordResponse:
    _require_kernel_actor(actor)
    await _validate_scope(session, request)
    value = kernel_transaction(
        index=(
            await _record_count(session, request.scope_type, request.scope_id, "transaction")
        )
        + 1,
        operation_type=request.operation_type,
        object_identity=request.object_identity,
        steps=tuple(request.steps),
        committed_hashes=tuple(request.committed_hashes),
        rollback_steps=tuple(request.rollback_steps),
        rolled_back_hashes=tuple(request.rolled_back_hashes),
    )
    row = _row(request, "transaction", value, actor.subject)
    session.add(row)
    await session.commit()
    return R9KernelRecordResponse.model_validate(row)


@router.post("/checkpoints", response_model=R9KernelRecordResponse, status_code=201)
async def record_uak_checkpoint(
    request: R9PlatformCheckpointRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R9KernelRecordResponse:
    _require_kernel_actor(actor)
    await _validate_scope(session, request)
    value = platform_checkpoint(
        index=(await _record_count(session, request.scope_type, request.scope_id, "checkpoint"))
        + 1,
        checkpoint_kind=UakCheckpointKind(request.checkpoint_kind),
        completed_steps=tuple(request.completed_steps),
    )
    row = _row(request, "checkpoint", value, actor.subject)
    session.add(row)
    await session.commit()
    return R9KernelRecordResponse.model_validate(row)


@router.post("/plugins", response_model=R9KernelRecordResponse, status_code=201)
async def register_uak_plugin(
    request: R9PluginRegistrationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R9KernelRecordResponse:
    _require_kernel_actor(actor)
    await _validate_scope(session, request)
    value = plugin_registration(
        index=(await _record_count(session, request.scope_type, request.scope_id, "plugin")) + 1,
        plugin_key=request.plugin_key,
        category=UakPluginCategory(request.category),
        version=request.version,
        capability_refs=tuple(request.capability_refs),
        extension_points=tuple(UakSubsystem(item) for item in request.extension_points),
        signed_artifact_hash=request.signed_artifact_hash,
    )
    row = _row(request, "plugin", value, actor.subject)
    session.add(row)
    await session.commit()
    return R9KernelRecordResponse.model_validate(row)


@router.post("/ai-session-boundaries", response_model=R9KernelRecordResponse, status_code=201)
async def record_uak_ai_session_boundary(
    request: R9AiSessionBoundaryRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R9KernelRecordResponse:
    _require_kernel_actor(actor)
    await _validate_scope(session, request)
    value = ai_session_boundary(
        index=(
            await _record_count(
                session, request.scope_type, request.scope_id, "ai_session_boundary"
            )
        )
        + 1,
        model_ref=request.model_ref,
        approved_context_refs=tuple(request.approved_context_refs),
        approved_registry_refs=tuple(request.approved_registry_refs),
        approved_object_refs=tuple(request.approved_object_refs),
        approved_template_refs=tuple(request.approved_template_refs),
        approved_permission_refs=tuple(request.approved_permission_refs),
    )
    row = _row(request, "ai_session_boundary", value, actor.subject)
    session.add(row)
    await session.commit()
    return R9KernelRecordResponse.model_validate(row)


@router.post("/workspace-hierarchies", response_model=R9KernelRecordResponse, status_code=201)
async def record_uak_workspace_hierarchy(
    request: R9WorkspaceHierarchyRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R9KernelRecordResponse:
    _require_kernel_actor(actor)
    await _validate_scope(session, request)
    value = workspace_hierarchy(
        index=(await _record_count(session, request.scope_type, request.scope_id, "workspace"))
        + 1,
        tenant_ref=request.tenant_ref,
        workspace_ref=request.workspace_ref,
        portfolio_ref=request.portfolio_ref,
        project_ref=request.project_ref,
        manifest_ref=request.manifest_ref,
        reusable_knowledge_refs=tuple(request.reusable_knowledge_refs),
    )
    row = _row(request, "workspace", value, actor.subject)
    session.add(row)
    await session.commit()
    return R9KernelRecordResponse.model_validate(row)


@router.post("/schedules", response_model=R9KernelRecordResponse, status_code=201)
async def record_uak_schedule_plan(
    request: R9SchedulePlanRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R9KernelRecordResponse:
    _require_kernel_actor(actor)
    await _validate_scope(session, request)
    value = schedule_plan(
        index=(await _record_count(session, request.scope_type, request.scope_id, "schedule")) + 1,
        work_type=request.work_type,
        object_identity=request.object_identity,
        dependencies=tuple(request.dependencies),
        unsatisfied_dependencies=tuple(request.unsatisfied_dependencies),
        resource_claims=request.resource_claims,
    )
    row = _row(request, "schedule", value, actor.subject)
    session.add(row)
    await session.commit()
    return R9KernelRecordResponse.model_validate(row)


@router.post("/resource-allocations", response_model=R9KernelRecordResponse, status_code=201)
async def record_uak_resource_allocation(
    request: R9ResourceAllocationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R9KernelRecordResponse:
    _require_kernel_actor(actor)
    await _validate_scope(session, request)
    value = resource_allocation(
        index=(await _record_count(session, request.scope_type, request.scope_id, "resource"))
        + 1,
        schedule_ref=request.schedule_ref,
        requested_resources=request.requested_resources,
        allocated_resources=request.allocated_resources,
    )
    row = _row(request, "resource", value, actor.subject)
    session.add(row)
    await session.commit()
    return R9KernelRecordResponse.model_validate(row)


@router.post("/sdk-contracts", response_model=R9KernelRecordResponse, status_code=201)
async def record_uak_sdk_contract(
    request: R9SdkContractRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R9KernelRecordResponse:
    _require_kernel_actor(actor)
    await _validate_scope(session, request)
    value = sdk_contract(
        index=(await _record_count(session, request.scope_type, request.scope_id, "sdk")) + 1,
        language=UakSdkLanguage(request.language),
        contract_version=request.contract_version,
        api_surfaces=tuple(request.api_surfaces),
        canonical_contract_hash=request.canonical_contract_hash,
        package_ref=request.package_ref,
    )
    row = _row(request, "sdk", value, actor.subject)
    session.add(row)
    await session.commit()
    return R9KernelRecordResponse.model_validate(row)


@router.post("/registry-snapshots", response_model=R9KernelRecordResponse, status_code=201)
async def record_uak_registry_snapshot(
    request: R9RegistrySnapshotRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R9KernelRecordResponse:
    _require_kernel_actor(actor)
    await _validate_scope(session, request)
    value = registry_snapshot(
        index=(await _record_count(session, request.scope_type, request.scope_id, "registry"))
        + 1,
        updl_registry_hash=request.updl_registry_hash,
        object_registry_hash=request.object_registry_hash,
        rule_registry_hash=request.rule_registry_hash,
        generator_registry_hash=request.generator_registry_hash,
        template_registry_hash=request.template_registry_hash,
        policy_registry_hash=request.policy_registry_hash,
    )
    row = _row(request, "registry", value, actor.subject)
    session.add(row)
    await session.commit()
    return R9KernelRecordResponse.model_validate(row)


@router.post("/security-envelopes", response_model=R9KernelRecordResponse, status_code=201)
async def record_uak_security_envelope(
    request: R9SecurityEnvelopeRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R9KernelRecordResponse:
    _require_kernel_actor(actor)
    await _validate_scope(session, request)
    value = security_envelope(
        index=(await _record_count(session, request.scope_type, request.scope_id, "security")) + 1,
        actor_identity_ref=request.actor_identity_ref,
        authorization_policy_refs=tuple(request.authorization_policy_refs),
        certificate_refs=tuple(request.certificate_refs),
        secret_refs=tuple(request.secret_refs),
    )
    row = _row(request, "security", value, actor.subject)
    session.add(row)
    await session.commit()
    return R9KernelRecordResponse.model_validate(row)


@router.post("/deployment-coordinations", response_model=R9KernelRecordResponse, status_code=201)
async def record_uak_deployment_coordination(
    request: R9DeploymentCoordinationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R9KernelRecordResponse:
    _require_kernel_actor(actor)
    await _validate_scope(session, request)
    value = deployment_coordination(
        index=(await _record_count(session, request.scope_type, request.scope_id, "deployment"))
        + 1,
        environment=UakDeploymentEnvironment(request.environment),
        manifest_ref=request.manifest_ref,
        deployment_provider_ref=request.deployment_provider_ref,
        runtime_ref=request.runtime_ref,
        deployment_hashes=tuple(request.deployment_hashes),
    )
    row = _row(request, "deployment", value, actor.subject)
    session.add(row)
    await session.commit()
    return R9KernelRecordResponse.model_validate(row)


@router.post("/monitoring-aggregates", response_model=R9KernelRecordResponse, status_code=201)
async def record_uak_monitoring_aggregate(
    request: R9MonitoringAggregateRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R9KernelRecordResponse:
    _require_kernel_actor(actor)
    await _validate_scope(session, request)
    value = monitoring_aggregate(
        index=(await _record_count(session, request.scope_type, request.scope_id, "monitoring"))
        + 1,
        metrics_by_domain=request.metrics_by_domain,
        source_record_hashes=tuple(request.source_record_hashes),
    )
    row = _row(request, "monitoring", value, actor.subject)
    session.add(row)
    await session.commit()
    return R9KernelRecordResponse.model_validate(row)


@router.get("/records", response_model=list[R9KernelRecordResponse])
async def list_uak_records(
    session: SessionDependency,
    actor: ActorDependency,
    scope_type: str,
    scope_id: str,
    record_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[R9KernelRecordResponse]:
    _require_kernel_actor(actor)
    query = select(R9KernelRecordModel).where(
        R9KernelRecordModel.scope_type == scope_type,
        R9KernelRecordModel.scope_id == scope_id,
    )
    if record_type is not None:
        query = query.where(R9KernelRecordModel.record_type == record_type)
    rows = (
        await session.scalars(query.order_by(R9KernelRecordModel.created_at.desc()).limit(limit))
    ).all()
    return [R9KernelRecordResponse.model_validate(row) for row in rows]


@router.get("/dashboard", response_model=R9KernelDashboardResponse)
async def uak_dashboard(
    session: SessionDependency,
    actor: ActorDependency,
    scope_type: str,
    scope_id: str,
) -> R9KernelDashboardResponse:
    _require_kernel_actor(actor)
    rows = (
        await session.scalars(
            select(R9KernelRecordModel)
            .where(
                R9KernelRecordModel.scope_type == scope_type,
                R9KernelRecordModel.scope_id == scope_id,
            )
            .order_by(R9KernelRecordModel.created_at.desc())
        )
    ).all()
    return R9KernelDashboardResponse(
        scope_type=scope_type,
        scope_id=scope_id,
        subsystem_count=sum(1 for row in rows if row.record_type == "subsystem"),
        event_count=sum(1 for row in rows if row.record_type == "event"),
        latest_lifecycle_state=_latest_status(rows, "lifecycle_snapshot"),
        committed_transaction_count=sum(
            1 for row in rows if row.record_type == "transaction" and row.status == "committed"
        ),
        rolled_back_transaction_count=sum(
            1 for row in rows if row.record_type == "transaction" and row.status == "rolled_back"
        ),
        ready_checkpoint_count=sum(
            1 for row in rows if row.record_type == "checkpoint" and row.status == "ready"
        ),
        blocked_checkpoint_count=sum(
            1 for row in rows if row.record_type == "checkpoint" and row.status == "blocked"
        ),
        plugin_count=sum(1 for row in rows if row.record_type == "plugin"),
        ai_session_boundary_count=sum(
            1 for row in rows if row.record_type == "ai_session_boundary"
        ),
        workspace_hierarchy_count=sum(1 for row in rows if row.record_type == "workspace"),
        dispatchable_schedule_count=sum(
            1 for row in rows if row.record_type == "schedule" and row.status == "dispatchable"
        ),
        blocked_schedule_count=sum(
            1 for row in rows if row.record_type == "schedule" and row.status == "blocked"
        ),
        allocated_resource_count=sum(
            1 for row in rows if row.record_type == "resource" and row.status == "allocated"
        ),
        insufficient_resource_count=sum(
            1 for row in rows if row.record_type == "resource" and row.status == "insufficient"
        ),
        sdk_contract_count=sum(1 for row in rows if row.record_type == "sdk"),
        registry_snapshot_count=sum(1 for row in rows if row.record_type == "registry"),
        security_envelope_count=sum(1 for row in rows if row.record_type == "security"),
        deployment_coordination_count=sum(
            1 for row in rows if row.record_type == "deployment"
        ),
        monitoring_aggregate_count=sum(1 for row in rows if row.record_type == "monitoring"),
    )


@router.get("/runtime/replay", response_model=R9KernelReplayResponse)
async def replay_uak_events(
    session: SessionDependency,
    actor: ActorDependency,
    scope_type: str,
    scope_id: str,
) -> R9KernelReplayResponse:
    _require_kernel_actor(actor)
    rows = await _records(session, scope_type, scope_id)
    try:
        replay = replay_kernel_events(_views(rows))
    except KernelRuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    documents = [entry.model_dump(mode="json") for entry in replay]
    return R9KernelReplayResponse(
        events=documents,
        replay_hash=_runtime_document_hash({"events": documents}),
    )


@router.post("/runtime/dispatch-schedules", response_model=R9ScheduleDispatchResponse)
async def dispatch_uak_schedules(
    session: SessionDependency,
    actor: ActorDependency,
    scope_type: str,
    scope_id: str,
) -> R9ScheduleDispatchResponse:
    _require_kernel_actor(actor)
    rows = await _records(session, scope_type, scope_id)
    next_event_index = await _record_count(session, scope_type, scope_id, "event") + 1
    try:
        dispatches = dispatch_ready_schedules(_views(rows), start_event_index=next_event_index)
    except KernelRuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    scope = _RuntimeScope(scope_type=scope_type, scope_id=scope_id)
    event_rows = []
    for dispatch in dispatches:
        row = _row(scope, "event", dispatch.event, actor.subject)
        session.add(row)
        event_rows.append(row)
    await session.commit()
    return R9ScheduleDispatchResponse(
        dispatch_count=len(event_rows),
        events=[R9KernelRecordResponse.model_validate(row) for row in event_rows],
    )


@router.post(
    "/sdk-contracts/{record_id}/materialize",
    response_model=R9SdkPackageMaterializationResponse,
)
async def materialize_uak_sdk_contract(
    record_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
    settings: SettingsDependency,
) -> R9SdkPackageMaterializationResponse:
    _require_kernel_actor(actor)
    row = await session.get(R9KernelRecordModel, record_id)
    if row is None or row.record_type != "sdk":
        raise HTTPException(status_code=404, detail="UAK SDK contract not found")
    contract = UakSdkContract.model_validate(row.record_document)
    try:
        materialization = materialize_sdk_package(
            contract,
            (settings.artifact_root / "r9-sdk-packages").resolve(),
        )
    except KernelRuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return R9SdkPackageMaterializationResponse(
        **materialization.model_dump(mode="json", exclude={"files"}),
        files=list(materialization.files),
    )


@router.get(
    "/runtime/operational-readiness",
    response_model=R9OperationalReadinessResponse,
)
async def r9_runtime_operational_readiness(
    actor: ActorDependency,
    settings: SettingsDependency,
) -> R9OperationalReadinessResponse:
    _require_kernel_actor(actor)
    readiness = r9_operational_readiness(settings)
    return R9OperationalReadinessResponse(
        **readiness.model_dump(mode="json", exclude={"checks"}),
        checks=[item.model_dump(mode="json") for item in readiness.checks],
    )


@router.post(
    "/sdk-contracts/{record_id}/publish",
    response_model=R9SdkRegistryPublicationResponse,
)
async def publish_uak_sdk_contract(
    record_id: uuid.UUID,
    request: R9SdkRegistryPublicationRequest,
    session: SessionDependency,
    actor: ActorDependency,
    settings: SettingsDependency,
) -> R9SdkRegistryPublicationResponse:
    _require_kernel_actor(actor)
    row = await session.get(R9KernelRecordModel, record_id)
    if row is None or row.record_type != "sdk":
        raise HTTPException(status_code=404, detail="UAK SDK contract not found")
    contract = UakSdkContract.model_validate(row.record_document)
    try:
        materialization = materialize_sdk_package(
            contract,
            (settings.artifact_root / "r9-sdk-packages").resolve(),
        )
        publication = publish_sdk_package_to_registry(
            materialization,
            settings,
            dry_run=request.dry_run,
        )
    except KernelRuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return R9SdkRegistryPublicationResponse(
        **publication.model_dump(mode="json", exclude={"command"}),
        command=list(publication.command),
    )


async def _validate_scope(session: object, request: object) -> None:
    organization_id = getattr(request, "organization_id", None)
    project_id = getattr(request, "project_id", None)
    if (
        organization_id is not None
        and await session.get(OrganizationModel, organization_id) is None
    ):
        raise HTTPException(status_code=404, detail="Organization not found")
    if project_id is not None and await session.get(ProjectModel, project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")


async def _record_count(
    session: object,
    scope_type: str,
    scope_id: str,
    record_type: str,
) -> int:
    return len(
        (
            await session.scalars(
                select(R9KernelRecordModel).where(
                    R9KernelRecordModel.scope_type == scope_type,
                    R9KernelRecordModel.scope_id == scope_id,
                    R9KernelRecordModel.record_type == record_type,
                )
            )
        ).all()
    )


async def _records(
    session: object,
    scope_type: str,
    scope_id: str,
) -> list[R9KernelRecordModel]:
    return (
        await session.scalars(
            select(R9KernelRecordModel)
            .where(
                R9KernelRecordModel.scope_type == scope_type,
                R9KernelRecordModel.scope_id == scope_id,
            )
            .order_by(R9KernelRecordModel.created_at.asc(), R9KernelRecordModel.record_id.asc())
        )
    ).all()


def _row(
    request: object,
    record_type: str,
    value: object,
    created_by: str,
    parent_record_hash: str | None = None,
) -> R9KernelRecordModel:
    document = value.model_dump(mode="json")  # type: ignore[attr-defined]
    return R9KernelRecordModel(
        id=uuid.uuid4(),
        scope_type=request.scope_type,
        scope_id=request.scope_id,
        organization_id=getattr(request, "organization_id", None),
        project_id=getattr(request, "project_id", None),
        record_type=record_type,
        record_id=_document_record_id(document),
        status=_document_status(document),
        object_identity=document.get("object_identity"),
        parent_record_hash=parent_record_hash,
        record_document=document,
        record_hash=_document_hash(document),
        created_by=created_by,
    )


class _RuntimeScope:
    def __init__(self, *, scope_type: str, scope_id: str) -> None:
        self.scope_type = scope_type
        self.scope_id = scope_id
        self.organization_id = None
        self.project_id = None


def _views(rows: list[R9KernelRecordModel]) -> list[KernelRecordView]:
    return [
        KernelRecordView(
            record_type=row.record_type,
            record_id=row.record_id,
            status=row.status,
            record_document=row.record_document,
            record_hash=row.record_hash,
        )
        for row in rows
    ]


def _document_record_id(document: dict[str, Any]) -> str:
    for key in (
        "subsystem_id",
        "event_id",
        "lifecycle_id",
        "transaction_id",
        "checkpoint_id",
        "plugin_id",
        "ai_session_id",
        "hierarchy_id",
        "schedule_id",
        "allocation_id",
        "sdk_id",
        "registry_snapshot_id",
        "security_id",
        "deployment_coordination_id",
        "monitoring_id",
    ):
        if key in document:
            return str(document[key])
    raise HTTPException(status_code=422, detail="UAK record id missing")


def _document_hash(document: dict[str, Any]) -> str:
    for key in (
        "registration_hash",
        "event_hash",
        "lifecycle_hash",
        "transaction_hash",
        "checkpoint_hash",
        "boundary_hash",
        "hierarchy_hash",
        "schedule_hash",
        "allocation_hash",
        "sdk_hash",
        "registry_hash",
        "security_hash",
        "coordination_hash",
        "monitoring_hash",
    ):
        if key in document:
            return str(document[key])
    raise HTTPException(status_code=422, detail="UAK record hash missing")


def _document_status(document: dict[str, Any]) -> str:
    return str(document.get("status") or document.get("state") or "recorded")


def _latest_status(rows: list[R9KernelRecordModel], record_type: str) -> str | None:
    return next((row.status for row in rows if row.record_type == record_type), None)


def _runtime_document_hash(document: dict[str, Any]) -> str:
    from ai_enterprise.domain.specification.kernel import specification_hash

    return specification_hash(document)
