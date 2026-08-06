from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class R13RepositoryLayoutContractResponse(BaseModel):
    directory_count: int
    directories: list[dict[str, Any]]
    readme_sentence: str
    contract_hash: str


class R13RepositoryLayoutResponse(BaseModel):
    item_count: int
    present_count: int
    missing_count: int
    items: list[dict[str, Any]]
    readme_sentence_present: bool
    layout_hash: str


class R13BootstrapSequenceContractResponse(BaseModel):
    step_count: int
    steps: list[dict[str, Any]]
    guarantees: list[str]
    contract_hash: str


class R13BootstrapSequenceValidationRequest(BaseModel):
    sequence: dict[str, Any]


class R13BootstrapSequenceValidationResponse(BaseModel):
    valid: bool
    finding_count: int
    findings: list[dict[str, Any]]
    sequence_fingerprint: str
    contract_hash: str
    report_hash: str


class R13RepositoryMissionContractResponse(BaseModel):
    input_artifact: str
    output_artifact: str
    ownership_boundary: str
    contract_hash: str


class R13BootstrapPipelineContractResponse(BaseModel):
    stage_count: int
    stages: list[dict[str, Any]]
    invariant: str
    contract_hash: str


class R13ComponentBoundaryContractResponse(BaseModel):
    component_count: int
    components: list[dict[str, Any]]
    invariant: str
    contract_hash: str


class R13DirectoryContentContractResponse(BaseModel):
    rule_count: int
    rules: list[dict[str, Any]]
    invariant: str
    contract_hash: str


class R13RepositoryPrinciplesContractResponse(BaseModel):
    principle_count: int
    principles: list[dict[str, Any]]
    contract_hash: str


class R13ExecutableSkeletonResponse(BaseModel):
    valid: bool
    layout_missing_count: int
    internal_home_missing_count: int
    internal_home_count: int
    missing_internal_homes: list[str]
    readme_sentence_present: bool
    component_count: int
    directory_rule_count: int
    principle_count: int
    bootstrap_step_count: int
    contract_hashes: dict[str, str]
    report_hash: str
