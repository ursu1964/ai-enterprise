from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from ai_enterprise.api.dependencies import ActorDependency, SettingsDependency
from ai_enterprise.api.r16_knowledge_graph_schemas import (
    R16GenericResponse,
    R16GraphAccessRequest,
    R16GraphBackendPublishRequest,
    R16GraphDiffRequest,
    R16GraphExportRequest,
    R16GraphFindRequest,
    R16GraphImpactRequest,
    R16GraphLoadRequest,
    R16GraphQueryRequest,
    R16GraphResponse,
    R16GraphTraverseRequest,
    R16GraphValidationRequest,
    R16GraphValidationResponse,
)
from ai_enterprise.application.r16_knowledge_graph_runtime import (
    R16KnowledgeGraphModel,
    r16_apply_access_policy,
    r16_diff_graphs,
    r16_export_graph,
    r16_find_graph,
    r16_graph_backend_readiness,
    r16_load_graph,
    r16_ontology_contract,
    r16_propagate_impact,
    r16_publish_graph_to_backend,
    r16_query_graph,
    r16_traverse_graph,
    r16_validate_graph,
)

router = APIRouter(prefix="/r16", tags=["r16-knowledge-graph"])


@router.get("/ontology-contract", response_model=R16GenericResponse)
async def ontology_contract(actor: ActorDependency) -> R16GenericResponse:
    _require_human_or_service(actor)
    return R16GenericResponse(
        result=r16_ontology_contract(_registry_root()).model_dump(mode="json")
    )


@router.get("/graph/backend-readiness", response_model=R16GenericResponse)
async def graph_backend_readiness(
    actor: ActorDependency,
    settings: SettingsDependency,
) -> R16GenericResponse:
    _require_human_or_service(actor)
    readiness = r16_graph_backend_readiness(settings, repo_root=_repo_root())
    return R16GenericResponse(result=readiness.model_dump(mode="json"))


@router.post("/graph/load", response_model=R16GraphResponse)
async def load_graph(
    request: R16GraphLoadRequest,
    actor: ActorDependency,
) -> R16GraphResponse:
    _require_human_or_service(actor)
    graph = r16_load_graph(
        request.knowledge_graph,
        compilation_report=request.compilation_report,
        registry_root=_registry_root(),
    )
    return R16GraphResponse(graph=graph.model_dump(mode="json"))


@router.post("/graph/validate", response_model=R16GraphValidationResponse)
async def validate_graph(
    request: R16GraphValidationRequest,
    actor: ActorDependency,
) -> R16GraphValidationResponse:
    _require_human_or_service(actor)
    report = r16_validate_graph(R16KnowledgeGraphModel.model_validate(request.graph))
    return R16GraphValidationResponse(
        valid=report.valid,
        diagnostics=[item.model_dump(mode="json") for item in report.diagnostics],
        report_hash=report.report_hash,
    )


@router.post("/graph/query", response_model=R16GenericResponse)
async def query_graph(
    request: R16GraphQueryRequest,
    actor: ActorDependency,
) -> R16GenericResponse:
    _require_human_or_service(actor)
    result = r16_query_graph(R16KnowledgeGraphModel.model_validate(request.graph), request.query)
    return R16GenericResponse(result=result.model_dump(mode="json"))


@router.post("/graph/find", response_model=R16GenericResponse)
async def find_graph(
    request: R16GraphFindRequest,
    actor: ActorDependency,
) -> R16GenericResponse:
    _require_human_or_service(actor)
    result = r16_find_graph(
        R16KnowledgeGraphModel.model_validate(request.graph),
        node_id=request.node_id,
        node_type=request.node_type,
    )
    return R16GenericResponse(result=result.model_dump(mode="json"))


@router.post("/graph/traverse", response_model=R16GenericResponse)
async def traverse_graph(
    request: R16GraphTraverseRequest,
    actor: ActorDependency,
) -> R16GenericResponse:
    _require_human_or_service(actor)
    result = r16_traverse_graph(
        R16KnowledgeGraphModel.model_validate(request.graph),
        start_node_id=request.start_node_id,
        max_depth=request.max_depth,
    )
    return R16GenericResponse(result=result.model_dump(mode="json"))


@router.post("/graph/impact", response_model=R16GenericResponse)
async def graph_impact(
    request: R16GraphImpactRequest,
    actor: ActorDependency,
) -> R16GenericResponse:
    _require_human_or_service(actor)
    result = r16_propagate_impact(
        R16KnowledgeGraphModel.model_validate(request.graph),
        start_node_id=request.start_node_id,
        max_depth=request.max_depth,
    )
    return R16GenericResponse(result=result.model_dump(mode="json"))


@router.post("/graph/access-filter", response_model=R16GraphResponse)
async def access_filter_graph(
    request: R16GraphAccessRequest,
    actor: ActorDependency,
) -> R16GraphResponse:
    _require_human_or_service(actor)
    result = r16_apply_access_policy(
        R16KnowledgeGraphModel.model_validate(request.graph),
        request.policy,
    )
    return R16GraphResponse(graph=result.model_dump(mode="json"))


@router.post("/graph/diff", response_model=R16GenericResponse)
async def diff_graph(
    request: R16GraphDiffRequest,
    actor: ActorDependency,
) -> R16GenericResponse:
    _require_human_or_service(actor)
    result = r16_diff_graphs(
        R16KnowledgeGraphModel.model_validate(request.previous_graph),
        R16KnowledgeGraphModel.model_validate(request.current_graph),
    )
    return R16GenericResponse(result=result.model_dump(mode="json"))


@router.post("/graph/export", response_model=R16GenericResponse)
async def export_graph(
    request: R16GraphExportRequest,
    actor: ActorDependency,
) -> R16GenericResponse:
    _require_human_or_service(actor)
    result = r16_export_graph(
        R16KnowledgeGraphModel.model_validate(request.graph),
        export_format=request.export_format,
    )
    return R16GenericResponse(result=result.model_dump(mode="json"))


@router.post("/graph/publish", response_model=R16GenericResponse)
async def publish_graph(
    request: R16GraphBackendPublishRequest,
    actor: ActorDependency,
    settings: SettingsDependency,
) -> R16GenericResponse:
    _require_human_or_service(actor)
    result = r16_publish_graph_to_backend(
        R16KnowledgeGraphModel.model_validate(request.graph),
        settings,
        dry_run=request.dry_run,
        repo_root=_repo_root(),
    )
    return R16GenericResponse(result=result.model_dump(mode="json"))


def _require_human_or_service(actor: object) -> None:
    if getattr(actor, "actor_type", None) not in {"human", "service"}:
        raise HTTPException(
            status_code=403,
            detail="R16 Knowledge Graph requires operator actor",
        )


def _registry_root() -> Path:
    return _repo_root() / "registry"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[6]
