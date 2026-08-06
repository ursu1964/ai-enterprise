from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class R19MemoryContractResponse(BaseModel):
    engine_version: str
    domains: list[str]
    retention_classes: list[str]
    principles: list[str]


class R19StoreMemoryRequest(BaseModel):
    project_id: str
    domain: str
    category: str
    author: str | None = None
    source: str
    summary: str
    related_objects: list[dict[str, Any]] = Field(default_factory=list)
    content: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    retention_class: str = "permanent"
    visibility: str = "internal"
    legal_hold: bool = False
    timestamp: str | None = None


class R19UpdateMemoryRequest(BaseModel):
    memory_id: str
    author: str | None = None
    summary: str
    content: dict[str, Any]
    tags: list[str] | None = None
    timestamp: str | None = None


class R19RelateMemoryRequest(BaseModel):
    source_memory_id: str
    target_type: str
    target_id: str
    relationship_type: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class R19QueryMemoryRequest(BaseModel):
    query: dict[str, Any]


class R19ContextRequestBody(BaseModel):
    request: dict[str, Any]


class R19IngestR17Request(BaseModel):
    project_id: str
    plan: dict[str, Any]
    author: str | None = None


class R19IngestR18Request(BaseModel):
    project_id: str
    result: dict[str, Any]
    author: str | None = None


class R19MemoryStoreResponse(BaseModel):
    store: dict[str, Any]


class R19MemoryQueryResponse(BaseModel):
    result: dict[str, Any]


class R19ContextResponse(BaseModel):
    context: dict[str, Any]


class R19MemoryHistoryResponse(BaseModel):
    records: list[dict[str, Any]]


class R19MemoryExportResponse(BaseModel):
    export: dict[str, Any]


class R19ValidationResponse(BaseModel):
    valid: bool
    diagnostics: list[dict[str, Any]]
    report_hash: str


class R19MemoryReadinessRequest(BaseModel):
    backend_config: dict[str, Any] | None = None


class R19MemoryReadinessResponse(BaseModel):
    readiness: dict[str, Any]


class R19SemanticIndexResponse(BaseModel):
    report: dict[str, Any]


class R19AuthorizationResponse(BaseModel):
    decision: dict[str, Any]
