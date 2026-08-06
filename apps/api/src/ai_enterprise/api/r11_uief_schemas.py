from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class R11IntegrationObjectRequest(BaseModel):
    manifest_ref: str
    name: str
    domain: str
    source_ref: str
    destination_ref: str
    purpose: str
    protocol: str
    contract_ref: str
    authentication_ref: str
    authorization_ref: str
    mapping_ref: str
    trigger: str
    frequency: str
    error_strategy_ref: str
    retry_policy_ref: str
    owner_ref: str
    monitoring_ref: str
    compliance_classification: str
    lifecycle_state: str = "proposed"
    approved_for_activation: bool = False


class R11ConnectorRegistrationRequest(BaseModel):
    provider: str
    supported_system: str
    version: str
    protocols: list[str]
    authentication_methods: list[str]
    operations: list[str]
    rate_limits: dict[str, float] = Field(default_factory=dict)
    data_classifications: list[str]
    certification_level: str
    compatibility_refs: list[str] = Field(default_factory=list)
    owner_ref: str
    lifecycle_status: str = "registered"


class R11ContractRegistrationRequest(BaseModel):
    manifest_ref: str
    contract_type: str
    contract_version: str
    operations: list[str]
    schema_refs: list[str]
    error_refs: list[str]
    security_requirement_refs: list[str]
    slo_refs: list[str]
    compatibility_rules: list[str]


class R11DataMappingRequest(BaseModel):
    integration_ref: str
    canonical_model_ref: str
    field_mappings: list[dict[str, str]]
    transformation_rules: list[str]
    test_refs: list[str]
    version: str


class R11EventDefinitionRequest(BaseModel):
    event_name: str
    producer_ref: str
    consumer_refs: list[str]
    schema_ref: str
    version: str
    partition_key: str
    delivery_semantics: str
    retention: str
    sensitivity: str
    retry_policy_ref: str
    dead_letter_strategy_ref: str


class R11RetryPolicyRequest(BaseModel):
    maximum_attempts: int
    delay_seconds: float
    retryable_errors: list[str]
    timeout_seconds: float
    escalation_ref: str
    dead_letter_destination: str


class R11SecurityPolicyRequest(BaseModel):
    identity_strength: str
    credential_ref: str
    transport_encryption: str
    authorization_scope_refs: list[str]
    data_protection_rules: list[str]
    residency_rules: list[str]
    logging_safety_rules: list[str]


class R11DigitalTwinRequest(BaseModel):
    integration_ref: str
    deployed_connector_ref: str
    active_version: str
    endpoint_ref: str
    dependency_refs: list[str]
    health: str
    performance_metrics: dict[str, float]
    data_flow_refs: list[str]
    contract_status: str
    security_status: str


class R11MarketplaceAssetRequest(BaseModel):
    asset_type: str
    creator_ref: str
    publisher_ref: str
    version: str
    source_ref: str
    dependency_refs: list[str] = Field(default_factory=list)
    license_ref: str
    signature_ref: str
    certification_level: str
    compatibility_refs: list[str] = Field(default_factory=list)


class R11ProviderAbstractionRequest(BaseModel):
    capability_ref: str
    logical_provider_type: str
    primary_provider_ref: str
    backup_provider_refs: list[str] = Field(default_factory=list)
    regional_provider_refs: list[str] = Field(default_factory=list)
    selection_policy_ref: str


class R11AiIntegrationBoundaryRequest(BaseModel):
    provider_ref: str
    model_ref: str
    region: str
    approved_data_classes: list[str]
    context_limit_ref: str
    retention_policy_ref: str
    output_constraint_refs: list[str]
    fallback_model_ref: str
    cost_control_ref: str
    audit_requirement_refs: list[str]


class R11RecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    record_type: str
    record_id: str
    integration_ref: str | None
    lifecycle_state: str | None
    health_status: str | None
    record_document: dict[str, Any]
    record_hash: str


class R11IntegrationDashboardResponse(BaseModel):
    project_id: uuid.UUID
    integration_count: int
    connector_count: int
    contract_count: int
    mapping_count: int
    event_count: int
    retry_policy_count: int
    security_policy_count: int
    digital_twin_count: int
    active_integration_count: int
    unhealthy_twin_count: int
    marketplace_asset_count: int
    provider_abstraction_count: int
    ai_boundary_count: int


class R11RuntimeCompatibilityResponse(BaseModel):
    compatible: bool
    integration_count: int
    findings: list[dict[str, Any]]
    report_hash: str


class R11GenerationPlanResponse(BaseModel):
    integration_count: int
    artifact_plans: list[dict[str, Any]]
    plan_hash: str


class R11TestPlanResponse(BaseModel):
    integration_count: int
    test_plans: list[dict[str, Any]]
    certification_ready: bool
    report_hash: str


class R11ReconciliationResponse(BaseModel):
    difference_count: int
    differences: list[dict[str, Any]]
    report_hash: str


class R11ObservabilitySnapshotResponse(BaseModel):
    integration_count: int
    healthy_count: int
    degraded_count: int
    unavailable_count: int
    disabled_count: int
    unknown_count: int
    metrics: dict[str, float]
    snapshot_hash: str


class R11TopologyMapResponse(BaseModel):
    node_count: int
    edge_count: int
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    topology_hash: str


class R11DocumentationBundleResponse(BaseModel):
    document_count: int
    documents: list[dict[str, Any]]
    bundle_hash: str


class R11SandboxPlanResponse(BaseModel):
    integration_count: int
    sandbox_plans: list[dict[str, Any]]
    ready_for_isolated_testing: bool
    report_hash: str


class R11SecurityReadinessResponse(BaseModel):
    integration_count: int
    finding_count: int
    activation_allowed: bool
    findings: list[dict[str, Any]]
    report_hash: str


class R11ImpactAnalysisResponse(BaseModel):
    changed_ref: str | None
    impact_count: int
    impacts: list[dict[str, Any]]
    report_hash: str


class R11MigrationPlanResponse(BaseModel):
    migration_count: int
    migration_plans: list[dict[str, Any]]
    report_hash: str


class R11EcosystemReadinessResponse(BaseModel):
    connector_registry_ready: bool
    gateway_ready: bool
    marketplace_ready: bool
    partner_ready: bool
    data_governance_ready: bool
    production_ready: bool
    finding_count: int
    findings: list[dict[str, Any]]
    report_hash: str


class R11DeveloperSurfaceResponse(BaseModel):
    public_api_count: int
    cli_capabilities: list[str]
    commands: list[dict[str, Any]]
    sdk_surfaces: list[str]
    validation_tools: list[str]
    certification_pipeline: list[str]
    documentation_portals: list[str]
    ready_for_external_developers: bool
    report_hash: str


class R11DeploymentPreflightResponse(BaseModel):
    external_integration_mode: str
    endpoint_allowlist_ready: bool
    credential_refs_ready: bool
    partner_trust_ready: bool
    gateway_ready: bool
    secrets_manager_ready: bool
    production_operational: bool
    checks: list[dict[str, Any]]
    report_hash: str
