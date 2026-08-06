from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class R20KernelContractResponse(BaseModel):
    kernel_version: str
    lifecycle_phases: list[str]
    task_states: list[str]
    service_interfaces: list[str]
    modules: list[str]
    invariants: list[str]


class R20BootKernelRequest(BaseModel):
    project_id: str
    manifest_hash: str | None = None
    graph: dict[str, Any] | None = None
    plan: dict[str, Any] | None = None
    execution_result: dict[str, Any] | None = None
    memory_store: dict[str, Any] | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    persist: bool = True


class R20TransitionRequest(BaseModel):
    snapshot: dict[str, Any] | None = None
    next_phase: str
    persist: bool = True


class R20ValidateRequest(BaseModel):
    snapshot: dict[str, Any] | None = None


class R20RecoverRequest(BaseModel):
    snapshot: dict[str, Any] | None = None
    persist: bool = True


class R20KernelSnapshotResponse(BaseModel):
    snapshot: dict[str, Any]


class R20KernelStatusResponse(BaseModel):
    present: bool
    snapshot: dict[str, Any] | None = None


class R20ValidationResponse(BaseModel):
    valid: bool
    diagnostics: list[dict[str, Any]]
    report_hash: str


class R20KernelEventsResponse(BaseModel):
    events: list[dict[str, Any]]
