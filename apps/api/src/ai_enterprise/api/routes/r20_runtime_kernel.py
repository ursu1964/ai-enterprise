from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from ai_enterprise.api.dependencies import ActorDependency
from ai_enterprise.api.r20_runtime_kernel_schemas import (
    R20BootKernelRequest,
    R20KernelContractResponse,
    R20KernelEventsResponse,
    R20KernelSnapshotResponse,
    R20KernelStatusResponse,
    R20RecoverRequest,
    R20TransitionRequest,
    R20ValidateRequest,
    R20ValidationResponse,
)
from ai_enterprise.application.r20_runtime_kernel_runtime import (
    LIFECYCLE_PHASES,
    MODULES,
    RUNTIME_KERNEL_VERSION,
    SERVICE_INTERFACES,
    TASK_STATES,
    R20KernelSnapshot,
    r20_boot_kernel,
    r20_read_kernel,
    r20_recover_kernel,
    r20_transition_lifecycle,
    r20_validate_kernel,
    r20_write_kernel,
)

router = APIRouter(prefix="/r20", tags=["r20-runtime-kernel"])


@router.get("/runtime-kernel-contract", response_model=R20KernelContractResponse)
async def runtime_kernel_contract(actor: ActorDependency) -> R20KernelContractResponse:
    _require_runtime_authority(actor, "read")
    return R20KernelContractResponse(
        kernel_version=RUNTIME_KERNEL_VERSION,
        lifecycle_phases=list(LIFECYCLE_PHASES),
        task_states=list(TASK_STATES),
        service_interfaces=list(SERVICE_INTERFACES),
        modules=list(MODULES),
        invariants=[
            "no-execution-without-validated-manifest",
            "no-generator-without-approved-plan",
            "no-artifact-without-traceability",
            "no-invalid-state-transition",
            "no-policy-bypass",
            "no-hidden-context",
            "no-silent-failure",
            "recoverable-state",
        ],
    )


@router.post("/runtime-kernel/boot", response_model=R20KernelSnapshotResponse)
async def boot_runtime_kernel(
    request: R20BootKernelRequest,
    actor: ActorDependency,
) -> R20KernelSnapshotResponse:
    _require_runtime_authority(actor, "write")
    snapshot = r20_boot_kernel(
        project_id=request.project_id,
        manifest_hash=request.manifest_hash,
        graph=request.graph,
        plan=request.plan,
        execution_result=request.execution_result,
        memory_store=request.memory_store,
        config=request.config,
    )
    if request.persist:
        _write(snapshot)
    return R20KernelSnapshotResponse(snapshot=snapshot.model_dump(mode="json"))


@router.post("/runtime-kernel/transition", response_model=R20KernelSnapshotResponse)
async def transition_runtime_kernel(
    request: R20TransitionRequest,
    actor: ActorDependency,
) -> R20KernelSnapshotResponse:
    _require_runtime_authority(actor, "write")
    base = request.snapshot or _read_required().model_dump(mode="json")
    snapshot = r20_transition_lifecycle(base, request.next_phase)
    if request.persist:
        _write(snapshot)
    return R20KernelSnapshotResponse(snapshot=snapshot.model_dump(mode="json"))


@router.post("/runtime-kernel/validate", response_model=R20ValidationResponse)
async def validate_runtime_kernel(
    request: R20ValidateRequest,
    actor: ActorDependency,
) -> R20ValidationResponse:
    _require_runtime_authority(actor, "read")
    base = request.snapshot or _read_required().model_dump(mode="json")
    report = r20_validate_kernel(base)
    return R20ValidationResponse(
        valid=report.valid,
        diagnostics=[item.model_dump(mode="json") for item in report.diagnostics],
        report_hash=report.report_hash,
    )


@router.post("/runtime-kernel/recover", response_model=R20KernelSnapshotResponse)
async def recover_runtime_kernel(
    request: R20RecoverRequest,
    actor: ActorDependency,
) -> R20KernelSnapshotResponse:
    _require_runtime_authority(actor, "write")
    base = request.snapshot or _read_required().model_dump(mode="json")
    snapshot = r20_recover_kernel(base)
    if request.persist:
        _write(snapshot)
    return R20KernelSnapshotResponse(snapshot=snapshot.model_dump(mode="json"))


@router.get("/runtime-kernel/status", response_model=R20KernelStatusResponse)
async def runtime_kernel_status(actor: ActorDependency) -> R20KernelStatusResponse:
    _require_runtime_authority(actor, "read")
    snapshot = r20_read_kernel(_kernel_path())
    return R20KernelStatusResponse(
        present=snapshot is not None,
        snapshot=snapshot.model_dump(mode="json") if snapshot else None,
    )


@router.get("/runtime-kernel/events", response_model=R20KernelEventsResponse)
async def runtime_kernel_events(actor: ActorDependency) -> R20KernelEventsResponse:
    _require_runtime_authority(actor, "read")
    snapshot = _read_required()
    return R20KernelEventsResponse(
        events=[item.model_dump(mode="json") for item in snapshot.event_history]
    )


def _read_required() -> R20KernelSnapshot:
    snapshot = r20_read_kernel(_kernel_path())
    if snapshot is None:
        raise HTTPException(status_code=404, detail="R20 runtime kernel snapshot is not present")
    return snapshot


def _write(snapshot: object) -> str:
    return r20_write_kernel(snapshot, _kernel_path())


def _kernel_path() -> Path:
    return _repo_root() / "runtime" / "r20-runtime-kernel.json"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[6]


def _require_runtime_authority(actor: object, action: str) -> None:
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
        },
        "write": {"platform-admin", "runtime-admin", "runtime-service"},
    }
    if actor_type not in {"human", "service"} or role not in allowed.get(action, set()):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "R20-RUNTIME-AUTHORITY-DENIED",
                "action": action,
                "actor_type": actor_type,
                "role": role,
            },
        )
