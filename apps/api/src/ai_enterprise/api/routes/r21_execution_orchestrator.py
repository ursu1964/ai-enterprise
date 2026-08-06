from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from ai_enterprise.api.dependencies import ActorDependency, SessionDependency
from ai_enterprise.api.r21_execution_orchestrator_schemas import (
    R21ApprovalDecisionRequest,
    R21CompilationResponse,
    R21CompileProjectRequest,
    R21CreatePlanRequest,
    R21ExecutionMutationRequest,
    R21ExecutionResponse,
    R21ExecutionStatusResponse,
    R21ImpactAnalysisRequest,
    R21ImpactAnalysisResponse,
    R21ListResponse,
    R21OrchestratorContractResponse,
    R21PlanResponse,
    R21RecoverRequest,
    R21RecoverResponse,
    R21StartExecutionRequest,
)
from ai_enterprise.application.r21_execution_orchestrator_runtime import (
    ARTIFACT_PROMOTION_LEVELS,
    EXECUTION_ORCHESTRATOR_VERSION,
    PROJECT_STATES,
    WORK_PACKAGE_STATES,
    WORKER_TYPES,
    r21_analyze_manifest_change,
    r21_apply_approval,
    r21_cancel_execution,
    r21_cancel_work_package,
    r21_compile_project,
    r21_create_execution_plan,
    r21_pause_execution,
    r21_read_execution,
    r21_read_execution_plan,
    r21_recover_execution,
    r21_remediate_work_package,
    r21_resume_execution,
    r21_retry_work_package,
    r21_start_execution,
    r21_write_compilation,
    r21_write_execution,
    r21_write_execution_plan,
)
from ai_enterprise.application.r21_persistence_service import R21PersistenceService
from ai_enterprise.config import get_settings

router = APIRouter(prefix="/r21", tags=["r21-execution-orchestrator"])


@router.get("/orchestrator-contract", response_model=R21OrchestratorContractResponse)
async def orchestrator_contract(actor: ActorDependency) -> R21OrchestratorContractResponse:
    _require_orchestrator_authority(actor, "read")
    return R21OrchestratorContractResponse(
        orchestrator_version=EXECUTION_ORCHESTRATOR_VERSION,
        project_states=list(PROJECT_STATES),
        work_package_states=list(WORK_PACKAGE_STATES),
        artifact_promotion_levels=list(ARTIFACT_PROMOTION_LEVELS),
        worker_types=list(WORKER_TYPES),
        principles=[
            "manifest-driven-execution",
            "bounded-autonomy",
            "evidence-before-completion",
            "deterministic-control",
            "mandatory-human-authority",
            "recoverable-checkpoints",
            "idempotent-work-package-execution",
        ],
    )


@router.post("/projects/{project_id}/compile", response_model=R21CompilationResponse)
async def compile_project(
    project_id: str,
    request: R21CompileProjectRequest,
    actor: ActorDependency,
    session: SessionDependency,
) -> R21CompilationResponse:
    _require_orchestrator_authority(actor, "write")
    _assert_project(project_id, request.manifest)
    compilation = r21_compile_project(request.manifest, _schema_path(), _registry_root())
    if request.persist:
        _write_compilation(compilation)
        await _record_compilation(session, compilation, actor)
    return R21CompilationResponse(compilation=compilation.model_dump(mode="json"))


@router.post("/projects/{project_id}/execution-plans", response_model=R21PlanResponse)
async def create_execution_plan(
    project_id: str,
    request: R21CreatePlanRequest,
    actor: ActorDependency,
    session: SessionDependency,
) -> R21PlanResponse:
    _require_orchestrator_authority(actor, "write")
    _assert_project(project_id, request.manifest)
    plan = r21_create_execution_plan(request.manifest, request.compilation)
    if request.persist:
        _write_plan(plan)
        await _record_plan(session, plan, actor)
    return R21PlanResponse(plan=plan.model_dump(mode="json"))


@router.get("/projects/{project_id}/execution-plans/{plan_id}", response_model=R21PlanResponse)
async def get_execution_plan(
    project_id: str,
    plan_id: str,
    actor: ActorDependency,
) -> R21PlanResponse:
    _require_orchestrator_authority(actor, "read")
    plan = r21_read_execution_plan(_plan_path(project_id, plan_id))
    if plan is None:
        raise HTTPException(status_code=404, detail="Execution plan is not present")
    return R21PlanResponse(plan=plan.model_dump(mode="json"))


@router.post("/projects/{project_id}/executions", response_model=R21ExecutionResponse)
async def start_execution(
    project_id: str,
    request: R21StartExecutionRequest,
    actor: ActorDependency,
    session: SessionDependency,
) -> R21ExecutionResponse:
    _require_orchestrator_authority(actor, "write")
    if request.plan.get("project_id") != project_id:
        raise HTTPException(status_code=409, detail="Path project does not match execution plan")
    execution = r21_start_execution(request.plan, options=request.options)
    if request.persist:
        _write_plan(request.plan)
        _write(execution)
        await _record_execution(session, execution, actor, "started")
    return R21ExecutionResponse(execution=execution.model_dump(mode="json"))


@router.get("/projects/{project_id}/executions/{execution_id}", response_model=R21ExecutionResponse)
async def get_execution(
    project_id: str,
    execution_id: str,
    actor: ActorDependency,
) -> R21ExecutionResponse:
    _require_orchestrator_authority(actor, "read")
    execution = _read_required()
    if execution.project_id != project_id or execution.execution_id != execution_id:
        raise HTTPException(status_code=404, detail="Execution is not present")
    return R21ExecutionResponse(execution=execution.model_dump(mode="json"))


@router.post(
    "/projects/{project_id}/executions/{execution_id}/pause", response_model=R21ExecutionResponse
)
async def pause_execution(
    project_id: str,
    execution_id: str,
    request: R21ExecutionMutationRequest,
    actor: ActorDependency,
    session: SessionDependency,
) -> R21ExecutionResponse:
    _require_orchestrator_authority(actor, "write")
    execution = request.execution or _read_required().model_dump(mode="json")
    if execution.get("project_id") != project_id or execution.get("execution_id") != execution_id:
        raise HTTPException(status_code=409, detail="Path execution does not match payload")
    paused = r21_pause_execution(execution, "api-request")
    if request.persist:
        _write(paused)
        await _record_execution(session, paused, actor, "paused")
    return R21ExecutionResponse(execution=paused.model_dump(mode="json"))


@router.post(
    "/projects/{project_id}/executions/{execution_id}/resume", response_model=R21ExecutionResponse
)
async def resume_execution(
    project_id: str,
    execution_id: str,
    request: R21ExecutionMutationRequest,
    actor: ActorDependency,
    session: SessionDependency,
) -> R21ExecutionResponse:
    _require_orchestrator_authority(actor, "write")
    execution = request.execution or _read_required().model_dump(mode="json")
    if execution.get("project_id") != project_id or execution.get("execution_id") != execution_id:
        raise HTTPException(status_code=409, detail="Path execution does not match payload")
    plan = request.plan or _read_plan_for_execution(execution)
    resumed = r21_resume_execution(plan, execution)
    if request.persist:
        _write(resumed)
        await _record_execution(session, resumed, actor, "resumed")
    return R21ExecutionResponse(execution=resumed.model_dump(mode="json"))


@router.post(
    "/projects/{project_id}/executions/{execution_id}/cancel", response_model=R21ExecutionResponse
)
async def cancel_execution(
    project_id: str,
    execution_id: str,
    request: R21ExecutionMutationRequest,
    actor: ActorDependency,
    session: SessionDependency,
) -> R21ExecutionResponse:
    _require_orchestrator_authority(actor, "write")
    execution = request.execution or _read_required().model_dump(mode="json")
    if execution.get("project_id") != project_id or execution.get("execution_id") != execution_id:
        raise HTTPException(status_code=409, detail="Path execution does not match payload")
    cancelled = r21_cancel_execution(
        execution,
        reason="api-request",
        actor_id=getattr(actor, "subject", "api"),
    )
    if request.persist:
        _write(cancelled)
        await _record_execution(session, cancelled, actor, "cancelled")
    return R21ExecutionResponse(execution=cancelled.model_dump(mode="json"))


@router.get("/executions/status", response_model=R21ExecutionStatusResponse)
async def execution_status(actor: ActorDependency) -> R21ExecutionStatusResponse:
    _require_orchestrator_authority(actor, "read")
    execution = r21_read_execution(_execution_path())
    return R21ExecutionStatusResponse(
        present=execution is not None,
        execution=execution.model_dump(mode="json") if execution else None,
    )


@router.get("/executions/{execution_id}/work-packages", response_model=R21ListResponse)
async def list_work_packages(execution_id: str, actor: ActorDependency) -> R21ListResponse:
    _require_orchestrator_authority(actor, "read")
    execution = _read_required()
    if execution.execution_id != execution_id:
        raise HTTPException(status_code=404, detail="Execution is not present")
    return R21ListResponse(
        items=[item.model_dump(mode="json") for item in execution.work_package_states]
    )


@router.get("/work-packages/{work_package_id}", response_model=R21ListResponse)
async def get_work_package(work_package_id: str, actor: ActorDependency) -> R21ListResponse:
    _require_orchestrator_authority(actor, "read")
    execution = _read_required()
    items = [
        item.model_dump(mode="json")
        for item in execution.work_package_states
        if item.work_package_id == work_package_id
    ]
    if not items:
        raise HTTPException(status_code=404, detail="Work package is not present")
    return R21ListResponse(items=items)


@router.post("/work-packages/{work_package_id}/retry", response_model=R21ExecutionResponse)
async def retry_work_package(
    work_package_id: str,
    request: R21ExecutionMutationRequest,
    actor: ActorDependency,
    session: SessionDependency,
) -> R21ExecutionResponse:
    _require_orchestrator_authority(actor, "write")
    execution = request.execution or _read_required().model_dump(mode="json")
    updated = r21_retry_work_package(
        execution,
        work_package_id=work_package_id,
        actor_id=getattr(actor, "subject", "api"),
    )
    if request.persist:
        _write(updated)
        await _record_execution(session, updated, actor, "work_package_retry")
    return R21ExecutionResponse(execution=updated.model_dump(mode="json"))


@router.post("/work-packages/{work_package_id}/cancel", response_model=R21ExecutionResponse)
async def cancel_work_package(
    work_package_id: str,
    request: R21ExecutionMutationRequest,
    actor: ActorDependency,
    session: SessionDependency,
) -> R21ExecutionResponse:
    _require_orchestrator_authority(actor, "write")
    execution = request.execution or _read_required().model_dump(mode="json")
    updated = r21_cancel_work_package(
        execution,
        work_package_id=work_package_id,
        actor_id=getattr(actor, "subject", "api"),
    )
    if request.persist:
        _write(updated)
        await _record_execution(session, updated, actor, "work_package_cancelled")
    return R21ExecutionResponse(execution=updated.model_dump(mode="json"))


@router.post("/work-packages/{work_package_id}/remediate", response_model=R21ExecutionResponse)
async def remediate_work_package(
    work_package_id: str,
    request: R21ExecutionMutationRequest,
    actor: ActorDependency,
    session: SessionDependency,
) -> R21ExecutionResponse:
    _require_orchestrator_authority(actor, "write")
    execution = request.execution or _read_required().model_dump(mode="json")
    updated = r21_remediate_work_package(
        execution,
        work_package_id=work_package_id,
        actor_id=getattr(actor, "subject", "api"),
    )
    if request.persist:
        _write(updated)
        await _record_execution(session, updated, actor, "work_package_remediated")
    return R21ExecutionResponse(execution=updated.model_dump(mode="json"))


@router.get("/projects/{project_id}/approval-gates", response_model=R21ListResponse)
async def list_approval_gates(project_id: str, actor: ActorDependency) -> R21ListResponse:
    _require_orchestrator_authority(actor, "read")
    execution = _read_required()
    if execution.project_id != project_id:
        raise HTTPException(status_code=404, detail="Project is not present")
    return R21ListResponse(
        items=[item.model_dump(mode="json") for item in execution.approval_gates]
    )


@router.get("/approval-gates/{gate_id}", response_model=R21ListResponse)
async def get_approval_gate(gate_id: str, actor: ActorDependency) -> R21ListResponse:
    _require_orchestrator_authority(actor, "read")
    execution = _read_required()
    items = [
        item.model_dump(mode="json") for item in execution.approval_gates if item.gate_id == gate_id
    ]
    if not items:
        raise HTTPException(status_code=404, detail="Approval gate is not present")
    return R21ListResponse(items=items)


@router.post("/approval-gates/{gate_id}/decisions", response_model=R21ExecutionResponse)
async def decide_approval_gate(
    gate_id: str,
    request: R21ApprovalDecisionRequest,
    actor: ActorDependency,
    session: SessionDependency,
) -> R21ExecutionResponse:
    _require_orchestrator_authority(actor, "write")
    execution = request.execution or _read_required().model_dump(mode="json")
    decided = r21_apply_approval(
        execution,
        gate_id=gate_id,
        decision=request.decision,
        actor_role=request.actor_role,
        actor_id=request.actor_id,
    )
    if request.persist:
        _write(decided)
        await _record_execution(session, decided, actor, "approval_decided")
    return R21ExecutionResponse(execution=decided.model_dump(mode="json"))


@router.get("/executions/{execution_id}/evidence", response_model=R21ListResponse)
async def execution_evidence(execution_id: str, actor: ActorDependency) -> R21ListResponse:
    _require_orchestrator_authority(actor, "read")
    execution = _read_required()
    if execution.execution_id != execution_id:
        raise HTTPException(status_code=404, detail="Execution is not present")
    return R21ListResponse(items=[item.model_dump(mode="json") for item in execution.evidence])


@router.get("/work-packages/{work_package_id}/evidence", response_model=R21ListResponse)
async def work_package_evidence(work_package_id: str, actor: ActorDependency) -> R21ListResponse:
    _require_orchestrator_authority(actor, "read")
    execution = _read_required()
    return R21ListResponse(
        items=[
            item.model_dump(mode="json")
            for item in execution.evidence
            if item.entity_id == work_package_id
        ]
    )


@router.get("/artifacts/{artifact_id}/provenance", response_model=R21ListResponse)
async def artifact_provenance(artifact_id: str, actor: ActorDependency) -> R21ListResponse:
    _require_orchestrator_authority(actor, "read")
    execution = _read_required()
    return R21ListResponse(
        items=[
            {
                "artifact_id": item.artifact_id,
                "provenance_hash": item.provenance_hash,
                "manifest_trace_hash": item.manifest_trace_hash,
            }
            for item in execution.artifacts
            if item.artifact_id == artifact_id
        ]
    )


@router.get("/projects/{project_id}/traceability", response_model=R21ListResponse)
async def project_traceability(project_id: str, actor: ActorDependency) -> R21ListResponse:
    _require_orchestrator_authority(actor, "read")
    execution = _read_required()
    if execution.project_id != project_id:
        raise HTTPException(status_code=404, detail="Project is not present")
    return R21ListResponse(
        items=[
            {
                "artifact_id": item.artifact_id,
                "work_package_id": item.work_package_id,
                "manifest_trace_hash": item.manifest_trace_hash,
            }
            for item in execution.artifacts
        ]
    )


@router.post("/executions/recover", response_model=R21RecoverResponse)
async def recover_execution(
    request: R21RecoverRequest,
    actor: ActorDependency,
    session: SessionDependency,
) -> R21RecoverResponse:
    _require_orchestrator_authority(actor, "read")
    recovery = r21_recover_execution(request.checkpoint)
    await _record_recovery(session, recovery, actor)
    return R21RecoverResponse(recovery=recovery)


@router.post("/projects/{project_id}/impact-analysis", response_model=R21ImpactAnalysisResponse)
async def impact_analysis(
    project_id: str,
    request: R21ImpactAnalysisRequest,
    actor: ActorDependency,
) -> R21ImpactAnalysisResponse:
    _require_orchestrator_authority(actor, "read")
    if request.plan.get("project_id") != project_id:
        raise HTTPException(status_code=409, detail="Path project does not match plan")
    analysis = r21_analyze_manifest_change(
        request.previous_manifest,
        request.current_manifest,
        request.plan,
        request.execution,
    )
    return R21ImpactAnalysisResponse(analysis=analysis.model_dump(mode="json"))


def _read_required() -> object:
    execution = r21_read_execution(_execution_path())
    if execution is None:
        raise HTTPException(status_code=404, detail="R21 execution is not present")
    return execution


def _write(execution: object) -> str:
    return r21_write_execution(execution, _execution_path())


def _write_compilation(compilation: object) -> str:
    project_id = getattr(compilation, "project_id", None)
    if project_id is None and isinstance(compilation, dict):
        project_id = compilation.get("project_id")
    if not project_id:
        raise HTTPException(status_code=409, detail="Compilation project_id is required")
    return r21_write_compilation(compilation, _compilation_path(str(project_id)))


def _write_plan(plan: object) -> str:
    project_id = getattr(plan, "project_id", None)
    plan_id = getattr(plan, "execution_plan_id", None)
    if isinstance(plan, dict):
        project_id = plan.get("project_id", project_id)
        plan_id = plan.get("execution_plan_id", plan_id)
    if not project_id or not plan_id:
        raise HTTPException(
            status_code=409, detail="Plan project_id and execution_plan_id are required"
        )
    return r21_write_execution_plan(plan, _plan_path(str(project_id), str(plan_id)))


def _read_plan_for_execution(execution: dict[str, object]) -> dict[str, object]:
    project_id = execution.get("project_id")
    plan_id = execution.get("execution_plan_id")
    if not project_id or not plan_id:
        raise HTTPException(status_code=409, detail="Execution does not reference a plan")
    plan = r21_read_execution_plan(_plan_path(str(project_id), str(plan_id)))
    if plan is None:
        raise HTTPException(status_code=404, detail="Persisted execution plan is not present")
    return plan.model_dump(mode="json")


async def _record_compilation(session: object, compilation: object, actor: object) -> None:
    await _persist_or_raise(
        R21PersistenceService(session).record_compilation(  # type: ignore[arg-type]
            compilation,  # type: ignore[arg-type]
            actor_type=getattr(actor, "actor_type", "unknown"),
            actor_id=getattr(actor, "subject", "unknown"),
        ),
        session,
    )


async def _record_plan(session: object, plan: object, actor: object) -> None:
    await _persist_or_raise(
        R21PersistenceService(session).record_plan(  # type: ignore[arg-type]
            plan,  # type: ignore[arg-type]
            actor_type=getattr(actor, "actor_type", "unknown"),
            actor_id=getattr(actor, "subject", "unknown"),
        ),
        session,
    )


async def _record_execution(
    session: object,
    execution: object,
    actor: object,
    action: str,
) -> None:
    await _persist_or_raise(
        R21PersistenceService(session).record_execution(  # type: ignore[arg-type]
            execution,  # type: ignore[arg-type]
            actor_type=getattr(actor, "actor_type", "unknown"),
            actor_id=getattr(actor, "subject", "unknown"),
            action=action,
        ),
        session,
    )


async def _record_recovery(session: object, recovery: dict[str, object], actor: object) -> None:
    await _persist_or_raise(
        R21PersistenceService(session).record_recovery(  # type: ignore[arg-type]
            project_key=str(
                recovery.get("project_key") or recovery.get("execution_id") or "unknown"
            ),
            execution_id=str(recovery.get("execution_id") or "unknown"),
            actor_type=getattr(actor, "actor_type", "unknown"),
            actor_id=getattr(actor, "subject", "unknown"),
            payload=recovery,
        ),
        session,
    )


async def _persist_or_raise(operation: object, session: object) -> None:
    settings = get_settings()
    if settings.app_env.lower() not in {
        "production",
        "staging",
    } and session.__class__.__module__.startswith("sqlalchemy.ext.asyncio"):
        close = getattr(operation, "close", None)
        if close is not None:
            close()
        return
    try:
        await operation  # type: ignore[misc]
        flush = getattr(session, "flush", None)
        if flush is not None:
            result = flush()
            if hasattr(result, "__await__"):
                await result
    except (SQLAlchemyError, RuntimeError) as exc:
        rollback = getattr(session, "rollback", None)
        if rollback is not None:
            try:
                result = rollback()
                if hasattr(result, "__await__"):
                    await result
            except (SQLAlchemyError, RuntimeError):
                pass
        if settings.app_env.lower() in {"production", "staging"}:
            raise HTTPException(status_code=503, detail="R21 database persistence failed") from exc


def _execution_path() -> Path:
    return _repo_root() / "runtime" / "r21-execution-orchestrator.json"


def _compilation_path(project_id: str) -> Path:
    return _repo_root() / "runtime" / "r21" / "compilations" / f"{project_id}.json"


def _plan_path(project_id: str, plan_id: str) -> Path:
    return _repo_root() / "runtime" / "r21" / "execution-plans" / project_id / f"{plan_id}.json"


def _schema_path() -> Path:
    return _repo_root() / "schemas" / "Manifest.schema.json"


def _registry_root() -> Path:
    return _repo_root() / "registry"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[6]


def _assert_project(project_id: str, manifest: dict[str, object]) -> None:
    manifest_project_id = (
        manifest.get("metadata", {}).get("id")
        if isinstance(manifest.get("metadata"), dict)
        else None
    )
    if manifest_project_id != project_id:
        raise HTTPException(status_code=409, detail="Path project does not match Manifest")


def _require_orchestrator_authority(actor: object, action: str) -> None:
    role = getattr(actor, "role", "")
    actor_type = getattr(actor, "actor_type", "")
    allowed = {
        "read": {
            "platform-admin",
            "runtime-admin",
            "runtime-service",
            "operator",
            "architect",
            "developer",
            "project-owner",
        },
        "write": {"platform-admin", "runtime-admin", "runtime-service"},
    }
    if actor_type not in {"human", "service"} or role not in allowed.get(action, set()):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "R21-ORCHESTRATOR-AUTHORITY-DENIED",
                "action": action,
                "actor_type": actor_type,
                "role": role,
            },
        )
