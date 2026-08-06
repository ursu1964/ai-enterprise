from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from ai_enterprise.api.dependencies import ActorDependency
from ai_enterprise.api.r18_generator_orchestration_schemas import (
    R18ExecutePlanRequest,
    R18ExecutionHistoryResponse,
    R18ExecutionResponse,
    R18OrchestratorContractResponse,
    R18ProviderReadinessRequest,
    R18ProviderReadinessResponse,
    R18ValidateRegistryRequest,
    R18ValidateRegistryResponse,
)
from ai_enterprise.application.r18_generator_orchestration_runtime import (
    BUILTIN_GENERATOR_REGISTRY,
    ORCHESTRATOR_VERSION,
    r18_check_provider_readiness,
    r18_orchestrate_execution,
    r18_persist_execution_result,
    r18_read_execution_history,
    r18_validate_generator_registry,
)
from ai_enterprise.config import get_settings

router = APIRouter(prefix="/r18", tags=["r18-generator-orchestration"])


@router.get("/orchestrator-contract", response_model=R18OrchestratorContractResponse)
async def orchestrator_contract(actor: ActorDependency) -> R18OrchestratorContractResponse:
    _require_human_or_service(actor)
    return R18OrchestratorContractResponse(
        orchestrator_version=ORCHESTRATOR_VERSION,
        builtin_generators=[item.model_dump(mode="json") for item in BUILTIN_GENERATOR_REGISTRY],
        principles=[
            "deterministic-generator-selection",
            "shared-semantic-context",
            "artifact-traceability",
            "central-artifact-repository",
            "stage-validation",
            "generator-isolation",
            "human-review-gates",
            "immutable-execution-history",
            "external-provider-readiness",
            "physical-artifact-materialization",
        ],
    )


@router.post("/generator-registry/validate", response_model=R18ValidateRegistryResponse)
async def validate_generator_registry(
    request: R18ValidateRegistryRequest,
    actor: ActorDependency,
) -> R18ValidateRegistryResponse:
    _require_human_or_service(actor)
    report = r18_validate_generator_registry(request.generator_registry)
    return R18ValidateRegistryResponse(
        valid=report.valid,
        diagnostics=[item.model_dump(mode="json") for item in report.diagnostics],
        registry_hash=report.registry_hash,
    )


@router.post("/provider-readiness", response_model=R18ProviderReadinessResponse)
async def provider_readiness(
    request: R18ProviderReadinessRequest,
    actor: ActorDependency,
) -> R18ProviderReadinessResponse:
    _require_human_or_service(actor)
    return R18ProviderReadinessResponse(
        providers=[
            item.model_dump(mode="json")
            for item in r18_check_provider_readiness(
                request.generator_registry,
                _runtime_options(request.orchestration_options),
            )
        ]
    )


@router.get("/execution-history", response_model=R18ExecutionHistoryResponse)
async def execution_history(actor: ActorDependency) -> R18ExecutionHistoryResponse:
    _require_human_or_service(actor)
    return R18ExecutionHistoryResponse(records=list(r18_read_execution_history(_history_path())))


@router.post("/execute-plan", response_model=R18ExecutionResponse)
async def execute_plan(
    request: R18ExecutePlanRequest,
    actor: ActorDependency,
) -> R18ExecutionResponse:
    _require_human_or_service(actor)
    result = r18_orchestrate_execution(
        request.plan,
        request.graph,
        generator_registry=request.generator_registry,
        orchestration_options=_runtime_options(request.orchestration_options),
    )
    history_reference = None
    if request.orchestration_options.get("persist_history") is True:
        history_reference = r18_persist_execution_result(
            result,
            _history_path(),
            actor_id=getattr(actor, "subject", "unknown"),
        )
    return R18ExecutionResponse(
        result=result.model_dump(mode="json"),
        history_reference=history_reference,
    )


def _history_path() -> Path:
    return _repo_root() / "runtime" / "r18-execution-history.jsonl"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[6]


def _runtime_options(request_options: dict[str, object]) -> dict[str, object]:
    settings = get_settings()
    provider_configs = {
        "openai": {
            "credential_reference": "settings:r18_openai_api_key",
            "api_key": (
                settings.r18_openai_api_key.get_secret_value()
                if settings.r18_openai_api_key
                else None
            ),
            "model_reference": settings.r18_openai_model,
            "endpoint_reference": settings.r18_openai_base_url,
            "timeout_seconds": settings.r18_provider_timeout_seconds,
        },
        "anthropic": {
            "credential_reference": "settings:r18_anthropic_api_key",
            "api_key": (
                settings.r18_anthropic_api_key.get_secret_value()
                if settings.r18_anthropic_api_key
                else None
            ),
            "model_reference": settings.r18_anthropic_model,
            "endpoint_reference": settings.r18_anthropic_base_url,
            "timeout_seconds": settings.r18_provider_timeout_seconds,
        },
        "google": {
            "credential_reference": "settings:r18_google_api_key",
            "api_key": (
                settings.r18_google_api_key.get_secret_value()
                if settings.r18_google_api_key
                else None
            ),
            "model_reference": settings.r18_google_model,
            "timeout_seconds": settings.r18_provider_timeout_seconds,
        },
        "custom-http": {
            "credential_reference": "settings:r18_custom_provider_api_key",
            "api_key": (
                settings.r18_custom_provider_api_key.get_secret_value()
                if settings.r18_custom_provider_api_key
                else None
            ),
            "model_reference": settings.r18_custom_provider_model,
            "endpoint_reference": settings.r18_custom_provider_base_url,
            "timeout_seconds": settings.r18_provider_timeout_seconds,
        },
    }
    clean_provider_configs = {
        provider: {key: value for key, value in config.items() if value is not None}
        for provider, config in provider_configs.items()
    }
    merged = dict(request_options)
    explicit_configs = merged.get("provider_configs")
    if isinstance(explicit_configs, dict):
        merged["provider_configs"] = {
            **clean_provider_configs,
            **explicit_configs,
        }
    else:
        merged["provider_configs"] = clean_provider_configs
    merged.setdefault("enable_live_provider_calls", settings.r18_live_provider_calls_enabled)
    return merged


def _require_human_or_service(actor: object) -> None:
    if getattr(actor, "actor_type", None) not in {"human", "service"}:
        raise HTTPException(
            status_code=403,
            detail="R18 Generator Orchestrator requires operator actor",
        )
