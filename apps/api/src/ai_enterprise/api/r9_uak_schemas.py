from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class R9KernelScopeRequest(BaseModel):
    scope_type: str = Field(pattern=r"^(platform|tenant|workspace|portfolio|project)$")
    scope_id: str = Field(min_length=1, max_length=120)
    organization_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None


class R9SubsystemRegistrationRequest(R9KernelScopeRequest):
    subsystem: str = Field(
        pattern=(
            r"^(manifest_manager|registry_manager|knowledge_manager|transformation_manager|"
            r"artifact_manager|runtime_manager|governance_manager|ai_manager|plugin_manager|"
            r"security_manager|deployment_manager|monitoring_manager|kernel_core)$"
        )
    )
    implementation_ref: str = Field(min_length=1, max_length=240)
    capabilities: list[str]
    dependencies: list[str] = Field(default_factory=list)


class R9KernelEventRequest(R9KernelScopeRequest):
    event_type: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    source_subsystem: str
    target_subsystem: str
    object_identity: str = Field(min_length=1, max_length=240)
    payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    causation_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class R9LifecycleSnapshotRequest(R9KernelScopeRequest):
    object_identity: str = Field(min_length=1, max_length=240)
    state: str = Field(
        pattern=(
            r"^(created|validated|normalized|transformed|generated|verified|approved|"
            r"deployed|running|observed|evolving)$"
        )
    )
    triggering_event_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class R9KernelTransactionRequest(R9KernelScopeRequest):
    operation_type: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    object_identity: str = Field(min_length=1, max_length=240)
    steps: list[str]
    committed_hashes: list[str] = Field(default_factory=list)
    rollback_steps: list[str] = Field(default_factory=list)
    rolled_back_hashes: list[str] = Field(default_factory=list)


class R9PlatformCheckpointRequest(R9KernelScopeRequest):
    checkpoint_kind: str = Field(pattern=r"^(startup|shutdown)$")
    completed_steps: list[str]


class R9PluginRegistrationRequest(R9KernelScopeRequest):
    plugin_key: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,159}$")
    category: str = Field(
        pattern=(
            r"^(generator|template|ai_provider|deployment_provider|integration|"
            r"compliance_pack|runtime_module)$"
        )
    )
    version: str = Field(min_length=1, max_length=80)
    capability_refs: list[str]
    extension_points: list[str]
    signed_artifact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class R9AiSessionBoundaryRequest(R9KernelScopeRequest):
    model_ref: str = Field(min_length=1, max_length=160)
    approved_context_refs: list[str]
    approved_registry_refs: list[str]
    approved_object_refs: list[str] = Field(default_factory=list)
    approved_template_refs: list[str] = Field(default_factory=list)
    approved_permission_refs: list[str]


class R9WorkspaceHierarchyRequest(R9KernelScopeRequest):
    tenant_ref: str = Field(min_length=1, max_length=160)
    workspace_ref: str = Field(min_length=1, max_length=160)
    portfolio_ref: str = Field(min_length=1, max_length=160)
    project_ref: str = Field(min_length=1, max_length=160)
    manifest_ref: str = Field(min_length=1, max_length=160)
    reusable_knowledge_refs: list[str] = Field(default_factory=list)


class R9SchedulePlanRequest(R9KernelScopeRequest):
    work_type: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    object_identity: str = Field(min_length=1, max_length=240)
    dependencies: list[str] = Field(default_factory=list)
    unsatisfied_dependencies: list[str] = Field(default_factory=list)
    resource_claims: dict[str, float]


class R9ResourceAllocationRequest(R9KernelScopeRequest):
    schedule_ref: str = Field(min_length=1, max_length=120)
    requested_resources: dict[str, float]
    allocated_resources: dict[str, float]


class R9SdkContractRequest(R9KernelScopeRequest):
    language: str = Field(pattern=r"^(csharp|java|typescript|python|go|rust)$")
    contract_version: str = Field(min_length=1, max_length=80)
    api_surfaces: list[str]
    canonical_contract_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    package_ref: str = Field(min_length=1, max_length=240)


class R9RegistrySnapshotRequest(R9KernelScopeRequest):
    updl_registry_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    object_registry_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    rule_registry_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    generator_registry_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    template_registry_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_registry_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class R9SecurityEnvelopeRequest(R9KernelScopeRequest):
    actor_identity_ref: str = Field(min_length=1, max_length=200)
    authorization_policy_refs: list[str]
    certificate_refs: list[str] = Field(default_factory=list)
    secret_refs: list[str] = Field(default_factory=list)


class R9DeploymentCoordinationRequest(R9KernelScopeRequest):
    environment: str = Field(
        pattern=r"^(development|testing|staging|production|hybrid_cloud|edge|on_premises)$"
    )
    manifest_ref: str = Field(min_length=1, max_length=200)
    deployment_provider_ref: str = Field(min_length=1, max_length=200)
    runtime_ref: str = Field(min_length=1, max_length=200)
    deployment_hashes: list[str]


class R9MonitoringAggregateRequest(R9KernelScopeRequest):
    metrics_by_domain: dict[str, float]
    source_record_hashes: list[str]


class R9KernelRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scope_type: str
    scope_id: str
    organization_id: uuid.UUID | None
    project_id: uuid.UUID | None
    record_type: str
    record_id: str
    status: str
    object_identity: str | None
    parent_record_hash: str | None
    record_document: dict[str, Any]
    record_hash: str


class R9KernelDashboardResponse(BaseModel):
    scope_type: str
    scope_id: str
    subsystem_count: int
    event_count: int
    latest_lifecycle_state: str | None
    committed_transaction_count: int
    rolled_back_transaction_count: int
    ready_checkpoint_count: int
    blocked_checkpoint_count: int
    plugin_count: int
    ai_session_boundary_count: int
    workspace_hierarchy_count: int
    dispatchable_schedule_count: int
    blocked_schedule_count: int
    allocated_resource_count: int
    insufficient_resource_count: int
    sdk_contract_count: int
    registry_snapshot_count: int
    security_envelope_count: int
    deployment_coordination_count: int
    monitoring_aggregate_count: int


class R9KernelReplayResponse(BaseModel):
    events: list[dict[str, Any]]
    replay_hash: str


class R9ScheduleDispatchResponse(BaseModel):
    dispatch_count: int
    events: list[R9KernelRecordResponse]


class R9SdkPackageMaterializationResponse(BaseModel):
    package_root: str
    package_ref: str
    language: str
    contract_hash: str
    package_hash: str
    files: list[str]


class R9OperationalBackendCheckResponse(BaseModel):
    name: str
    configured: bool
    ready: bool
    detail: str
    required: list[str] = Field(default_factory=list)


class R9OperationalReadinessResponse(BaseModel):
    event_bus_backend: str
    event_bus_ready: bool
    worker_fleet_ready: bool
    sdk_registry_backend: str
    sdk_registry_ready: bool
    ready: bool
    checks: list[R9OperationalBackendCheckResponse]


class R9SdkRegistryPublicationRequest(BaseModel):
    dry_run: bool = True


class R9SdkRegistryPublicationResponse(BaseModel):
    backend: str
    registry_ref: str
    package_root: str
    package_hash: str
    publication_ref: str
    ready: bool
    published: bool
    command: list[str] = Field(default_factory=list)
    detail: str
