from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

CLASSIFICATION_ORDER = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
COST_ORDER = {"free": 0, "low": 1, "medium": 2, "high": 3}


@dataclass(frozen=True)
class ModelDeployment:
    id: UUID
    provider_key: str
    model_reference: str
    deployment_class: str
    context_window: int
    supports_tools: bool
    supports_structured_output: bool
    maximum_data_classification: str
    cost_class: str = "low"
    latency_class: str = "standard"
    reliability_band: int = 0
    status: str = "active"


@dataclass(frozen=True)
class ModelRoutingPolicy:
    version: str
    required_context_window: int
    require_tool_support: bool
    require_structured_output: bool
    allowed_provider_keys: tuple[str, ...]
    allowed_deployment_classes: tuple[str, ...]
    maximum_cost_class: str
    maximum_data_classification: str
    fallback_allowed: bool = False
    maximum_fallbacks: int = 0
    preferred_deployment_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True)
class ModelRoute:
    policy_version: str
    candidate_ids: tuple[UUID, ...]
    selected_id: UUID | None
    fallback_ids: tuple[UUID, ...]
    rejected: tuple[dict[str, str], ...]
    selection_reasons: tuple[str, ...]


class ModelRouter:
    def route(
        self,
        deployments: tuple[ModelDeployment, ...],
        policy: ModelRoutingPolicy,
        *,
        context_classification: str,
    ) -> ModelRoute:
        eligible: list[ModelDeployment] = []
        rejected: list[dict[str, str]] = []
        for deployment in sorted(deployments, key=lambda item: str(item.id)):
            reasons: list[str] = []
            if deployment.status != "active":
                reasons.append("MODEL-INACTIVE")
            if deployment.provider_key not in policy.allowed_provider_keys:
                reasons.append("PROVIDER-NOT-ALLOWED")
            if deployment.deployment_class not in policy.allowed_deployment_classes:
                reasons.append("DEPLOYMENT-CLASS-NOT-ALLOWED")
            if deployment.context_window < policy.required_context_window:
                reasons.append("CONTEXT-WINDOW-INSUFFICIENT")
            if policy.require_tool_support and not deployment.supports_tools:
                reasons.append("TOOL-SUPPORT-REQUIRED")
            if policy.require_structured_output and not deployment.supports_structured_output:
                reasons.append("STRUCTURED-OUTPUT-REQUIRED")
            if CLASSIFICATION_ORDER.get(context_classification, 99) > CLASSIFICATION_ORDER.get(
                deployment.maximum_data_classification, -1
            ):
                reasons.append("CLASSIFICATION-VIOLATION")
            if CLASSIFICATION_ORDER.get(context_classification, 99) > CLASSIFICATION_ORDER.get(
                policy.maximum_data_classification, -1
            ):
                reasons.append("POLICY-CLASSIFICATION-VIOLATION")
            if COST_ORDER.get(deployment.cost_class, 99) > COST_ORDER.get(
                policy.maximum_cost_class, -1
            ):
                reasons.append("COST-CLASS-EXCEEDED")
            if reasons:
                rejected.append({"deployment_id": str(deployment.id), "reasons": ",".join(reasons)})
            else:
                eligible.append(deployment)
        preferences = {item: index for index, item in enumerate(policy.preferred_deployment_ids)}
        eligible.sort(
            key=lambda item: (
                preferences.get(item.id, len(preferences)),
                item.deployment_class != "local",
                -item.reliability_band,
                COST_ORDER.get(item.cost_class, 99),
                item.latency_class,
                item.model_reference,
                str(item.id),
            )
        )
        selected = eligible[0].id if eligible else None
        fallbacks = eligible[1 : 1 + policy.maximum_fallbacks] if policy.fallback_allowed else []
        return ModelRoute(
            policy_version=policy.version,
            candidate_ids=tuple(item.id for item in eligible),
            selected_id=selected,
            fallback_ids=tuple(item.id for item in fallbacks),
            rejected=tuple(rejected),
            selection_reasons=("deterministic-policy-ranking",)
            if selected
            else ("no-compliant-model",),
        )


@dataclass(frozen=True)
class ModelGenerationResult:
    output: str
    input_token_count: int = 0
    output_token_count: int = 0
    finish_reason: str = "stop"


class ModelProviderPort(Protocol):
    def generate(
        self,
        *,
        model_reference: str,
        messages: tuple[dict[str, object], ...],
        tools: tuple[dict[str, object], ...],
        output_schema: dict[str, object],
        runtime_limits: dict[str, int],
    ) -> ModelGenerationResult: ...


@dataclass
class FakeModelProvider:
    responses: list[str]
    requests: list[dict[str, object]] = field(default_factory=list)

    def generate(self, **kwargs: object) -> ModelGenerationResult:
        self.requests.append(dict(kwargs))
        if not self.responses:
            raise RuntimeError("FAKE-PROVIDER-EXHAUSTED")
        return ModelGenerationResult(output=self.responses.pop(0))
