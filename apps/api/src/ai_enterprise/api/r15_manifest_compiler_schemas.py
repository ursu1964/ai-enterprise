from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class R15CompilerContractResponse(BaseModel):
    compiler_version: str
    stages: list[str]
    principles: list[str]


class R15CompileRequest(BaseModel):
    manifest: dict[str, Any]
    compiler_options: dict[str, Any] = Field(default_factory=dict)


class R15CompileResponse(BaseModel):
    success_status: bool
    knowledge_graph: dict[str, Any] | None
    dependency_graph: dict[str, Any] | None
    execution_graph: dict[str, Any] | None
    incremental_impact: dict[str, Any]
    pass_reports: list[dict[str, Any]]
    compilation_report: dict[str, Any]
    diagnostics: list[dict[str, Any]]
    result_hash: str
    history_reference: str | None = None


class R15CompilationHistoryResponse(BaseModel):
    records: list[dict[str, Any]]
