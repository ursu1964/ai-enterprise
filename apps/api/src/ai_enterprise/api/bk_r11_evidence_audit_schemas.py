from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class BKR11ContractResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str
    evidence_types: list[str]
    archive_backends: list[str]
    signature_providers: list[str]
    principles: list[str]


class BKR11CreateEvidenceArtifactRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str
    evidence_type: str
    source_system: str
    uri: str
    content_hash: str
    captured_by: dict[str, str]
    subjects: tuple[dict[str, str], ...]
    captured_at: str = "1970-01-01T00:00:00Z"
    classification: str = "internal"
    retention_class: str = "project-lifecycle"
    metadata: dict[str, Any] = {}


class BKR11AppendAuditRecordRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    existing_records: tuple[dict[str, Any], ...] = ()
    stream_id: str
    event_type: str
    actor: dict[str, str]
    subject: dict[str, str]
    evidence_ids: tuple[str, ...]
    payload: dict[str, Any]
    occurred_at: str = "1970-01-01T00:00:00Z"


class BKR11BuildPackageRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_package_id: str
    project_id: str
    baseline_refs: dict[str, str]
    artifacts: tuple[dict[str, Any], ...]
    audit_records: tuple[dict[str, Any], ...]
    required_evidence_by_obligation: dict[str, tuple[str, ...]]
    package_version: str = "evidence-audit-engine-1.0"
    persist: bool = False


class BKR11ArchiveReadinessRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    environment: str = "development"
    backend_config: dict[str, Any] = {}


class BKR11SignedExportRequest(BKR11BuildPackageRequest):
    model_config = ConfigDict(frozen=True)

    environment: str = "development"
    backend_config: dict[str, Any] = {}


class BKR11PublishArchiveRequest(BKR11SignedExportRequest):
    model_config = ConfigDict(frozen=True)

    sign_archive: bool = False
    persist_publication: bool = False


class BKR11SignPackageRequest(BKR11SignedExportRequest):
    model_config = ConfigDict(frozen=True)

    archive_hash: str


class BKR11VerifyPublicationRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    publication: dict[str, Any]
    backend_config: dict[str, Any] = {}
    persist_verification: bool = False


class BKR11RecordResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    record: dict[str, Any]


class BKR11ListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    records: list[dict[str, Any]]
