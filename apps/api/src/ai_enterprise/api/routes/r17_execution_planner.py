from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from ai_enterprise.api.dependencies import ActorDependency
from ai_enterprise.api.r17_execution_planner_schemas import (
    R17CreatePlanRequest,
    R17PlanHistoryResponse,
    R17PlannerContractResponse,
    R17PlanResponse,
    R17ValidatePlanRequest,
    R17ValidatePlanResponse,
)
from ai_enterprise.application.r17_execution_planner_runtime import (
    GENERATOR_CATALOG,
    PLANNER_VERSION,
    PLANNING_STAGES,
    R17ExecutionPlan,
    _execution_policy,
    _generator_permissions,
    r17_create_execution_plan,
    r17_persist_execution_plan,
    r17_read_execution_plan_history,
    r17_validate_execution_plan,
)

router = APIRouter(prefix="/r17", tags=["r17-execution-planner"])


@router.get("/planner-contract", response_model=R17PlannerContractResponse)
async def planner_contract(actor: ActorDependency) -> R17PlannerContractResponse:
    _require_human_or_service(actor)
    return R17PlannerContractResponse(
        planner_version=PLANNER_VERSION,
        stages=[stage_id for stage_id, _ in PLANNING_STAGES],
        generator_catalog=GENERATOR_CATALOG,
        default_execution_policy=_execution_policy({}).model_dump(mode="json"),
        default_generator_permissions=[
            item.model_dump(mode="json") for item in _generator_permissions({})
        ],
        principles=[
            "deterministic",
            "dependency-aware",
            "parallel-safe",
            "explainable",
            "incremental",
            "signed-before-use",
            "permission-bounded",
            "policy-enforced",
            "resource-aware",
        ],
    )


@router.get("/execution-plan/history", response_model=R17PlanHistoryResponse)
async def execution_plan_history(actor: ActorDependency) -> R17PlanHistoryResponse:
    _require_human_or_service(actor)
    return R17PlanHistoryResponse(records=list(r17_read_execution_plan_history(_history_path())))


@router.post("/execution-plan/create", response_model=R17PlanResponse)
async def create_execution_plan(
    request: R17CreatePlanRequest,
    actor: ActorDependency,
) -> R17PlanResponse:
    _require_human_or_service(actor)
    plan = r17_create_execution_plan(
        request.graph,
        planning_options=request.planning_options,
    )
    history_reference = None
    if request.planning_options.get("persist_history") is True:
        history_reference = r17_persist_execution_plan(
            plan,
            _history_path(),
            actor_id=getattr(actor, "subject", "unknown"),
        )
    return R17PlanResponse(
        plan=plan.model_dump(mode="json"),
        history_reference=history_reference,
    )


@router.post("/execution-plan/validate", response_model=R17ValidatePlanResponse)
async def validate_execution_plan(
    request: R17ValidatePlanRequest,
    actor: ActorDependency,
) -> R17ValidatePlanResponse:
    _require_human_or_service(actor)
    report = r17_validate_execution_plan(R17ExecutionPlan.model_validate(request.plan))
    return R17ValidatePlanResponse(
        valid=report.valid,
        diagnostics=[item.model_dump(mode="json") for item in report.diagnostics],
        report_hash=report.report_hash,
    )


def _history_path() -> Path:
    return _repo_root() / "planner" / "history.jsonl"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[6]


def _require_human_or_service(actor: object) -> None:
    if getattr(actor, "actor_type", None) not in {"human", "service"}:
        raise HTTPException(
            status_code=403,
            detail="R17 Execution Planner requires operator actor",
        )
