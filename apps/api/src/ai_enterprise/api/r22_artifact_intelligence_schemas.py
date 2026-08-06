from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class R22ArtifactContractResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_intelligence_version: str
    artifact_classes: list[str]
    lifecycle_states: list[str]
    validation_states: list[str]
    freshness_states: list[str]
    integrity_states: list[str]
    governance_states: list[str]
    trace_relationship_types: list[str]
    graph_node_types: list[str]
    graph_edge_types: list[str]
    principles: list[str]


class R22CreateRegistryRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: str = "default"
    persist: bool = True


class R22RegisterArtifactRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: str = "default"
    artifact_type: str
    artifact_class: str
    title: str
    content: dict[str, Any] | str
    media_type: str = "application/json"
    schema_id: str = "artifact.schema.json"
    schema_version: str = "1.0"
    provenance: dict[str, Any] | None = None
    manifest_traces: tuple[dict[str, str], ...] = ()
    work_package_ids: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    validations: tuple[dict[str, Any], ...] = ()
    approvals: tuple[dict[str, str], ...] = ()
    declared_checksum: str | None = None
    classification: str = "INTERNAL"
    retention_policy_id: str = "default-retention"
    persist: bool = True


class R22PromoteArtifactRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: str = "default"
    target_lifecycle: str
    persist: bool = True


class R22SupersedeArtifactRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: str = "default"
    replacement_version_id: str
    reason: str
    persist: bool = True


class R22ImpactAnalysisRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: str = "default"
    changed_object_id: str
    persist: bool = True


class R22GraphPathRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: str = "default"
    source_node_id: str
    target_node_id: str


class R22IngestR21ExecutionRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: str = "default"
    execution: dict[str, Any]
    persist: bool = True


class R22OperationalReadinessRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    production: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class R22RegistryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    registry: dict[str, Any]


class R22RegistrationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    accepted: bool
    artifact_id: str | None
    artifact_version_id: str | None
    diagnostics: list[dict[str, Any]]
    registry: dict[str, Any]


class R22ArtifactVersionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_version: dict[str, Any]


class R22ReportResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    report: dict[str, Any]


class R22ListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    records: list[dict[str, Any]] = Field(default_factory=list)
