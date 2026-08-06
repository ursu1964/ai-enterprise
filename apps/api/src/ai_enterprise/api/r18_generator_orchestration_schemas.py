from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class R18OrchestratorContractResponse(BaseModel):
    orchestrator_version: str
    builtin_generators: list[dict[str, Any]]
    principles: list[str]


class R18ValidateRegistryRequest(BaseModel):
    generator_registry: list[dict[str, Any]] | None = None


class R18ValidateRegistryResponse(BaseModel):
    valid: bool
    diagnostics: list[dict[str, Any]]
    registry_hash: str


class R18ProviderReadinessRequest(BaseModel):
    generator_registry: list[dict[str, Any]] | None = None
    orchestration_options: dict[str, Any] = Field(default_factory=dict)


class R18ProviderReadinessResponse(BaseModel):
    providers: list[dict[str, Any]]


class R18ExecutePlanRequest(BaseModel):
    plan: dict[str, Any]
    graph: dict[str, Any]
    generator_registry: list[dict[str, Any]] | None = None
    orchestration_options: dict[str, Any] = Field(default_factory=dict)


class R18ExecutionResponse(BaseModel):
    result: dict[str, Any]
    history_reference: str | None = None


class R18ExecutionHistoryResponse(BaseModel):
    records: list[dict[str, Any]]
