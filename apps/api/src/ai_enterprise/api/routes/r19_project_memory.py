from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from ai_enterprise.api.dependencies import ActorDependency
from ai_enterprise.api.r19_project_memory_schemas import (
    R19AuthorizationResponse,
    R19ContextRequestBody,
    R19ContextResponse,
    R19IngestR17Request,
    R19IngestR18Request,
    R19MemoryContractResponse,
    R19MemoryExportResponse,
    R19MemoryHistoryResponse,
    R19MemoryQueryResponse,
    R19MemoryReadinessRequest,
    R19MemoryReadinessResponse,
    R19MemoryStoreResponse,
    R19QueryMemoryRequest,
    R19RelateMemoryRequest,
    R19SemanticIndexResponse,
    R19StoreMemoryRequest,
    R19UpdateMemoryRequest,
    R19ValidationResponse,
)
from ai_enterprise.application.r19_project_memory_runtime import (
    DETERMINISTIC_MEMORY_TIMESTAMP,
    MEMORY_DOMAINS,
    MEMORY_ENGINE_VERSION,
    RETENTION_CLASSES,
    r19_authorize_memory_action,
    r19_context,
    r19_export_memory,
    r19_history,
    r19_ingest_r17_execution_plan,
    r19_ingest_r18_execution_result,
    r19_memory_readiness,
    r19_production_validate_store,
    r19_query_memory,
    r19_read_store,
    r19_relate_memory,
    r19_semantic_index_report,
    r19_store_memory,
    r19_update_memory,
    r19_validate_store,
    r19_write_store,
)
from ai_enterprise.config import get_settings

router = APIRouter(prefix="/r19", tags=["r19-project-memory"])


@router.get("/memory-contract", response_model=R19MemoryContractResponse)
async def memory_contract(actor: ActorDependency) -> R19MemoryContractResponse:
    _require_memory_authority(actor, "read")
    return R19MemoryContractResponse(
        engine_version=MEMORY_ENGINE_VERSION,
        domains=list(MEMORY_DOMAINS),
        retention_classes=list(RETENTION_CLASSES),
        principles=[
            "persistent",
            "versioned",
            "immutable-by-default",
            "searchable",
            "explainable",
            "deterministic",
            "auditable",
            "technology-independent",
            "minimal-context-assembly",
        ],
    )


@router.post("/memory/store", response_model=R19MemoryStoreResponse)
async def store_memory(
    request: R19StoreMemoryRequest,
    actor: ActorDependency,
) -> R19MemoryStoreResponse:
    _require_memory_authority(
        actor,
        "write",
        include_confidential=(
            request.retention_class == "confidential" or request.visibility == "confidential"
        ),
    )
    _require_production_ready_for_record(request.retention_class, request.visibility)
    store = r19_store_memory(
        _read(),
        project_id=request.project_id,
        domain=request.domain,
        category=request.category,
        author=request.author or getattr(actor, "subject", "unknown"),
        source=request.source,
        summary=request.summary,
        related_objects=request.related_objects,
        content=request.content,
        tags=request.tags,
        confidence=request.confidence,
        retention_class=request.retention_class,
        visibility=request.visibility,
        legal_hold=request.legal_hold,
        timestamp=request.timestamp or DETERMINISTIC_MEMORY_TIMESTAMP,
    )
    _write(store)
    return R19MemoryStoreResponse(store=store.model_dump(mode="json"))


@router.post("/memory/update", response_model=R19MemoryStoreResponse)
async def update_memory(
    request: R19UpdateMemoryRequest,
    actor: ActorDependency,
) -> R19MemoryStoreResponse:
    _require_memory_authority(actor, "write")
    store = r19_update_memory(
        _read(),
        memory_id=request.memory_id,
        author=request.author or getattr(actor, "subject", "unknown"),
        summary=request.summary,
        content=request.content,
        tags=request.tags,
        timestamp=request.timestamp or DETERMINISTIC_MEMORY_TIMESTAMP,
    )
    _write(store)
    return R19MemoryStoreResponse(store=store.model_dump(mode="json"))


@router.post("/memory/relate", response_model=R19MemoryStoreResponse)
async def relate_memory(
    request: R19RelateMemoryRequest,
    actor: ActorDependency,
) -> R19MemoryStoreResponse:
    _require_memory_authority(actor, "write")
    store = r19_relate_memory(
        _read(),
        source_memory_id=request.source_memory_id,
        target_type=request.target_type,
        target_id=request.target_id,
        relationship_type=request.relationship_type,
        evidence=request.evidence,
    )
    _write(store)
    return R19MemoryStoreResponse(store=store.model_dump(mode="json"))


@router.post("/memory/query", response_model=R19MemoryQueryResponse)
async def query_memory(
    request: R19QueryMemoryRequest,
    actor: ActorDependency,
) -> R19MemoryQueryResponse:
    include_confidential = bool(request.query.get("include_confidential"))
    _require_memory_authority(actor, "read", include_confidential=include_confidential)
    result = r19_query_memory(_read(), request.query)
    return R19MemoryQueryResponse(result=result.model_dump(mode="json"))


@router.post("/memory/context", response_model=R19ContextResponse)
async def context_memory(
    request: R19ContextRequestBody,
    actor: ActorDependency,
) -> R19ContextResponse:
    include_confidential = bool(request.request.get("include_confidential"))
    _require_memory_authority(actor, "read", include_confidential=include_confidential)
    context = r19_context(_read(), request.request)
    return R19ContextResponse(context=context.model_dump(mode="json"))


@router.get("/memory/history/{memory_id}", response_model=R19MemoryHistoryResponse)
async def memory_history(
    memory_id: str,
    actor: ActorDependency,
) -> R19MemoryHistoryResponse:
    _require_memory_authority(actor, "read")
    return R19MemoryHistoryResponse(
        records=[item.model_dump(mode="json") for item in r19_history(_read(), memory_id)]
    )


@router.get("/memory/export", response_model=R19MemoryExportResponse)
async def export_memory(actor: ActorDependency) -> R19MemoryExportResponse:
    _require_memory_authority(actor, "export")
    return R19MemoryExportResponse(export=r19_export_memory(_read()).model_dump(mode="json"))


@router.get("/memory/validate", response_model=R19ValidationResponse)
async def validate_memory(actor: ActorDependency) -> R19ValidationResponse:
    _require_memory_authority(actor, "read")
    report = r19_validate_store(_read())
    return R19ValidationResponse(
        valid=report.valid,
        diagnostics=list(report.diagnostics),
        report_hash=report.report_hash,
    )


@router.post("/memory/readiness", response_model=R19MemoryReadinessResponse)
async def memory_readiness(
    request: R19MemoryReadinessRequest,
    actor: ActorDependency,
) -> R19MemoryReadinessResponse:
    _require_memory_authority(actor, "admin")
    readiness = r19_memory_readiness(request.backend_config or _backend_config())
    return R19MemoryReadinessResponse(readiness=readiness.model_dump(mode="json"))


@router.get("/memory/semantic-index", response_model=R19SemanticIndexResponse)
async def semantic_index(actor: ActorDependency) -> R19SemanticIndexResponse:
    _require_memory_authority(actor, "read")
    report = r19_semantic_index_report(_read(), _backend_config())
    return R19SemanticIndexResponse(report=report.model_dump(mode="json"))


@router.get("/memory/production-validate", response_model=R19ValidationResponse)
async def production_validate_memory(actor: ActorDependency) -> R19ValidationResponse:
    _require_memory_authority(actor, "admin")
    report = r19_production_validate_store(_read(), _backend_config())
    return R19ValidationResponse(
        valid=report.valid,
        diagnostics=list(report.diagnostics),
        report_hash=report.report_hash,
    )


@router.get("/memory/authorization/{action}", response_model=R19AuthorizationResponse)
async def authorization_check(
    action: str,
    actor: ActorDependency,
    include_confidential: bool = False,
) -> R19AuthorizationResponse:
    decision = r19_authorize_memory_action(
        action=action,
        actor_type=getattr(actor, "actor_type", ""),
        actor_role=getattr(actor, "role", ""),
        include_confidential=include_confidential,
    )
    return R19AuthorizationResponse(decision=decision.model_dump(mode="json"))


@router.post("/memory/ingest/r17", response_model=R19MemoryStoreResponse)
async def ingest_r17(
    request: R19IngestR17Request,
    actor: ActorDependency,
) -> R19MemoryStoreResponse:
    _require_memory_authority(actor, "write")
    store = r19_ingest_r17_execution_plan(
        _read(),
        request.plan,
        project_id=request.project_id,
        author=request.author or getattr(actor, "subject", "unknown"),
    )
    _write(store)
    return R19MemoryStoreResponse(store=store.model_dump(mode="json"))


@router.post("/memory/ingest/r18", response_model=R19MemoryStoreResponse)
async def ingest_r18(
    request: R19IngestR18Request,
    actor: ActorDependency,
) -> R19MemoryStoreResponse:
    _require_memory_authority(actor, "write")
    store = r19_ingest_r18_execution_result(
        _read(),
        request.result,
        project_id=request.project_id,
        author=request.author or getattr(actor, "subject", "unknown"),
    )
    _write(store)
    return R19MemoryStoreResponse(store=store.model_dump(mode="json"))


def _read() -> object:
    return r19_read_store(_store_path())


def _write(store: object) -> str:
    return r19_write_store(store, _store_path())


def _store_path() -> Path:
    return _repo_root() / "runtime" / "r19-project-memory.json"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[6]


def _backend_config() -> dict[str, object]:
    settings = get_settings()
    return {
        "memory_backend": settings.r19_memory_backend,
        "semantic_index_backend": settings.r19_memory_semantic_index_backend,
        "endpoint_reference": settings.r19_memory_endpoint_ref,
        "database_reference": settings.r19_memory_database_ref,
        "index_reference": settings.r19_memory_index_ref,
        "credentials_reference": settings.r19_memory_credentials_ref,
        "deployment_evidence_ref": settings.r19_memory_deployment_evidence_ref,
        "connectivity_evidence_ref": settings.r19_memory_connectivity_evidence_ref,
        "encryption_required": settings.r19_memory_encryption_required,
        "kms_key_ref": settings.r19_memory_kms_key_ref,
        "rbac_policy_ref": settings.r19_memory_rbac_policy_ref,
        "retention_policy_ref": settings.r19_memory_retention_policy_ref,
    }


def _require_memory_authority(
    actor: object,
    action: str,
    *,
    include_confidential: bool = False,
) -> None:
    decision = r19_authorize_memory_action(
        action=action,
        actor_type=getattr(actor, "actor_type", ""),
        actor_role=getattr(actor, "role", ""),
        include_confidential=include_confidential,
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=403,
            detail=decision.model_dump(mode="json"),
        )


def _require_production_ready_for_record(retention_class: str, visibility: str) -> None:
    settings = get_settings()
    if retention_class != "confidential" and visibility != "confidential":
        return
    readiness = r19_memory_readiness(_backend_config())
    if settings.r19_memory_encryption_required and not readiness.checks["kms"]["ok"]:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "R19-CONFIDENTIAL-MEMORY-KMS-NOT-READY",
                "readiness": readiness.model_dump(mode="json"),
            },
        )
