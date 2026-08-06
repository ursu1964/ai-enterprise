from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class R16GraphLoadRequest(BaseModel):
    knowledge_graph: dict[str, Any]
    compilation_report: dict[str, Any] | None = None


class R16GraphResponse(BaseModel):
    graph: dict[str, Any]


class R16GraphValidationRequest(BaseModel):
    graph: dict[str, Any]


class R16GraphValidationResponse(BaseModel):
    valid: bool
    diagnostics: list[dict[str, Any]]
    report_hash: str


class R16GraphQueryRequest(BaseModel):
    graph: dict[str, Any]
    query: dict[str, Any] = Field(default_factory=dict)


class R16GraphFindRequest(BaseModel):
    graph: dict[str, Any]
    node_id: str | None = None
    node_type: str | None = None


class R16GraphTraverseRequest(BaseModel):
    graph: dict[str, Any]
    start_node_id: str
    max_depth: int = 2


class R16GraphImpactRequest(BaseModel):
    graph: dict[str, Any]
    start_node_id: str
    max_depth: int = 99


class R16GraphAccessRequest(BaseModel):
    graph: dict[str, Any]
    policy: dict[str, Any] = Field(default_factory=dict)


class R16GraphDiffRequest(BaseModel):
    previous_graph: dict[str, Any]
    current_graph: dict[str, Any]


class R16GraphExportRequest(BaseModel):
    graph: dict[str, Any]
    export_format: str = "json"


class R16GraphBackendPublishRequest(BaseModel):
    graph: dict[str, Any]
    dry_run: bool = True


class R16GenericResponse(BaseModel):
    result: dict[str, Any]
