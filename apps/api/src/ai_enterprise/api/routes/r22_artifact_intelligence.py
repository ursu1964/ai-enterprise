from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from ai_enterprise.api.dependencies import ActorDependency
from ai_enterprise.api.r22_artifact_intelligence_schemas import (
    R22ArtifactContractResponse,
    R22ArtifactVersionResponse,
    R22CreateRegistryRequest,
    R22GraphPathRequest,
    R22ImpactAnalysisRequest,
    R22IngestR21ExecutionRequest,
    R22ListResponse,
    R22OperationalReadinessRequest,
    R22PromoteArtifactRequest,
    R22RegisterArtifactRequest,
    R22RegistrationResponse,
    R22RegistryResponse,
    R22ReportResponse,
    R22SupersedeArtifactRequest,
)
from ai_enterprise.application.r22_artifact_intelligence_runtime import (
    ARTIFACT_CLASSES,
    ARTIFACT_INTELLIGENCE_VERSION,
    FRESHNESS_STATES,
    GOVERNANCE_STATES,
    GRAPH_EDGE_TYPES,
    GRAPH_NODE_TYPES,
    INTEGRITY_STATES,
    LIFECYCLE_STATES,
    TRACE_RELATIONSHIP_TYPES,
    VALIDATION_STATES,
    r22_empty_registry,
    r22_evidence_coverage,
    r22_generate_evidence_package,
    r22_graph_neighbors,
    r22_graph_path,
    r22_ingest_r21_execution,
    r22_mark_downstream_stale,
    r22_operational_readiness,
    r22_promote_artifact_version,
    r22_read_registry,
    r22_register_artifact,
    r22_reproducibility_record,
    r22_search_artifacts,
    r22_supersede_artifact_version,
    r22_verify_integrity,
    r22_write_registry,
)

router = APIRouter(prefix="/r22", tags=["r22-artifact-intelligence"])


@router.get("/artifact-intelligence-contract", response_model=R22ArtifactContractResponse)
async def artifact_intelligence_contract(actor: ActorDependency) -> R22ArtifactContractResponse:
    _require_artifact_authority(actor, "read")
    return R22ArtifactContractResponse(
        artifact_intelligence_version=ARTIFACT_INTELLIGENCE_VERSION,
        artifact_classes=list(ARTIFACT_CLASSES),
        lifecycle_states=list(LIFECYCLE_STATES),
        validation_states=list(VALIDATION_STATES),
        freshness_states=list(FRESHNESS_STATES),
        integrity_states=list(INTEGRITY_STATES),
        governance_states=list(GOVERNANCE_STATES),
        trace_relationship_types=list(TRACE_RELATIONSHIP_TYPES),
        graph_node_types=list(GRAPH_NODE_TYPES),
        graph_edge_types=list(GRAPH_EDGE_TYPES),
        principles=[
            "immutable-artifact-versions",
            "content-addressed-integrity",
            "mandatory-provenance",
            "manifest-traceability-before-release",
            "approval-binds-to-exact-version",
            "tenant-isolated-evidence-graph",
        ],
    )


@router.post("/operational-readiness", response_model=R22ReportResponse)
async def operational_readiness(
    request: R22OperationalReadinessRequest,
    actor: ActorDependency,
) -> R22ReportResponse:
    _require_artifact_authority(actor, "read")
    report = r22_operational_readiness(request.config, production=request.production)
    return R22ReportResponse(report=report.model_dump(mode="json"))


@router.post("/projects/{project_id}/registry", response_model=R22RegistryResponse)
async def create_registry(
    project_id: str,
    request: R22CreateRegistryRequest,
    actor: ActorDependency,
) -> R22RegistryResponse:
    _require_artifact_authority(actor, "write")
    registry = r22_empty_registry(project_id, request.tenant_id)
    if request.persist:
        r22_write_registry(registry, _registry_path(project_id, request.tenant_id))
    return R22RegistryResponse(registry=registry.model_dump(mode="json"))


@router.get("/projects/{project_id}/registry", response_model=R22RegistryResponse)
async def get_registry(
    project_id: str,
    actor: ActorDependency,
    tenant_id: str = "default",
) -> R22RegistryResponse:
    _require_artifact_authority(actor, "read")
    return R22RegistryResponse(
        registry=_read_or_empty(project_id, tenant_id).model_dump(mode="json")
    )


@router.post("/projects/{project_id}/artifacts", response_model=R22RegistrationResponse)
async def register_artifact(
    project_id: str,
    request: R22RegisterArtifactRequest,
    actor: ActorDependency,
) -> R22RegistrationResponse:
    _require_artifact_authority(actor, "write")
    result = r22_register_artifact(
        _read_or_empty(project_id, request.tenant_id),
        artifact_type=request.artifact_type,
        artifact_class=request.artifact_class,
        title=request.title,
        content=request.content,
        media_type=request.media_type,
        schema_id=request.schema_id,
        schema_version=request.schema_version,
        created_by=actor.subject,
        provenance=request.provenance,
        manifest_traces=request.manifest_traces,
        work_package_ids=request.work_package_ids,
        dependencies=request.dependencies,
        validations=request.validations,
        approvals=request.approvals,
        declared_checksum=request.declared_checksum,
        classification=request.classification,
        retention_policy_id=request.retention_policy_id,
    )
    if request.persist:
        r22_write_registry(result.registry, _registry_path(project_id, request.tenant_id))
    status = result.registry.model_dump(mode="json")
    return R22RegistrationResponse(
        accepted=result.accepted,
        artifact_id=result.artifact_id,
        artifact_version_id=result.artifact_version_id,
        diagnostics=[item.model_dump(mode="json") for item in result.diagnostics],
        registry=status,
    )


@router.get("/artifact-versions/{artifact_version_id}", response_model=R22ArtifactVersionResponse)
async def get_artifact_version(
    artifact_version_id: str,
    actor: ActorDependency,
    project_id: str,
    tenant_id: str = "default",
) -> R22ArtifactVersionResponse:
    _require_artifact_authority(actor, "read")
    registry = _read_or_empty(project_id, tenant_id)
    version = next(
        (item for item in registry.versions if item.artifact_version_id == artifact_version_id),
        None,
    )
    if version is None:
        raise HTTPException(status_code=404, detail="Artifact version is not present")
    return R22ArtifactVersionResponse(artifact_version=version.model_dump(mode="json"))


@router.post("/artifact-versions/{artifact_version_id}/promote", response_model=R22ReportResponse)
async def promote_artifact_version(
    artifact_version_id: str,
    request: R22PromoteArtifactRequest,
    actor: ActorDependency,
    project_id: str,
) -> R22ReportResponse:
    _require_artifact_authority(actor, "write")
    report = r22_promote_artifact_version(
        _read_or_empty(project_id, request.tenant_id),
        artifact_version_id,
        request.target_lifecycle,
        actor_id=actor.subject,
    )
    if request.persist:
        r22_write_registry(report.registry, _registry_path(project_id, request.tenant_id))
    return R22ReportResponse(report=report.model_dump(mode="json"))


@router.post(
    "/artifact-versions/{artifact_version_id}/supersede", response_model=R22RegistryResponse
)
async def supersede_artifact_version(
    artifact_version_id: str,
    request: R22SupersedeArtifactRequest,
    actor: ActorDependency,
    project_id: str,
) -> R22RegistryResponse:
    _require_artifact_authority(actor, "write")
    registry = r22_supersede_artifact_version(
        _read_or_empty(project_id, request.tenant_id),
        artifact_version_id,
        request.replacement_version_id,
        reason=request.reason,
        actor_id=actor.subject,
    )
    if request.persist:
        r22_write_registry(registry, _registry_path(project_id, request.tenant_id))
    return R22RegistryResponse(registry=registry.model_dump(mode="json"))


@router.post("/projects/{project_id}/impact-analysis", response_model=R22ReportResponse)
async def impact_analysis(
    project_id: str,
    request: R22ImpactAnalysisRequest,
    actor: ActorDependency,
) -> R22ReportResponse:
    _require_artifact_authority(actor, "write")
    registry, analysis = r22_mark_downstream_stale(
        _read_or_empty(project_id, request.tenant_id),
        request.changed_object_id,
        actor_id=actor.subject,
    )
    if request.persist:
        r22_write_registry(registry, _registry_path(project_id, request.tenant_id))
    return R22ReportResponse(report=analysis.model_dump(mode="json"))


@router.get("/projects/{project_id}/evidence-coverage", response_model=R22ReportResponse)
async def evidence_coverage(
    project_id: str,
    actor: ActorDependency,
    tenant_id: str = "default",
) -> R22ReportResponse:
    _require_artifact_authority(actor, "read")
    return R22ReportResponse(
        report=r22_evidence_coverage(_read_or_empty(project_id, tenant_id)).model_dump(mode="json")
    )


@router.post("/projects/{project_id}/evidence-package", response_model=R22ReportResponse)
async def evidence_package(
    project_id: str,
    actor: ActorDependency,
    tenant_id: str = "default",
    execution_id: str | None = None,
) -> R22ReportResponse:
    _require_artifact_authority(actor, "read")
    package = r22_generate_evidence_package(
        _read_or_empty(project_id, tenant_id), execution_id=execution_id
    )
    return R22ReportResponse(report=package.model_dump(mode="json"))


@router.get("/artifact-versions/{artifact_version_id}/integrity", response_model=R22ReportResponse)
async def verify_integrity(
    artifact_version_id: str,
    actor: ActorDependency,
    project_id: str,
    tenant_id: str = "default",
) -> R22ReportResponse:
    _require_artifact_authority(actor, "read")
    report = r22_verify_integrity(_read_or_empty(project_id, tenant_id), artifact_version_id)
    return R22ReportResponse(report=report.model_dump(mode="json"))


@router.get(
    "/artifact-versions/{artifact_version_id}/reproducibility", response_model=R22ReportResponse
)
async def reproducibility(
    artifact_version_id: str,
    actor: ActorDependency,
    project_id: str,
    tenant_id: str = "default",
) -> R22ReportResponse:
    _require_artifact_authority(actor, "read")
    report = r22_reproducibility_record(_read_or_empty(project_id, tenant_id), artifact_version_id)
    return R22ReportResponse(report=report.model_dump(mode="json"))


@router.get("/graph/nodes/{node_id}/downstream", response_model=R22ReportResponse)
async def graph_downstream(
    node_id: str,
    actor: ActorDependency,
    project_id: str,
    tenant_id: str = "default",
) -> R22ReportResponse:
    _require_artifact_authority(actor, "read")
    return R22ReportResponse(
        report=r22_graph_neighbors(
            _read_or_empty(project_id, tenant_id),
            node_id,
            direction="downstream",
            actor_tenant_id=tenant_id,
        )
    )


@router.get("/graph/nodes/{node_id}/upstream", response_model=R22ReportResponse)
async def graph_upstream(
    node_id: str,
    actor: ActorDependency,
    project_id: str,
    tenant_id: str = "default",
) -> R22ReportResponse:
    _require_artifact_authority(actor, "read")
    return R22ReportResponse(
        report=r22_graph_neighbors(
            _read_or_empty(project_id, tenant_id),
            node_id,
            direction="upstream",
            actor_tenant_id=tenant_id,
        )
    )


@router.post("/graph/path", response_model=R22ReportResponse)
async def graph_path(
    request: R22GraphPathRequest,
    actor: ActorDependency,
    project_id: str,
) -> R22ReportResponse:
    _require_artifact_authority(actor, "read")
    return R22ReportResponse(
        report=r22_graph_path(
            _read_or_empty(project_id, request.tenant_id),
            request.source_node_id,
            request.target_node_id,
            actor_tenant_id=request.tenant_id,
        )
    )


@router.get("/projects/{project_id}/artifacts/search", response_model=R22ListResponse)
async def search_artifacts(
    project_id: str,
    actor: ActorDependency,
    tenant_id: str = "default",
    artifact_class: str | None = None,
    lifecycle: str | None = None,
    classification: str | None = None,
) -> R22ListResponse:
    _require_artifact_authority(actor, "read")
    records = r22_search_artifacts(
        _read_or_empty(project_id, tenant_id),
        artifact_class=artifact_class,
        lifecycle=lifecycle,
        classification=classification,
    )
    return R22ListResponse(records=[item.model_dump(mode="json") for item in records])


@router.post("/projects/{project_id}/ingest-r21-execution", response_model=R22RegistryResponse)
async def ingest_r21_execution(
    project_id: str,
    request: R22IngestR21ExecutionRequest,
    actor: ActorDependency,
) -> R22RegistryResponse:
    _require_artifact_authority(actor, "write")
    registry = r22_ingest_r21_execution(request.execution, tenant_id=request.tenant_id)
    if registry.project_id != project_id:
        raise HTTPException(
            status_code=400, detail="R21 execution project does not match route project"
        )
    if request.persist:
        r22_write_registry(registry, _registry_path(project_id, request.tenant_id))
    return R22RegistryResponse(registry=registry.model_dump(mode="json"))


def _read_or_empty(project_id: str, tenant_id: str):
    return r22_read_registry(_registry_path(project_id, tenant_id)) or r22_empty_registry(
        project_id, tenant_id
    )


def _registry_path(project_id: str, tenant_id: str) -> Path:
    return _repo_root() / "runtime" / "r22-artifact-intelligence" / tenant_id / f"{project_id}.json"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[6]


def _require_artifact_authority(actor: ActorDependency, action: str) -> None:
    role = getattr(actor, "role", "")
    if role in {"admin", "owner", "architect", "reviewer", "operator", "platform-admin"}:
        return
    if action == "read" and role in {"developer", "viewer", "analyst"}:
        return
    raise HTTPException(status_code=403, detail="Actor lacks R22 artifact-intelligence authority")
