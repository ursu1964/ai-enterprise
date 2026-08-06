from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from ai_enterprise.api.dependencies import ActorDependency
from ai_enterprise.api.r12_bootstrap_schemas import (
    R12BootstrapPlanResponse,
    R12BuildManifestContractResponse,
    R12BuildManifestValidationRequest,
    R12BuildManifestValidationResponse,
    R12DeliveryArchitectureContractResponse,
    R12DeliveryArchitectureValidationRequest,
    R12DeliveryArchitectureValidationResponse,
    R12DeterministicFingerprintContractResponse,
    R12DeterministicFingerprintRequest,
    R12DeterministicFingerprintResponse,
    R12ErrorContractResponse,
    R12ErrorContractValidationRequest,
    R12ErrorContractValidationResponse,
    R12IdentityContractValidationRequest,
    R12IdentityContractValidationResponse,
    R12ImplementationStatusResponse,
    R12OperationalBaselineContractResponse,
    R12OperationalBaselineValidationRequest,
    R12OperationalBaselineValidationResponse,
    R12PlatformEntityCatalogResponse,
    R12RepositoryLayoutResponse,
    R12RoadmapGovernanceContractResponse,
    R12RoadmapGovernanceValidationRequest,
    R12RoadmapGovernanceValidationResponse,
    R12SharedContractCatalogResponse,
    R12SharedContractValidationRequest,
    R12SharedContractValidationResponse,
    R12VerificationStrategyContractResponse,
    R12VerificationStrategyValidationRequest,
    R12VerificationStrategyValidationResponse,
)
from ai_enterprise.application.r12_bootstrap_runtime import (
    r12_bootstrap_plan,
    r12_build_manifest_contract,
    r12_compute_deterministic_fingerprint,
    r12_delivery_architecture_contract,
    r12_deterministic_fingerprint_contract,
    r12_error_contract,
    r12_implementation_status,
    r12_operational_baseline_contract,
    r12_platform_entity_catalog,
    r12_repository_layout,
    r12_roadmap_governance_contract,
    r12_shared_contract_catalog,
    r12_validate_build_manifest,
    r12_validate_delivery_architecture,
    r12_validate_error_contract,
    r12_validate_identity_contract,
    r12_validate_operational_baseline,
    r12_validate_roadmap_governance,
    r12_validate_shared_contract,
    r12_validate_verification_strategy,
    r12_verification_strategy_contract,
)

router = APIRouter(prefix="/r12", tags=["r12-bootstrap"])


@router.get("/implementation-status", response_model=R12ImplementationStatusResponse)
async def implementation_status(actor: ActorDependency) -> R12ImplementationStatusResponse:
    _require_human_or_service(actor)
    report = r12_implementation_status(_repo_root())
    return R12ImplementationStatusResponse(
        **report.model_dump(mode="json", exclude={"phases"}),
        phases=[item.model_dump(mode="json") for item in report.phases],
    )


@router.get("/repository-layout", response_model=R12RepositoryLayoutResponse)
async def repository_layout(actor: ActorDependency) -> R12RepositoryLayoutResponse:
    _require_human_or_service(actor)
    report = r12_repository_layout(_repo_root())
    return R12RepositoryLayoutResponse(
        **report.model_dump(mode="json", exclude={"items"}),
        items=[item.model_dump(mode="json") for item in report.items],
    )


@router.get("/bootstrap-plan", response_model=R12BootstrapPlanResponse)
async def bootstrap_plan(actor: ActorDependency) -> R12BootstrapPlanResponse:
    _require_human_or_service(actor)
    report = r12_bootstrap_plan()
    return R12BootstrapPlanResponse(
        **report.model_dump(mode="json", exclude={"commands"}),
        commands=[item.model_dump(mode="json") for item in report.commands],
    )


@router.get(
    "/build-manifest-contract",
    response_model=R12BuildManifestContractResponse,
)
async def build_manifest_contract(
    actor: ActorDependency,
) -> R12BuildManifestContractResponse:
    _require_human_or_service(actor)
    report = r12_build_manifest_contract()
    return R12BuildManifestContractResponse(
        **report.model_dump(mode="json", exclude={"requirements"}),
        requirements=[item.model_dump(mode="json") for item in report.requirements],
    )


@router.post(
    "/build-manifest/validate",
    response_model=R12BuildManifestValidationResponse,
)
async def validate_build_manifest(
    request: R12BuildManifestValidationRequest,
    actor: ActorDependency,
) -> R12BuildManifestValidationResponse:
    _require_human_or_service(actor)
    report = r12_validate_build_manifest(request.manifest)
    return R12BuildManifestValidationResponse(
        **report.model_dump(mode="json", exclude={"findings"}),
        findings=[item.model_dump(mode="json") for item in report.findings],
    )


@router.get("/error-contract", response_model=R12ErrorContractResponse)
async def error_contract(actor: ActorDependency) -> R12ErrorContractResponse:
    _require_human_or_service(actor)
    report = r12_error_contract()
    return R12ErrorContractResponse(
        **report.model_dump(mode="json", exclude={"fields"}),
        fields=[item.model_dump(mode="json") for item in report.fields],
    )


@router.post(
    "/error-contract/validate",
    response_model=R12ErrorContractValidationResponse,
)
async def validate_error_contract(
    request: R12ErrorContractValidationRequest,
    actor: ActorDependency,
) -> R12ErrorContractValidationResponse:
    _require_human_or_service(actor)
    report = r12_validate_error_contract(request.error)
    return R12ErrorContractValidationResponse(
        **report.model_dump(mode="json", exclude={"findings"}),
        findings=[item.model_dump(mode="json") for item in report.findings],
    )


@router.get("/shared-contracts", response_model=R12SharedContractCatalogResponse)
async def shared_contracts(actor: ActorDependency) -> R12SharedContractCatalogResponse:
    _require_human_or_service(actor)
    report = r12_shared_contract_catalog()
    return R12SharedContractCatalogResponse(
        **report.model_dump(mode="json", exclude={"contracts"}),
        contracts=[
            {
                **item.model_dump(mode="json", exclude={"fields"}),
                "fields": [field.model_dump(mode="json") for field in item.fields],
            }
            for item in report.contracts
        ],
    )


@router.post(
    "/shared-contracts/validate",
    response_model=R12SharedContractValidationResponse,
)
async def validate_shared_contract(
    request: R12SharedContractValidationRequest,
    actor: ActorDependency,
) -> R12SharedContractValidationResponse:
    _require_human_or_service(actor)
    report = r12_validate_shared_contract(request.contract_type, request.envelope)
    return R12SharedContractValidationResponse(
        **report.model_dump(mode="json", exclude={"findings"}),
        findings=[item.model_dump(mode="json") for item in report.findings],
    )


@router.get("/platform-entities", response_model=R12PlatformEntityCatalogResponse)
async def platform_entities(actor: ActorDependency) -> R12PlatformEntityCatalogResponse:
    _require_human_or_service(actor)
    report = r12_platform_entity_catalog()
    return R12PlatformEntityCatalogResponse(
        **report.model_dump(mode="json", exclude={"entities"}),
        entities=[item.model_dump(mode="json") for item in report.entities],
    )


@router.post(
    "/identity-contract/validate",
    response_model=R12IdentityContractValidationResponse,
)
async def validate_identity_contract(
    request: R12IdentityContractValidationRequest,
    actor: ActorDependency,
) -> R12IdentityContractValidationResponse:
    _require_human_or_service(actor)
    report = r12_validate_identity_contract(request.entity)
    return R12IdentityContractValidationResponse(
        **report.model_dump(mode="json", exclude={"findings"}),
        findings=[item.model_dump(mode="json") for item in report.findings],
    )


@router.get(
    "/deterministic-fingerprint-contract",
    response_model=R12DeterministicFingerprintContractResponse,
)
async def deterministic_fingerprint_contract(
    actor: ActorDependency,
) -> R12DeterministicFingerprintContractResponse:
    _require_human_or_service(actor)
    report = r12_deterministic_fingerprint_contract()
    return R12DeterministicFingerprintContractResponse(**report.model_dump(mode="json"))


@router.post(
    "/deterministic-fingerprint",
    response_model=R12DeterministicFingerprintResponse,
)
async def deterministic_fingerprint(
    request: R12DeterministicFingerprintRequest,
    actor: ActorDependency,
) -> R12DeterministicFingerprintResponse:
    _require_human_or_service(actor)
    report = r12_compute_deterministic_fingerprint(request.inputs)
    return R12DeterministicFingerprintResponse(
        **report.model_dump(mode="json", exclude={"findings"}),
        findings=[item.model_dump(mode="json") for item in report.findings],
    )


@router.get(
    "/operational-baseline-contract",
    response_model=R12OperationalBaselineContractResponse,
)
async def operational_baseline_contract(
    actor: ActorDependency,
) -> R12OperationalBaselineContractResponse:
    _require_human_or_service(actor)
    report = r12_operational_baseline_contract()
    return R12OperationalBaselineContractResponse(
        **report.model_dump(mode="json", exclude={"sections"}),
        sections=[item.model_dump(mode="json") for item in report.sections],
    )


@router.post(
    "/operational-baseline/validate",
    response_model=R12OperationalBaselineValidationResponse,
)
async def validate_operational_baseline(
    request: R12OperationalBaselineValidationRequest,
    actor: ActorDependency,
) -> R12OperationalBaselineValidationResponse:
    _require_human_or_service(actor)
    report = r12_validate_operational_baseline(request.evidence)
    return R12OperationalBaselineValidationResponse(
        **report.model_dump(mode="json", exclude={"findings"}),
        findings=[item.model_dump(mode="json") for item in report.findings],
    )


@router.get(
    "/verification-strategy-contract",
    response_model=R12VerificationStrategyContractResponse,
)
async def verification_strategy_contract(
    actor: ActorDependency,
) -> R12VerificationStrategyContractResponse:
    _require_human_or_service(actor)
    report = r12_verification_strategy_contract()
    return R12VerificationStrategyContractResponse(
        **report.model_dump(mode="json", exclude={"sections"}),
        sections=[item.model_dump(mode="json") for item in report.sections],
    )


@router.post(
    "/verification-strategy/validate",
    response_model=R12VerificationStrategyValidationResponse,
)
async def validate_verification_strategy(
    request: R12VerificationStrategyValidationRequest,
    actor: ActorDependency,
) -> R12VerificationStrategyValidationResponse:
    _require_human_or_service(actor)
    report = r12_validate_verification_strategy(request.evidence)
    return R12VerificationStrategyValidationResponse(
        **report.model_dump(mode="json", exclude={"findings"}),
        findings=[item.model_dump(mode="json") for item in report.findings],
    )


@router.get(
    "/roadmap-governance-contract",
    response_model=R12RoadmapGovernanceContractResponse,
)
async def roadmap_governance_contract(
    actor: ActorDependency,
) -> R12RoadmapGovernanceContractResponse:
    _require_human_or_service(actor)
    report = r12_roadmap_governance_contract()
    return R12RoadmapGovernanceContractResponse(
        **report.model_dump(mode="json", exclude={"sections"}),
        sections=[item.model_dump(mode="json") for item in report.sections],
    )


@router.post(
    "/roadmap-governance/validate",
    response_model=R12RoadmapGovernanceValidationResponse,
)
async def validate_roadmap_governance(
    request: R12RoadmapGovernanceValidationRequest,
    actor: ActorDependency,
) -> R12RoadmapGovernanceValidationResponse:
    _require_human_or_service(actor)
    report = r12_validate_roadmap_governance(request.evidence)
    return R12RoadmapGovernanceValidationResponse(
        **report.model_dump(mode="json", exclude={"findings"}),
        findings=[item.model_dump(mode="json") for item in report.findings],
    )


@router.get(
    "/delivery-architecture-contract",
    response_model=R12DeliveryArchitectureContractResponse,
)
async def delivery_architecture_contract(
    actor: ActorDependency,
) -> R12DeliveryArchitectureContractResponse:
    _require_human_or_service(actor)
    report = r12_delivery_architecture_contract()
    return R12DeliveryArchitectureContractResponse(
        **report.model_dump(mode="json", exclude={"sections"}),
        sections=[item.model_dump(mode="json") for item in report.sections],
    )


@router.post(
    "/delivery-architecture/validate",
    response_model=R12DeliveryArchitectureValidationResponse,
)
async def validate_delivery_architecture(
    request: R12DeliveryArchitectureValidationRequest,
    actor: ActorDependency,
) -> R12DeliveryArchitectureValidationResponse:
    _require_human_or_service(actor)
    report = r12_validate_delivery_architecture(request.evidence)
    return R12DeliveryArchitectureValidationResponse(
        **report.model_dump(mode="json", exclude={"findings"}),
        findings=[item.model_dump(mode="json") for item in report.findings],
    )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[6]


def _require_human_or_service(actor: object) -> None:
    if getattr(actor, "actor_type", None) not in {"human", "service"}:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="R12 bootstrap status requires operator actor")
