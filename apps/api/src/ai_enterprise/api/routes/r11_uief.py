from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from ai_enterprise.api.dependencies import ActorDependency, SessionDependency, SettingsDependency
from ai_enterprise.api.r11_uief_schemas import (
    R11AiIntegrationBoundaryRequest,
    R11ConnectorRegistrationRequest,
    R11ContractRegistrationRequest,
    R11DataMappingRequest,
    R11DeploymentPreflightResponse,
    R11DeveloperSurfaceResponse,
    R11DigitalTwinRequest,
    R11DocumentationBundleResponse,
    R11EcosystemReadinessResponse,
    R11EventDefinitionRequest,
    R11GenerationPlanResponse,
    R11ImpactAnalysisResponse,
    R11IntegrationDashboardResponse,
    R11IntegrationObjectRequest,
    R11MarketplaceAssetRequest,
    R11MigrationPlanResponse,
    R11ObservabilitySnapshotResponse,
    R11ProviderAbstractionRequest,
    R11ReconciliationResponse,
    R11RecordResponse,
    R11RetryPolicyRequest,
    R11RuntimeCompatibilityResponse,
    R11SandboxPlanResponse,
    R11SecurityPolicyRequest,
    R11SecurityReadinessResponse,
    R11TestPlanResponse,
    R11TopologyMapResponse,
)
from ai_enterprise.application.r11_uief_runtime import (
    UiefRecordView,
    analyze_compatibility,
    analyze_integration_impact,
    assess_ecosystem_readiness,
    build_generation_plan,
    build_migration_plan,
    build_sandbox_plan,
    build_test_plan,
    build_topology_map,
    describe_developer_surface,
    generate_integration_documentation,
    r11_deployment_preflight,
    reconcile_integrations,
    summarize_observability,
    validate_security_readiness,
)
from ai_enterprise.domain.r11_uief import (
    UiefCertificationLevel,
    UiefContractType,
    UiefHealthStatus,
    UiefIntegrationDomain,
    UiefIntegrationLifecycle,
    ai_integration_boundary,
    connector_registration,
    contract_registration,
    data_mapping,
    digital_twin,
    event_definition,
    integration_object,
    marketplace_asset,
    provider_abstraction,
    retry_policy,
    security_policy,
)
from ai_enterprise.infrastructure.database.models import ProjectModel
from ai_enterprise.infrastructure.knowledge.models import R11IntegrationRecordModel

router = APIRouter(prefix="/projects", tags=["r11-uief"])


def _require_human(actor: object) -> None:
    if getattr(actor, "actor_type", None) != "human":
        raise HTTPException(status_code=403, detail="Human integration authority is required")


@router.post("/{project_id}/uief/integrations", response_model=R11RecordResponse, status_code=201)
async def create_integration(
    project_id: uuid.UUID,
    request: R11IntegrationObjectRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = integration_object(
        integration_id=await _next_id(session, project_id, "integration", "UIEF-INT"),
        manifest_ref=request.manifest_ref,
        name=request.name,
        domain=UiefIntegrationDomain(request.domain),
        source_ref=request.source_ref,
        destination_ref=request.destination_ref,
        purpose=request.purpose,
        protocol=request.protocol,
        contract_ref=request.contract_ref,
        authentication_ref=request.authentication_ref,
        authorization_ref=request.authorization_ref,
        mapping_ref=request.mapping_ref,
        trigger=request.trigger,
        frequency=request.frequency,
        error_strategy_ref=request.error_strategy_ref,
        retry_policy_ref=request.retry_policy_ref,
        owner_ref=request.owner_ref,
        monitoring_ref=request.monitoring_ref,
        compliance_classification=request.compliance_classification,
        lifecycle_state=UiefIntegrationLifecycle(request.lifecycle_state),
        manifest_owned=True,
        approved_for_activation=request.approved_for_activation,
    )
    return await _persist(session, project_id, "integration", value, actor.subject)


@router.post("/{project_id}/uief/connectors", response_model=R11RecordResponse, status_code=201)
async def create_connector(
    project_id: uuid.UUID,
    request: R11ConnectorRegistrationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = connector_registration(
        connector_id=f"UIEF-CONN-{(await _record_count(session, project_id, 'connector')) + 1:04d}",
        provider=request.provider,
        supported_system=request.supported_system,
        version=request.version,
        protocols=tuple(request.protocols),
        authentication_methods=tuple(request.authentication_methods),
        operations=tuple(request.operations),
        rate_limits=request.rate_limits,
        data_classifications=tuple(request.data_classifications),
        certification_level=UiefCertificationLevel(request.certification_level),
        compatibility_refs=tuple(request.compatibility_refs),
        owner_ref=request.owner_ref,
        lifecycle_status=request.lifecycle_status,
    )
    return await _persist(session, project_id, "connector", value, actor.subject)


@router.post("/{project_id}/uief/contracts", response_model=R11RecordResponse, status_code=201)
async def create_contract(
    project_id: uuid.UUID,
    request: R11ContractRegistrationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = contract_registration(
        contract_id=f"UIEF-CTR-{(await _record_count(session, project_id, 'contract')) + 1:04d}",
        manifest_ref=request.manifest_ref,
        contract_type=UiefContractType(request.contract_type),
        contract_version=request.contract_version,
        operations=tuple(request.operations),
        schema_refs=tuple(request.schema_refs),
        error_refs=tuple(request.error_refs),
        security_requirement_refs=tuple(request.security_requirement_refs),
        slo_refs=tuple(request.slo_refs),
        compatibility_rules=tuple(request.compatibility_rules),
    )
    return await _persist(session, project_id, "contract", value, actor.subject)


@router.post("/{project_id}/uief/data-mappings", response_model=R11RecordResponse, status_code=201)
async def create_data_mapping(
    project_id: uuid.UUID,
    request: R11DataMappingRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = data_mapping(
        mapping_id=f"UIEF-MAP-{(await _record_count(session, project_id, 'mapping')) + 1:04d}",
        integration_ref=request.integration_ref,
        canonical_model_ref=request.canonical_model_ref,
        field_mappings=tuple(request.field_mappings),
        transformation_rules=tuple(request.transformation_rules),
        test_refs=tuple(request.test_refs),
        version=request.version,
    )
    return await _persist(session, project_id, "mapping", value, actor.subject)


@router.post("/{project_id}/uief/events", response_model=R11RecordResponse, status_code=201)
async def create_event_definition(
    project_id: uuid.UUID,
    request: R11EventDefinitionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = event_definition(
        event_id=f"UIEF-EVT-{(await _record_count(session, project_id, 'event')) + 1:04d}",
        event_name=request.event_name,
        producer_ref=request.producer_ref,
        consumer_refs=tuple(request.consumer_refs),
        schema_ref=request.schema_ref,
        version=request.version,
        partition_key=request.partition_key,
        delivery_semantics=request.delivery_semantics,
        retention=request.retention,
        sensitivity=request.sensitivity,
        retry_policy_ref=request.retry_policy_ref,
        dead_letter_strategy_ref=request.dead_letter_strategy_ref,
    )
    return await _persist(session, project_id, "event", value, actor.subject)


@router.post("/{project_id}/uief/retry-policies", response_model=R11RecordResponse, status_code=201)
async def create_retry_policy(
    project_id: uuid.UUID,
    request: R11RetryPolicyRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = retry_policy(
        retry_policy_id=await _next_id(session, project_id, "retry_policy", "UIEF-RETRY"),
        maximum_attempts=request.maximum_attempts,
        delay_seconds=request.delay_seconds,
        retryable_errors=tuple(request.retryable_errors),
        timeout_seconds=request.timeout_seconds,
        escalation_ref=request.escalation_ref,
        dead_letter_destination=request.dead_letter_destination,
    )
    return await _persist(session, project_id, "retry_policy", value, actor.subject)


@router.post(
    "/{project_id}/uief/security-policies",
    response_model=R11RecordResponse,
    status_code=201,
)
async def create_security_policy(
    project_id: uuid.UUID,
    request: R11SecurityPolicyRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = security_policy(
        security_policy_id=await _next_id(
            session, project_id, "security_policy", "UIEF-SEC"
        ),
        identity_strength=request.identity_strength,
        credential_ref=request.credential_ref,
        transport_encryption=request.transport_encryption,
        authorization_scope_refs=tuple(request.authorization_scope_refs),
        data_protection_rules=tuple(request.data_protection_rules),
        residency_rules=tuple(request.residency_rules),
        logging_safety_rules=tuple(request.logging_safety_rules),
    )
    return await _persist(session, project_id, "security_policy", value, actor.subject)


@router.post("/{project_id}/uief/digital-twins", response_model=R11RecordResponse, status_code=201)
async def create_digital_twin(
    project_id: uuid.UUID,
    request: R11DigitalTwinRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = digital_twin(
        twin_id=f"UIEF-TWIN-{(await _record_count(session, project_id, 'digital_twin')) + 1:04d}",
        integration_ref=request.integration_ref,
        deployed_connector_ref=request.deployed_connector_ref,
        active_version=request.active_version,
        endpoint_ref=request.endpoint_ref,
        dependency_refs=tuple(request.dependency_refs),
        health=UiefHealthStatus(request.health),
        performance_metrics=request.performance_metrics,
        data_flow_refs=tuple(request.data_flow_refs),
        contract_status=request.contract_status,
        security_status=request.security_status,
    )
    return await _persist(session, project_id, "digital_twin", value, actor.subject)


@router.post(
    "/{project_id}/uief/marketplace-assets",
    response_model=R11RecordResponse,
    status_code=201,
)
async def create_marketplace_asset(
    project_id: uuid.UUID,
    request: R11MarketplaceAssetRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = marketplace_asset(
        asset_id=await _next_id(session, project_id, "marketplace_asset", "UIEF-ASSET"),
        asset_type=request.asset_type,
        creator_ref=request.creator_ref,
        publisher_ref=request.publisher_ref,
        version=request.version,
        source_ref=request.source_ref,
        dependency_refs=tuple(request.dependency_refs),
        license_ref=request.license_ref,
        signature_ref=request.signature_ref,
        certification_level=UiefCertificationLevel(request.certification_level),
        compatibility_refs=tuple(request.compatibility_refs),
    )
    return await _persist(session, project_id, "marketplace_asset", value, actor.subject)


@router.post(
    "/{project_id}/uief/provider-abstractions",
    response_model=R11RecordResponse,
    status_code=201,
)
async def create_provider_abstraction(
    project_id: uuid.UUID,
    request: R11ProviderAbstractionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = provider_abstraction(
        provider_id=await _next_id(
            session, project_id, "provider_abstraction", "UIEF-PROV"
        ),
        capability_ref=request.capability_ref,
        logical_provider_type=request.logical_provider_type,
        primary_provider_ref=request.primary_provider_ref,
        backup_provider_refs=tuple(request.backup_provider_refs),
        regional_provider_refs=tuple(request.regional_provider_refs),
        selection_policy_ref=request.selection_policy_ref,
    )
    return await _persist(session, project_id, "provider_abstraction", value, actor.subject)


@router.post("/{project_id}/uief/ai-boundaries", response_model=R11RecordResponse, status_code=201)
async def create_ai_boundary(
    project_id: uuid.UUID,
    request: R11AiIntegrationBoundaryRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = ai_integration_boundary(
        ai_boundary_id=await _next_id(session, project_id, "ai_boundary", "UIEF-AI"),
        provider_ref=request.provider_ref,
        model_ref=request.model_ref,
        region=request.region,
        approved_data_classes=tuple(request.approved_data_classes),
        context_limit_ref=request.context_limit_ref,
        retention_policy_ref=request.retention_policy_ref,
        output_constraint_refs=tuple(request.output_constraint_refs),
        fallback_model_ref=request.fallback_model_ref,
        cost_control_ref=request.cost_control_ref,
        audit_requirement_refs=tuple(request.audit_requirement_refs),
    )
    return await _persist(session, project_id, "ai_boundary", value, actor.subject)


@router.get("/{project_id}/uief/records", response_model=list[R11RecordResponse])
async def list_records(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
    record_type: str | None = Query(default=None),
) -> list[R11RecordResponse]:
    _require_human(actor)
    await _project(session, project_id)
    statement = select(R11IntegrationRecordModel).where(
        R11IntegrationRecordModel.project_id == project_id
    )
    if record_type is not None:
        statement = statement.where(R11IntegrationRecordModel.record_type == record_type)
    rows = (
        await session.scalars(
            statement.order_by(
                R11IntegrationRecordModel.created_at.asc(),
                R11IntegrationRecordModel.record_id.asc(),
            )
        )
    ).all()
    return [R11RecordResponse.model_validate(row) for row in rows]


@router.get("/{project_id}/uief/dashboard", response_model=R11IntegrationDashboardResponse)
async def integration_dashboard(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11IntegrationDashboardResponse:
    _require_human(actor)
    await _project(session, project_id)
    rows = await _records(session, project_id)
    return R11IntegrationDashboardResponse(
        project_id=project_id,
        integration_count=sum(1 for row in rows if row.record_type == "integration"),
        connector_count=sum(1 for row in rows if row.record_type == "connector"),
        contract_count=sum(1 for row in rows if row.record_type == "contract"),
        mapping_count=sum(1 for row in rows if row.record_type == "mapping"),
        event_count=sum(1 for row in rows if row.record_type == "event"),
        retry_policy_count=sum(1 for row in rows if row.record_type == "retry_policy"),
        security_policy_count=sum(1 for row in rows if row.record_type == "security_policy"),
        digital_twin_count=sum(1 for row in rows if row.record_type == "digital_twin"),
        active_integration_count=sum(
            1
            for row in rows
            if row.record_type == "integration" and row.lifecycle_state == "activated"
        ),
        unhealthy_twin_count=sum(
            1
            for row in rows
            if row.record_type == "digital_twin"
            and row.health_status in {"degraded", "unavailable", "unknown"}
        ),
        marketplace_asset_count=sum(
            1 for row in rows if row.record_type == "marketplace_asset"
        ),
        provider_abstraction_count=sum(
            1 for row in rows if row.record_type == "provider_abstraction"
        ),
        ai_boundary_count=sum(1 for row in rows if row.record_type == "ai_boundary"),
    )


@router.get(
    "/{project_id}/uief/runtime/compatibility",
    response_model=R11RuntimeCompatibilityResponse,
)
async def runtime_compatibility(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11RuntimeCompatibilityResponse:
    _require_human(actor)
    await _project(session, project_id)
    report = analyze_compatibility(_views(await _records(session, project_id)))
    return R11RuntimeCompatibilityResponse(
        **report.model_dump(mode="json", exclude={"findings"}),
        findings=[item.model_dump(mode="json") for item in report.findings],
    )


@router.get(
    "/{project_id}/uief/runtime/generation-plan",
    response_model=R11GenerationPlanResponse,
)
async def runtime_generation_plan(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11GenerationPlanResponse:
    _require_human(actor)
    await _project(session, project_id)
    report = build_generation_plan(_views(await _records(session, project_id)))
    return R11GenerationPlanResponse(
        **report.model_dump(mode="json", exclude={"artifact_plans"}),
        artifact_plans=[item.model_dump(mode="json") for item in report.artifact_plans],
    )


@router.get("/{project_id}/uief/runtime/test-plan", response_model=R11TestPlanResponse)
async def runtime_test_plan(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11TestPlanResponse:
    _require_human(actor)
    await _project(session, project_id)
    report = build_test_plan(_views(await _records(session, project_id)))
    return R11TestPlanResponse(
        **report.model_dump(mode="json", exclude={"test_plans"}),
        test_plans=[item.model_dump(mode="json") for item in report.test_plans],
    )


@router.get(
    "/{project_id}/uief/runtime/reconciliation",
    response_model=R11ReconciliationResponse,
)
async def runtime_reconciliation(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11ReconciliationResponse:
    _require_human(actor)
    await _project(session, project_id)
    report = reconcile_integrations(_views(await _records(session, project_id)))
    return R11ReconciliationResponse(
        **report.model_dump(mode="json", exclude={"differences"}),
        differences=[item.model_dump(mode="json") for item in report.differences],
    )


@router.get(
    "/{project_id}/uief/runtime/observability",
    response_model=R11ObservabilitySnapshotResponse,
)
async def runtime_observability(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11ObservabilitySnapshotResponse:
    _require_human(actor)
    await _project(session, project_id)
    report = summarize_observability(_views(await _records(session, project_id)))
    return R11ObservabilitySnapshotResponse.model_validate(report.model_dump(mode="json"))


@router.get("/{project_id}/uief/runtime/topology", response_model=R11TopologyMapResponse)
async def runtime_topology(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11TopologyMapResponse:
    _require_human(actor)
    await _project(session, project_id)
    report = build_topology_map(_views(await _records(session, project_id)))
    return R11TopologyMapResponse(
        **report.model_dump(mode="json", exclude={"nodes", "edges"}),
        nodes=[item.model_dump(mode="json") for item in report.nodes],
        edges=[item.model_dump(mode="json") for item in report.edges],
    )


@router.get(
    "/{project_id}/uief/runtime/documentation",
    response_model=R11DocumentationBundleResponse,
)
async def runtime_documentation(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11DocumentationBundleResponse:
    _require_human(actor)
    await _project(session, project_id)
    report = generate_integration_documentation(_views(await _records(session, project_id)))
    return R11DocumentationBundleResponse(
        **report.model_dump(mode="json", exclude={"documents"}),
        documents=[item.model_dump(mode="json") for item in report.documents],
    )


@router.get(
    "/{project_id}/uief/runtime/sandbox-plan",
    response_model=R11SandboxPlanResponse,
)
async def runtime_sandbox_plan(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11SandboxPlanResponse:
    _require_human(actor)
    await _project(session, project_id)
    report = build_sandbox_plan(_views(await _records(session, project_id)))
    return R11SandboxPlanResponse(
        **report.model_dump(mode="json", exclude={"sandbox_plans"}),
        sandbox_plans=[item.model_dump(mode="json") for item in report.sandbox_plans],
    )


@router.get(
    "/{project_id}/uief/runtime/security-readiness",
    response_model=R11SecurityReadinessResponse,
)
async def runtime_security_readiness(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11SecurityReadinessResponse:
    _require_human(actor)
    await _project(session, project_id)
    report = validate_security_readiness(_views(await _records(session, project_id)))
    return R11SecurityReadinessResponse(
        **report.model_dump(mode="json", exclude={"findings"}),
        findings=[item.model_dump(mode="json") for item in report.findings],
    )


@router.get(
    "/{project_id}/uief/runtime/impact-analysis",
    response_model=R11ImpactAnalysisResponse,
)
async def runtime_impact_analysis(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
    changed_ref: str | None = Query(default=None, min_length=1, max_length=240),
) -> R11ImpactAnalysisResponse:
    _require_human(actor)
    await _project(session, project_id)
    report = analyze_integration_impact(
        _views(await _records(session, project_id)),
        changed_ref=changed_ref,
    )
    return R11ImpactAnalysisResponse(
        **report.model_dump(mode="json", exclude={"impacts"}),
        impacts=[item.model_dump(mode="json") for item in report.impacts],
    )


@router.get(
    "/{project_id}/uief/runtime/migration-plan",
    response_model=R11MigrationPlanResponse,
)
async def runtime_migration_plan(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11MigrationPlanResponse:
    _require_human(actor)
    await _project(session, project_id)
    report = build_migration_plan(_views(await _records(session, project_id)))
    return R11MigrationPlanResponse(
        **report.model_dump(mode="json", exclude={"migration_plans"}),
        migration_plans=[item.model_dump(mode="json") for item in report.migration_plans],
    )


@router.get(
    "/{project_id}/uief/runtime/ecosystem-readiness",
    response_model=R11EcosystemReadinessResponse,
)
async def runtime_ecosystem_readiness(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11EcosystemReadinessResponse:
    _require_human(actor)
    await _project(session, project_id)
    report = assess_ecosystem_readiness(_views(await _records(session, project_id)))
    return R11EcosystemReadinessResponse(
        **report.model_dump(mode="json", exclude={"findings"}),
        findings=[item.model_dump(mode="json") for item in report.findings],
    )


@router.get(
    "/{project_id}/uief/runtime/developer-surface",
    response_model=R11DeveloperSurfaceResponse,
)
async def runtime_developer_surface(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R11DeveloperSurfaceResponse:
    _require_human(actor)
    await _project(session, project_id)
    report = describe_developer_surface()
    return R11DeveloperSurfaceResponse(
        **report.model_dump(mode="json", exclude={"commands"}),
        commands=[item.model_dump(mode="json") for item in report.commands],
    )


@router.get(
    "/{project_id}/uief/runtime/deployment-preflight",
    response_model=R11DeploymentPreflightResponse,
)
async def runtime_deployment_preflight(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
    settings: SettingsDependency,
) -> R11DeploymentPreflightResponse:
    _require_human(actor)
    await _project(session, project_id)
    report = r11_deployment_preflight(settings)
    return R11DeploymentPreflightResponse(
        **report.model_dump(mode="json", exclude={"checks"}),
        checks=[item.model_dump(mode="json") for item in report.checks],
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
                select(R11IntegrationRecordModel).where(
                    R11IntegrationRecordModel.project_id == project_id,
                    R11IntegrationRecordModel.record_type == record_type,
                )
            )
        ).all()
    )


async def _next_id(
    session: object,
    project_id: uuid.UUID,
    record_type: str,
    prefix: str,
) -> str:
    return f"{prefix}-{(await _record_count(session, project_id, record_type)) + 1:04d}"


async def _records(session: object, project_id: uuid.UUID) -> list[R11IntegrationRecordModel]:
    return (
        await session.scalars(
            select(R11IntegrationRecordModel)
            .where(R11IntegrationRecordModel.project_id == project_id)
            .order_by(
                R11IntegrationRecordModel.created_at.asc(),
                R11IntegrationRecordModel.record_id.asc(),
            )
        )
    ).all()


def _views(rows: list[R11IntegrationRecordModel]) -> list[UiefRecordView]:
    return [
        UiefRecordView(
            record_type=row.record_type,
            record_id=row.record_id,
            integration_ref=row.integration_ref,
            lifecycle_state=row.lifecycle_state,
            health_status=row.health_status,
            record_document=row.record_document,
            record_hash=row.record_hash,
        )
        for row in rows
    ]


async def _persist(
    session: object,
    project_id: uuid.UUID,
    record_type: str,
    value: object,
    created_by: str,
) -> R11RecordResponse:
    document = value.model_dump(mode="json")  # type: ignore[attr-defined]
    row = R11IntegrationRecordModel(
        id=uuid.uuid4(),
        project_id=project_id,
        record_type=record_type,
        record_id=_document_record_id(document),
        integration_ref=_document_integration_ref(document),
        lifecycle_state=document.get("lifecycle_state"),
        health_status=document.get("health"),
        record_document=document,
        record_hash=_document_hash(document),
        created_by=created_by,
    )
    session.add(row)
    await session.commit()
    return R11RecordResponse.model_validate(row)


def _document_record_id(document: dict[str, Any]) -> str:
    for key in (
        "integration_id",
        "connector_id",
        "contract_id",
        "mapping_id",
        "event_id",
        "retry_policy_id",
        "security_policy_id",
        "twin_id",
        "asset_id",
        "provider_id",
        "ai_boundary_id",
    ):
        if key in document:
            return str(document[key])
    raise HTTPException(status_code=422, detail="UIEF record id missing")


def _document_hash(document: dict[str, Any]) -> str:
    for key in (
        "integration_hash",
        "connector_hash",
        "contract_hash",
        "mapping_hash",
        "event_hash",
        "retry_hash",
        "security_hash",
        "twin_hash",
        "asset_hash",
        "provider_hash",
        "ai_hash",
    ):
        if key in document:
            return str(document[key])
    raise HTTPException(status_code=422, detail="UIEF record hash missing")


def _document_integration_ref(document: dict[str, Any]) -> str | None:
    for key in ("integration_id", "integration_ref"):
        value = document.get(key)
        if isinstance(value, str):
            return value
    return None
