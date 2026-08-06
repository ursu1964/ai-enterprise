from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class R21OrchestratorContractResponse(BaseModel):
    orchestrator_version: str
    project_states: list[str]
    work_package_states: list[str]
    artifact_promotion_levels: list[str]
    worker_types: list[str]
    principles: list[str]


class R21CompileProjectRequest(BaseModel):
    manifest: dict[str, Any]
    persist: bool = True


class R21CreatePlanRequest(BaseModel):
    manifest: dict[str, Any]
    compilation: dict[str, Any]
    persist: bool = True


class R21StartExecutionRequest(BaseModel):
    plan: dict[str, Any]
    options: dict[str, Any] = Field(default_factory=dict)
    persist: bool = True


class R21ExecutionMutationRequest(BaseModel):
    execution: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    persist: bool = True


class R21ApprovalDecisionRequest(BaseModel):
    execution: dict[str, Any] | None = None
    decision: str
    actor_role: str
    actor_id: str
    persist: bool = True


class R21RecoverRequest(BaseModel):
    checkpoint: dict[str, Any]


class R21ImpactAnalysisRequest(BaseModel):
    previous_manifest: dict[str, Any]
    current_manifest: dict[str, Any]
    plan: dict[str, Any]
    execution: dict[str, Any]


class R21CompilationResponse(BaseModel):
    compilation: dict[str, Any]


class R21PlanResponse(BaseModel):
    plan: dict[str, Any]


class R21ExecutionResponse(BaseModel):
    execution: dict[str, Any]


class R21ExecutionStatusResponse(BaseModel):
    present: bool
    execution: dict[str, Any] | None = None


class R21ListResponse(BaseModel):
    items: list[dict[str, Any]]


class R21RecoverResponse(BaseModel):
    recovery: dict[str, Any]


class R21ImpactAnalysisResponse(BaseModel):
    analysis: dict[str, Any]
