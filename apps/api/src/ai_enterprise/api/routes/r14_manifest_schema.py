from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from ai_enterprise.api.dependencies import ActorDependency
from ai_enterprise.api.r14_manifest_schema_schemas import (
    R14ManifestEvolutionValidationRequest,
    R14ManifestEvolutionValidationResponse,
    R14ManifestSchemaContractResponse,
    R14ManifestSchemaResponse,
    R14ManifestValidationRequest,
    R14ManifestValidationResponse,
)
from ai_enterprise.application.r14_manifest_schema_runtime import (
    r14_manifest_schema,
    r14_manifest_schema_contract,
    r14_validate_manifest,
    r14_validate_manifest_evolution,
)
from ai_enterprise.domain.specification.kernel import specification_hash

router = APIRouter(prefix="/r14", tags=["r14-manifest-schema"])


@router.get(
    "/manifest-schema-contract",
    response_model=R14ManifestSchemaContractResponse,
)
async def manifest_schema_contract(
    actor: ActorDependency,
) -> R14ManifestSchemaContractResponse:
    _require_human_or_service(actor)
    report = r14_manifest_schema_contract()
    return R14ManifestSchemaContractResponse(**report.model_dump(mode="json"))


@router.get("/manifest-schema", response_model=R14ManifestSchemaResponse)
async def manifest_schema(actor: ActorDependency) -> R14ManifestSchemaResponse:
    _require_human_or_service(actor)
    schema = r14_manifest_schema(_schema_path())
    return R14ManifestSchemaResponse(
        schema_document=schema,
        schema_hash=specification_hash(schema),
    )


@router.post("/manifest/validate", response_model=R14ManifestValidationResponse)
async def validate_manifest(
    request: R14ManifestValidationRequest,
    actor: ActorDependency,
) -> R14ManifestValidationResponse:
    _require_human_or_service(actor)
    report = r14_validate_manifest(request.manifest, _schema_path(), _registry_root())
    return R14ManifestValidationResponse(
        **report.model_dump(mode="json", exclude={"findings"}),
        findings=[item.model_dump(mode="json") for item in report.findings],
    )


@router.post(
    "/manifest/evolution/validate",
    response_model=R14ManifestEvolutionValidationResponse,
)
async def validate_manifest_evolution(
    request: R14ManifestEvolutionValidationRequest,
    actor: ActorDependency,
) -> R14ManifestEvolutionValidationResponse:
    _require_human_or_service(actor)
    report = r14_validate_manifest_evolution(
        request.previous_manifest,
        request.current_manifest,
    )
    return R14ManifestEvolutionValidationResponse(
        **report.model_dump(mode="json", exclude={"findings"}),
        findings=[item.model_dump(mode="json") for item in report.findings],
    )


def _schema_path() -> Path:
    return _repo_root() / "schemas" / "Manifest.schema.json"


def _registry_root() -> Path:
    return _repo_root() / "registry"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[6]


def _require_human_or_service(actor: object) -> None:
    if getattr(actor, "actor_type", None) not in {"human", "service"}:
        raise HTTPException(
            status_code=403,
            detail="R14 Manifest schema status requires operator actor",
        )
