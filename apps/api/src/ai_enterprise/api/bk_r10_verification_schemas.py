from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class BKR10ContractResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: str
    campaign_states: list[str]
    verification_methods: list[str]
    test_types: list[str]
    final_obligation_states: list[str]
    principles: list[str]


class BKR10CreateHandoffRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    implementation_result_id: str
    implementation_slice_id: str
    repository_revision: str
    requirement_baseline_id: str
    architecture_baseline_id: str
    planning_baseline_id: str
    produced_by: dict[str, str]
    policy_refs: tuple[str, ...] = ()
    artifact_refs: tuple[str, ...] = ()


class BKR10CreateCampaignRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    organization_id: str
    handoff: dict[str, Any]
    owner: dict[str, str]
    obligations: tuple[dict[str, Any], ...]
    procedures: tuple[dict[str, Any], ...] = ()
    criticality: str = "MEDIUM"
    risk_classification: str = "standard"
    persist: bool = True


class BKR10EnvironmentRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    environment: dict[str, Any]
    actor: dict[str, str]
    persist: bool = True


class BKR10StartCampaignRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    actor: dict[str, str]
    persist: bool = True


class BKR10RecordResultRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    procedure_id: str
    environment_id: str
    executor: dict[str, str]
    obligation_results: tuple[dict[str, Any], ...]
    raw_evidence_references: tuple[str, ...]
    normalized_evidence_references: tuple[str, ...] = ()
    observed_outputs: dict[str, Any] | None = None
    defects_detected: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    persist: bool = True


class BKR10WaiverRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    obligation_id: str
    authority: dict[str, str]
    justification: str
    risk_acceptance: str
    scope: str
    expires_at: str
    compensating_controls: tuple[str, ...]
    persist: bool = True


class BKR10ActorRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    actor: dict[str, str]
    persist: bool = True


class BKR10VerdictRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    actor: dict[str, str]
    validation_status: str = "NOT_REQUIRED"
    persist: bool = True


class BKR10ExternalReadinessRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    environment: str = "development"
    required_backends: tuple[str, ...] | None = None
    backend_configs: tuple[dict[str, Any], ...] = ()


class BKR10ExternalExecutionRequestSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    environment: str = "development"
    backend_config: dict[str, Any]
    execution_request: dict[str, Any]


class BKR10CampaignResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    campaign: dict[str, Any]


class BKR10RecordResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    record: dict[str, Any]
