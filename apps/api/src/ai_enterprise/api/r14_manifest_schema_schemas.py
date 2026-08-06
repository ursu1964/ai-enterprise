from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class R14ManifestSchemaContractResponse(BaseModel):
    schema_version: str
    intake_mode: str
    minimal_intake_supported: bool
    normalization_layer: str
    required_sections: list[str]
    forbidden_implementation_fields: list[str]
    lifecycle: list[str]
    expansion_outputs: list[str]
    contract_hash: str


class R14ManifestSchemaResponse(BaseModel):
    schema_document: dict[str, Any]
    schema_hash: str


class R14ManifestValidationRequest(BaseModel):
    manifest: dict[str, Any]


class R14ManifestValidationResponse(BaseModel):
    valid: bool
    finding_count: int
    findings: list[dict[str, Any]]
    manifest_hash: str
    schema_hash: str
    report_hash: str


class R14ManifestEvolutionValidationRequest(BaseModel):
    previous_manifest: dict[str, Any]
    current_manifest: dict[str, Any]


class R14ManifestEvolutionValidationResponse(BaseModel):
    valid: bool
    changed: bool
    previous_manifest_hash: str
    current_manifest_hash: str
    previous_manifest_version: str | None
    current_manifest_version: str | None
    findings: list[dict[str, Any]]
    report_hash: str
