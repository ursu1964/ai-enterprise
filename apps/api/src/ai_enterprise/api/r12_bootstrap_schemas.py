from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class R12ImplementationStatusResponse(BaseModel):
    phase_count: int
    operational_phase_count: int
    next_phase: str | None
    vertical_slice_ready: bool
    phases: list[dict[str, Any]]
    status_hash: str


class R12RepositoryLayoutResponse(BaseModel):
    item_count: int
    present_count: int
    missing_count: int
    items: list[dict[str, Any]]
    layout_hash: str


class R12BootstrapPlanResponse(BaseModel):
    command_count: int
    commands: list[dict[str, Any]]
    plan_hash: str


class R12BuildManifestContractResponse(BaseModel):
    requirement_count: int
    requirements: list[dict[str, Any]]
    contract_hash: str


class R12BuildManifestValidationRequest(BaseModel):
    manifest: dict[str, Any]


class R12BuildManifestValidationResponse(BaseModel):
    valid: bool
    finding_count: int
    findings: list[dict[str, Any]]
    required_contract_hash: str
    manifest_fingerprint: str
    report_hash: str


class R12ErrorContractResponse(BaseModel):
    field_count: int
    fields: list[dict[str, Any]]
    contract_hash: str


class R12ErrorContractValidationRequest(BaseModel):
    error: dict[str, Any]


class R12ErrorContractValidationResponse(BaseModel):
    valid: bool
    finding_count: int
    findings: list[dict[str, Any]]
    required_contract_hash: str
    error_fingerprint: str
    report_hash: str


class R12SharedContractCatalogResponse(BaseModel):
    contract_count: int
    contracts: list[dict[str, Any]]
    catalog_hash: str


class R12SharedContractValidationRequest(BaseModel):
    contract_type: str
    envelope: dict[str, Any]


class R12SharedContractValidationResponse(BaseModel):
    valid: bool
    contract_type: str
    finding_count: int
    findings: list[dict[str, Any]]
    required_contract_hash: str
    envelope_fingerprint: str
    report_hash: str


class R12PlatformEntityCatalogResponse(BaseModel):
    entity_count: int
    versioned_entity_count: int
    entities: list[dict[str, Any]]
    catalog_hash: str


class R12IdentityContractValidationRequest(BaseModel):
    entity: dict[str, Any]


class R12IdentityContractValidationResponse(BaseModel):
    valid: bool
    finding_count: int
    findings: list[dict[str, Any]]
    entity_fingerprint: str
    report_hash: str


class R12DeterministicFingerprintContractResponse(BaseModel):
    required_input_count: int
    required_inputs: list[str]
    contract_hash: str


class R12DeterministicFingerprintRequest(BaseModel):
    inputs: dict[str, Any]


class R12DeterministicFingerprintResponse(BaseModel):
    valid: bool
    finding_count: int
    findings: list[dict[str, Any]]
    deterministic_fingerprint: str
    contract_hash: str
    report_hash: str


class R12OperationalBaselineContractResponse(BaseModel):
    section_count: int
    sections: list[dict[str, Any]]
    contract_hash: str


class R12OperationalBaselineValidationRequest(BaseModel):
    evidence: dict[str, Any]


class R12OperationalBaselineValidationResponse(BaseModel):
    valid: bool
    finding_count: int
    findings: list[dict[str, Any]]
    evidence_fingerprint: str
    contract_hash: str
    report_hash: str


class R12VerificationStrategyContractResponse(BaseModel):
    section_count: int
    sections: list[dict[str, Any]]
    contract_hash: str


class R12VerificationStrategyValidationRequest(BaseModel):
    evidence: dict[str, Any]


class R12VerificationStrategyValidationResponse(BaseModel):
    valid: bool
    finding_count: int
    findings: list[dict[str, Any]]
    evidence_fingerprint: str
    contract_hash: str
    report_hash: str


class R12RoadmapGovernanceContractResponse(BaseModel):
    section_count: int
    sections: list[dict[str, Any]]
    contract_hash: str


class R12RoadmapGovernanceValidationRequest(BaseModel):
    evidence: dict[str, Any]


class R12RoadmapGovernanceValidationResponse(BaseModel):
    valid: bool
    finding_count: int
    findings: list[dict[str, Any]]
    evidence_fingerprint: str
    contract_hash: str
    report_hash: str


class R12DeliveryArchitectureContractResponse(BaseModel):
    section_count: int
    sections: list[dict[str, Any]]
    contract_hash: str


class R12DeliveryArchitectureValidationRequest(BaseModel):
    evidence: dict[str, Any]


class R12DeliveryArchitectureValidationResponse(BaseModel):
    valid: bool
    finding_count: int
    findings: list[dict[str, Any]]
    evidence_fingerprint: str
    contract_hash: str
    report_hash: str
