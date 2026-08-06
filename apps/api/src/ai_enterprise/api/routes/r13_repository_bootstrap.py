from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from ai_enterprise.api.dependencies import ActorDependency
from ai_enterprise.api.r13_repository_bootstrap_schemas import (
    R13BootstrapPipelineContractResponse,
    R13BootstrapSequenceContractResponse,
    R13BootstrapSequenceValidationRequest,
    R13BootstrapSequenceValidationResponse,
    R13ComponentBoundaryContractResponse,
    R13DirectoryContentContractResponse,
    R13ExecutableSkeletonResponse,
    R13RepositoryLayoutContractResponse,
    R13RepositoryLayoutResponse,
    R13RepositoryMissionContractResponse,
    R13RepositoryPrinciplesContractResponse,
)
from ai_enterprise.application.r13_repository_bootstrap_runtime import (
    r13_bootstrap_pipeline_contract,
    r13_bootstrap_sequence_contract,
    r13_component_boundary_contract,
    r13_directory_content_contract,
    r13_executable_skeleton_report,
    r13_repository_layout,
    r13_repository_layout_contract,
    r13_repository_mission_contract,
    r13_repository_principles_contract,
    r13_validate_bootstrap_sequence,
)

router = APIRouter(prefix="/r13", tags=["r13-repository-bootstrap"])


@router.get(
    "/repository-layout-contract",
    response_model=R13RepositoryLayoutContractResponse,
)
async def repository_layout_contract(
    actor: ActorDependency,
) -> R13RepositoryLayoutContractResponse:
    _require_human_or_service(actor)
    report = r13_repository_layout_contract()
    return R13RepositoryLayoutContractResponse(
        **report.model_dump(mode="json", exclude={"directories"}),
        directories=[item.model_dump(mode="json") for item in report.directories],
    )


@router.get("/repository-layout", response_model=R13RepositoryLayoutResponse)
async def repository_layout(actor: ActorDependency) -> R13RepositoryLayoutResponse:
    _require_human_or_service(actor)
    report = r13_repository_layout(_repo_root())
    return R13RepositoryLayoutResponse(
        **report.model_dump(mode="json", exclude={"items"}),
        items=[item.model_dump(mode="json") for item in report.items],
    )


@router.get(
    "/repository-mission-contract",
    response_model=R13RepositoryMissionContractResponse,
)
async def repository_mission_contract(
    actor: ActorDependency,
) -> R13RepositoryMissionContractResponse:
    _require_human_or_service(actor)
    report = r13_repository_mission_contract()
    return R13RepositoryMissionContractResponse(**report.model_dump(mode="json"))


@router.get(
    "/bootstrap-sequence-contract",
    response_model=R13BootstrapSequenceContractResponse,
)
async def bootstrap_sequence_contract(
    actor: ActorDependency,
) -> R13BootstrapSequenceContractResponse:
    _require_human_or_service(actor)
    report = r13_bootstrap_sequence_contract()
    return R13BootstrapSequenceContractResponse(
        **report.model_dump(mode="json", exclude={"steps"}),
        steps=[item.model_dump(mode="json") for item in report.steps],
    )


@router.get(
    "/bootstrap-pipeline-contract",
    response_model=R13BootstrapPipelineContractResponse,
)
async def bootstrap_pipeline_contract(
    actor: ActorDependency,
) -> R13BootstrapPipelineContractResponse:
    _require_human_or_service(actor)
    report = r13_bootstrap_pipeline_contract()
    return R13BootstrapPipelineContractResponse(
        **report.model_dump(mode="json", exclude={"stages"}),
        stages=[item.model_dump(mode="json") for item in report.stages],
    )


@router.post(
    "/bootstrap-sequence/validate",
    response_model=R13BootstrapSequenceValidationResponse,
)
async def validate_bootstrap_sequence(
    request: R13BootstrapSequenceValidationRequest,
    actor: ActorDependency,
) -> R13BootstrapSequenceValidationResponse:
    _require_human_or_service(actor)
    report = r13_validate_bootstrap_sequence(request.sequence)
    return R13BootstrapSequenceValidationResponse(
        **report.model_dump(mode="json", exclude={"findings"}),
        findings=[item.model_dump(mode="json") for item in report.findings],
    )


@router.get(
    "/component-boundary-contract",
    response_model=R13ComponentBoundaryContractResponse,
)
async def component_boundary_contract(
    actor: ActorDependency,
) -> R13ComponentBoundaryContractResponse:
    _require_human_or_service(actor)
    report = r13_component_boundary_contract()
    return R13ComponentBoundaryContractResponse(
        **report.model_dump(mode="json", exclude={"components"}),
        components=[item.model_dump(mode="json") for item in report.components],
    )


@router.get(
    "/directory-content-contract",
    response_model=R13DirectoryContentContractResponse,
)
async def directory_content_contract(
    actor: ActorDependency,
) -> R13DirectoryContentContractResponse:
    _require_human_or_service(actor)
    report = r13_directory_content_contract()
    return R13DirectoryContentContractResponse(
        **report.model_dump(mode="json", exclude={"rules"}),
        rules=[item.model_dump(mode="json") for item in report.rules],
    )


@router.get(
    "/repository-principles-contract",
    response_model=R13RepositoryPrinciplesContractResponse,
)
async def repository_principles_contract(
    actor: ActorDependency,
) -> R13RepositoryPrinciplesContractResponse:
    _require_human_or_service(actor)
    report = r13_repository_principles_contract()
    return R13RepositoryPrinciplesContractResponse(
        **report.model_dump(mode="json", exclude={"principles"}),
        principles=[item.model_dump(mode="json") for item in report.principles],
    )


@router.get("/executable-skeleton", response_model=R13ExecutableSkeletonResponse)
async def executable_skeleton(actor: ActorDependency) -> R13ExecutableSkeletonResponse:
    _require_human_or_service(actor)
    report = r13_executable_skeleton_report(_repo_root())
    return R13ExecutableSkeletonResponse(**report.model_dump(mode="json"))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[6]


def _require_human_or_service(actor: object) -> None:
    if getattr(actor, "actor_type", None) not in {"human", "service"}:
        raise HTTPException(
            status_code=403,
            detail="R13 repository bootstrap status requires operator actor",
        )
