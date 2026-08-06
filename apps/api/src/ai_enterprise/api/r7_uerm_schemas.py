from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class R7RuntimeDeploymentRequest(BaseModel):
    service_identity: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,179}$")
    environment: str = Field(default="development", pattern=r"^[a-z][a-z0-9_.-]{1,79}$")
    manifest_version: str = Field(default="1.0", min_length=1, max_length=120)
    application_version: str = Field(default="1.0.0", min_length=1, max_length=120)
    template_version: str = Field(default="1.0", min_length=1, max_length=80)
    deployment_location: str = Field(default="unassigned", min_length=1, max_length=300)
    endpoint_urls: list[str] = Field(default_factory=list)
    dependency_service_ids: list[str] = Field(default_factory=list)


class R7RuntimeContextRequest(BaseModel):
    request_id: str = Field(pattern=r"^[a-zA-Z0-9._:-]{8,128}$")
    correlation_id: str = Field(pattern=r"^[a-zA-Z0-9._:-]{8,128}$")
    tenant: str = Field(min_length=1, max_length=120)
    user: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=120)
    permissions: list[str] = Field(default_factory=list)
    session_id: str | None = Field(default=None, max_length=160)
    locale: str = Field(default="en-US", min_length=2, max_length=20)
    time_zone: str = Field(default="UTC", min_length=1, max_length=80)
    manifest_version: str = Field(min_length=1, max_length=120)
    application_version: str = Field(min_length=1, max_length=120)


class R7HealthReportRequest(BaseModel):
    checks: dict[str, str]
    metrics: dict[str, float] = Field(default_factory=dict)


class R7RuntimeEventRequest(BaseModel):
    event_type: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,119}$")
    context: R7RuntimeContextRequest
    payload: dict[str, Any] = Field(default_factory=dict)
    manifest_rule_ref: str = Field(min_length=1, max_length=200)


class R7CompatibilityReportRequest(BaseModel):
    current_manifest_version: str = Field(min_length=1, max_length=120)
    current_application_version: str = Field(min_length=1, max_length=120)


class R7WorkflowStartRequest(BaseModel):
    workflow_key: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,179}$")
    initial_state: str = Field(min_length=1, max_length=120)
    allowed_transitions: dict[str, list[str]]
    responsible_actor: str = Field(min_length=1, max_length=200)
    context: R7RuntimeContextRequest
    pending_actions: list[str] = Field(default_factory=list)


class R7WorkflowTransitionRequest(BaseModel):
    next_state: str = Field(min_length=1, max_length=120)
    actor: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=500)
    pending_actions: list[str] = Field(default_factory=list)


class R7RuntimeErrorRequest(BaseModel):
    severity: str = Field(pattern=r"^(information|warning|error|critical)$")
    category: str = Field(
        pattern=r"^(authorization|validation|business_rule|workflow|integration|system)$"
    )
    source: str = Field(min_length=1, max_length=200)
    context: R7RuntimeContextRequest
    message: str = Field(min_length=1, max_length=500)
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_.-]{2,119}$")
    recovery_guidance: str = Field(min_length=1, max_length=500)


class R7RecoveryActionRequest(BaseModel):
    strategy: str = Field(
        pattern=r"^(retry|rollback|compensation|timeout|circuit_breaker|escalation)$"
    )
    status: str = Field(default="planned", pattern=r"^(planned|executed|escalated)$")
    policy_document: dict[str, Any] = Field(default_factory=dict)


class R7DigitalTwinSnapshotRequest(BaseModel):
    health_status: str = Field(pattern=r"^(healthy|degraded|unhealthy)$")
    metrics: dict[str, float] = Field(default_factory=dict)
    configuration: dict[str, Any] = Field(default_factory=dict)
    active_workflows: list[str] = Field(default_factory=list)
    event_flows: list[str] = Field(default_factory=list)


class R7RuntimeProviderRequest(BaseModel):
    kind: str = Field(
        pattern=r"^(event_bus|deployment_runtime|policy_engine|ai_service|plugin_runtime)$"
    )
    name: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,119}$")
    version: str = Field(min_length=1, max_length=80)
    status: str = Field(
        default="registered", pattern=r"^(registered|available|unavailable)$"
    )
    capabilities: list[str] = Field(default_factory=list)
    endpoint_ref: str | None = Field(default=None, max_length=300)
    configuration: dict[str, Any] = Field(default_factory=dict)


class R7PolicyEvaluationRequest(BaseModel):
    context: R7RuntimeContextRequest
    action: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    resource: str = Field(min_length=1, max_length=200)
    provider_id: uuid.UUID | None = None
    policy_refs: list[str] = Field(default_factory=list)


class R7EventDispatchRequest(BaseModel):
    provider_id: uuid.UUID
    subscriber_refs: list[str] = Field(default_factory=list)


class R7DeploymentRuntimeSyncRequest(BaseModel):
    provider_id: uuid.UUID


class R7RuntimeAiRequest(BaseModel):
    provider_id: uuid.UUID
    context: R7RuntimeContextRequest
    capability: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    prompt: str = Field(min_length=1, max_length=1200)
    action: str = Field(default="runtime.ai.invoke", pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    resource: str = Field(default="runtime-ai-service", min_length=1, max_length=200)
    policy_refs: list[str] = Field(default_factory=list)


class R7PluginBindingRequest(BaseModel):
    provider_id: uuid.UUID
    plugin_name: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,119}$")
    plugin_version: str = Field(min_length=1, max_length=80)
    requested_capabilities: list[str] = Field(default_factory=list)


class R7RuntimeConfigurationRequest(BaseModel):
    configuration: dict[str, Any] = Field(default_factory=dict)
    feature_flags: dict[str, bool] = Field(default_factory=dict)


class R7RuntimeAuditRecordRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=200)
    action: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    affected_object: str = Field(min_length=1, max_length=200)
    correlation_id: str = Field(pattern=r"^[a-zA-Z0-9._:-]{8,128}$")
    manifest_rule_ref: str = Field(min_length=1, max_length=200)
    previous_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None


class R7RuntimeTelemetryBatchRequest(BaseModel):
    metrics: dict[str, float] = Field(default_factory=dict)
    trace_ids: list[str] = Field(default_factory=list)
    log_signatures: list[str] = Field(default_factory=list)
    performance_indicators: dict[str, float] = Field(default_factory=dict)


class R7RuntimeGovernanceTraceRequest(BaseModel):
    runtime_action_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    business_rule_ref: str = Field(min_length=1, max_length=200)
    registry_rule_ref: str = Field(min_length=1, max_length=200)
    manifest_object_ref: str = Field(min_length=1, max_length=200)
    requirement_ref: str = Field(min_length=1, max_length=200)


class R7RuntimeSynchronizationRequest(BaseModel):
    current_manifest_version: str = Field(min_length=1, max_length=120)
    current_application_version: str = Field(min_length=1, max_length=120)
    observed_runtime: dict[str, Any] = Field(default_factory=dict)


class R7RuntimeDeploymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    r6_generation_build_id: uuid.UUID
    deployment_id: str
    service_identity: str
    environment: str
    status: str
    manifest_version: str
    application_version: str
    template_version: str
    generator_pack_id: str
    generator_pack_version: str
    deployment_location: str
    endpoint_urls: list[str]
    dependency_service_ids: list[str]
    deployment_document: dict[str, Any]
    deployment_hash: str


class R7HealthReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    runtime_deployment_id: uuid.UUID
    status: str
    checks_document: dict[str, Any]
    metrics_document: dict[str, Any]
    report_document: dict[str, Any]
    report_hash: str


class R7RuntimeEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    runtime_deployment_id: uuid.UUID
    event_id: str
    event_type: str
    context_document: dict[str, Any]
    payload_document: dict[str, Any]
    manifest_rule_ref: str
    event_hash: str


class R7CompatibilityReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    runtime_deployment_id: uuid.UUID
    status: str
    report_document: dict[str, Any]
    report_hash: str


class R7WorkflowInstanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    runtime_deployment_id: uuid.UUID
    workflow_instance_id: str
    workflow_key: str
    previous_state: str | None
    current_state: str
    status: str
    context_document: dict[str, Any]
    workflow_document: dict[str, Any]
    instance_hash: str


class R7RuntimeErrorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    runtime_deployment_id: uuid.UUID
    error_id: str
    severity: str
    category: str
    source: str
    correlation_id: str
    code: str
    message: str
    recovery_guidance: str
    context_document: dict[str, Any]
    error_hash: str


class R7RecoveryActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    runtime_error_id: uuid.UUID
    recovery_id: str
    strategy: str
    status: str
    policy_document: dict[str, Any]
    action_hash: str


class R7DigitalTwinSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    runtime_deployment_id: uuid.UUID
    snapshot_id: str
    health_status: str
    topology_document: dict[str, Any]
    metrics_document: dict[str, Any]
    configuration_document: dict[str, Any]
    snapshot_document: dict[str, Any]
    snapshot_hash: str


class R7RuntimeProviderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    provider_id: str
    kind: str
    name: str
    version: str
    status: str
    capabilities: list[str]
    endpoint_ref: str | None
    configuration_document: dict[str, Any]
    provider_document: dict[str, Any]
    provider_hash: str


class R7PolicyEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    runtime_deployment_id: uuid.UUID
    runtime_provider_id: uuid.UUID | None
    evaluation_id: str
    action: str
    resource: str
    decision: str
    matched_policies: list[str]
    reason: str
    context_document: dict[str, Any]
    evaluation_document: dict[str, Any]
    evaluation_hash: str


class R7EventDispatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    runtime_event_id: uuid.UUID
    runtime_provider_id: uuid.UUID
    dispatch_id: str
    status: str
    subscriber_refs: list[str]
    dispatch_document: dict[str, Any]
    dispatch_hash: str


class R7DeploymentRuntimeSyncResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    runtime_deployment_id: uuid.UUID
    runtime_provider_id: uuid.UUID
    sync_id: str
    status: str
    runtime_document: dict[str, Any]
    sync_hash: str


class R7RuntimeAiRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    runtime_deployment_id: uuid.UUID
    runtime_provider_id: uuid.UUID
    policy_evaluation_id: uuid.UUID
    ai_request_id: str
    capability: str
    status: str
    prompt: str
    context_document: dict[str, Any]
    response_document: dict[str, Any]
    request_document: dict[str, Any]
    request_hash: str


class R7PluginBindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    runtime_deployment_id: uuid.UUID
    runtime_provider_id: uuid.UUID
    binding_id: str
    plugin_name: str
    plugin_version: str
    compatibility_status: str
    requested_capabilities: list[str]
    findings: list[str]
    binding_document: dict[str, Any]
    binding_hash: str


class R7RuntimeConfigurationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    runtime_deployment_id: uuid.UUID
    configuration_id: str
    manifest_version: str
    configuration_document: dict[str, Any]
    feature_flags: dict[str, bool]
    sensitive_keys: list[str]
    configuration_hash: str


class R7RuntimeAuditRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    runtime_deployment_id: uuid.UUID
    audit_id: str
    actor: str
    action: str
    affected_object: str
    previous_value_hash: str | None
    new_value_hash: str | None
    correlation_id: str
    manifest_rule_ref: str
    audit_document: dict[str, Any]
    audit_hash: str


class R7RuntimeTelemetryBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    runtime_deployment_id: uuid.UUID
    telemetry_id: str
    metrics_document: dict[str, Any]
    trace_ids: list[str]
    log_signatures: list[str]
    performance_indicators: dict[str, Any]
    telemetry_document: dict[str, Any]
    telemetry_hash: str


class R7RuntimeGovernanceTraceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    runtime_deployment_id: uuid.UUID
    governance_trace_id: str
    runtime_action_hash: str
    business_rule_ref: str
    registry_rule_ref: str
    manifest_object_ref: str
    requirement_ref: str
    trace_document: dict[str, Any]
    trace_hash: str


class R7RuntimeProviderReadinessResponse(BaseModel):
    provider_id: uuid.UUID
    provider_kind: str
    provider_name: str
    ready: bool
    checks: list[dict[str, Any]]
    required_configuration: list[str]


class R7RuntimeSynchronizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    runtime_deployment_id: uuid.UUID
    synchronization_id: str
    status: str
    findings: list[str]
    observed_runtime_document: dict[str, Any]
    report_document: dict[str, Any]
    report_hash: str


class R7RuntimeUpgradePlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    runtime_deployment_id: uuid.UUID
    synchronization_report_id: uuid.UUID
    upgrade_plan_id: str
    status: str
    blocked_by: list[str]
    steps_document: list[dict[str, Any]]
    plan_document: dict[str, Any]
    plan_hash: str
