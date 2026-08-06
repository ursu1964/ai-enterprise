from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class R17PlannerContractResponse(BaseModel):
    planner_version: str
    stages: list[str]
    generator_catalog: dict[str, dict[str, Any]]
    default_execution_policy: dict[str, Any]
    default_generator_permissions: list[dict[str, Any]]
    principles: list[str]


class R17CreatePlanRequest(BaseModel):
    graph: dict[str, Any]
    planning_options: dict[str, Any] = Field(default_factory=dict)


class R17PlanResponse(BaseModel):
    plan: dict[str, Any]
    history_reference: str | None = None


class R17ValidatePlanRequest(BaseModel):
    plan: dict[str, Any]


class R17ValidatePlanResponse(BaseModel):
    valid: bool
    diagnostics: list[dict[str, Any]]
    report_hash: str


class R17PlanHistoryResponse(BaseModel):
    records: list[dict[str, Any]]
