from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from ai_enterprise.api.dependencies import ActorDependency
from ai_enterprise.api.r15_manifest_compiler_schemas import (
    R15CompilationHistoryResponse,
    R15CompilerContractResponse,
    R15CompileRequest,
    R15CompileResponse,
)
from ai_enterprise.application.r15_manifest_compiler_runtime import (
    COMPILATION_STAGES,
    COMPILER_VERSION,
    r15_compile_manifest,
    r15_persist_compilation_history,
    r15_read_compilation_history,
)

router = APIRouter(prefix="/r15", tags=["r15-manifest-compiler"])


@router.get("/compiler-contract", response_model=R15CompilerContractResponse)
async def compiler_contract(actor: ActorDependency) -> R15CompilerContractResponse:
    _require_human_or_service(actor)
    return R15CompilerContractResponse(
        compiler_version=COMPILER_VERSION,
        stages=list(COMPILATION_STAGES),
        principles=[
            "deterministic",
            "stateless",
            "reproducible",
            "explainable",
            "incremental",
            "traceable",
            "technology-independent",
        ],
    )


@router.get("/compilation-history", response_model=R15CompilationHistoryResponse)
async def compilation_history(actor: ActorDependency) -> R15CompilationHistoryResponse:
    _require_human_or_service(actor)
    return R15CompilationHistoryResponse(
        records=list(r15_read_compilation_history(_history_path()))
    )


@router.post("/compile", response_model=R15CompileResponse)
async def compile_manifest(
    request: R15CompileRequest,
    actor: ActorDependency,
) -> R15CompileResponse:
    _require_human_or_service(actor)
    result = r15_compile_manifest(
        request.manifest,
        _schema_path(),
        _registry_root(),
        compiler_options=request.compiler_options,
    )
    history_reference = None
    if request.compiler_options.get("persist_history") is True:
        history_reference = r15_persist_compilation_history(
            result,
            _history_path(),
            actor_id=getattr(actor, "subject", "unknown"),
        )
    return R15CompileResponse(
        success_status=result.success_status,
        knowledge_graph=(
            result.knowledge_graph.model_dump(mode="json")
            if result.knowledge_graph
            else None
        ),
        dependency_graph=(
            result.dependency_graph.model_dump(mode="json")
            if result.dependency_graph
            else None
        ),
        execution_graph=(
            result.execution_graph.model_dump(mode="json")
            if result.execution_graph
            else None
        ),
        incremental_impact=result.incremental_impact.model_dump(mode="json"),
        pass_reports=[item.model_dump(mode="json") for item in result.pass_reports],
        compilation_report=result.compilation_report.model_dump(mode="json"),
        diagnostics=[item.model_dump(mode="json") for item in result.diagnostics],
        result_hash=result.result_hash,
        history_reference=history_reference,
    )


def _schema_path() -> Path:
    return _repo_root() / "schemas" / "Manifest.schema.json"


def _registry_root() -> Path:
    return _repo_root() / "registry"


def _history_path() -> Path:
    return _repo_root() / "knowledge" / "history.jsonl"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[6]


def _require_human_or_service(actor: object) -> None:
    if getattr(actor, "actor_type", None) not in {"human", "service"}:
        raise HTTPException(
            status_code=403,
            detail="R15 Manifest compiler requires operator actor",
        )
