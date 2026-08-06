from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_enterprise.domain.specification.kernel import specification_hash


class UakValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class UakSubsystem(StrEnum):
    KERNEL_CORE = "kernel_core"
    MANIFEST_MANAGER = "manifest_manager"
    REGISTRY_MANAGER = "registry_manager"
    KNOWLEDGE_MANAGER = "knowledge_manager"
    TRANSFORMATION_MANAGER = "transformation_manager"
    ARTIFACT_MANAGER = "artifact_manager"
    RUNTIME_MANAGER = "runtime_manager"
    GOVERNANCE_MANAGER = "governance_manager"
    AI_MANAGER = "ai_manager"
    PLUGIN_MANAGER = "plugin_manager"
    SECURITY_MANAGER = "security_manager"
    DEPLOYMENT_MANAGER = "deployment_manager"
    MONITORING_MANAGER = "monitoring_manager"


class UakLifecycleState(StrEnum):
    CREATED = "created"
    VALIDATED = "validated"
    NORMALIZED = "normalized"
    TRANSFORMED = "transformed"
    GENERATED = "generated"
    VERIFIED = "verified"
    APPROVED = "approved"
    DEPLOYED = "deployed"
    RUNNING = "running"
    OBSERVED = "observed"
    EVOLVING = "evolving"


class UakTransactionStatus(StrEnum):
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"


class UakCheckpointKind(StrEnum):
    STARTUP = "startup"
    SHUTDOWN = "shutdown"


class UakCheckpointStatus(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


class UakPluginCategory(StrEnum):
    GENERATOR = "generator"
    TEMPLATE = "template"
    AI_PROVIDER = "ai_provider"
    DEPLOYMENT_PROVIDER = "deployment_provider"
    INTEGRATION = "integration"
    COMPLIANCE_PACK = "compliance_pack"
    RUNTIME_MODULE = "runtime_module"


class UakScheduleStatus(StrEnum):
    DISPATCHABLE = "dispatchable"
    BLOCKED = "blocked"


class UakResourceAllocationStatus(StrEnum):
    ALLOCATED = "allocated"
    INSUFFICIENT = "insufficient"


class UakSdkLanguage(StrEnum):
    CSHARP = "csharp"
    JAVA = "java"
    TYPESCRIPT = "typescript"
    PYTHON = "python"
    GO = "go"
    RUST = "rust"


class UakDeploymentEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"
    HYBRID_CLOUD = "hybrid_cloud"
    EDGE = "edge"
    ON_PREMISES = "on_premises"


class UakSubsystemRegistration(UakValue):
    schema_version: Literal["uak-subsystem-registration-0.1"] = (
        "uak-subsystem-registration-0.1"
    )
    subsystem_id: str = Field(pattern=r"^UAK-SUB-[0-9]{4}$")
    subsystem: UakSubsystem
    implementation_ref: str = Field(min_length=1, max_length=240)
    capabilities: tuple[str, ...]
    dependencies: tuple[UakSubsystem, ...] = ()
    replaceable: bool = True
    direct_subsystem_communication_allowed: bool = False
    registration_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_registration(self) -> UakSubsystemRegistration:
        if not self.capabilities:
            raise ValueError("UAK subsystem registration requires capabilities")
        if tuple(sorted(set(self.capabilities))) != self.capabilities:
            raise ValueError("UAK subsystem capabilities must be unique and sorted")
        if tuple(sorted(set(self.dependencies), key=lambda item: item.value)) != self.dependencies:
            raise ValueError("UAK subsystem dependencies must be unique and sorted")
        if self.subsystem in self.dependencies:
            raise ValueError("UAK subsystem may not depend on itself")
        if not self.replaceable:
            raise ValueError("UAK kernel subsystems must remain replaceable")
        if self.direct_subsystem_communication_allowed:
            raise ValueError("UAK subsystems must communicate through the kernel")
        if self.registration_hash != _subsystem_registration_hash(self):
            raise ValueError("UAK subsystem registration hash does not match canonical content")
        return self


class UakKernelEvent(UakValue):
    schema_version: Literal["uak-kernel-event-0.1"] = "uak-kernel-event-0.1"
    event_id: str = Field(pattern=r"^UAK-EVT-[0-9]{4}$")
    event_type: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    source_subsystem: UakSubsystem
    target_subsystem: UakSubsystem
    object_identity: str = Field(min_length=1, max_length=240)
    payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    causation_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    routed_by_kernel: bool = True
    event_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_event(self) -> UakKernelEvent:
        if self.source_subsystem is self.target_subsystem:
            raise ValueError("UAK kernel event requires distinct source and target subsystems")
        if not self.routed_by_kernel:
            raise ValueError("UAK events must be routed by the kernel")
        if self.event_hash != _kernel_event_hash(self):
            raise ValueError("UAK kernel event hash does not match canonical content")
        return self


class UakLifecycleSnapshot(UakValue):
    schema_version: Literal["uak-lifecycle-snapshot-0.1"] = "uak-lifecycle-snapshot-0.1"
    lifecycle_id: str = Field(pattern=r"^UAK-LIFE-[0-9]{4}$")
    project_id: str = Field(min_length=1)
    object_identity: str = Field(min_length=1, max_length=240)
    state: UakLifecycleState
    triggering_event_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    lifecycle_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_lifecycle(self) -> UakLifecycleSnapshot:
        if self.lifecycle_hash != _lifecycle_snapshot_hash(self):
            raise ValueError("UAK lifecycle snapshot hash does not match canonical content")
        return self


class UakKernelTransaction(UakValue):
    schema_version: Literal["uak-kernel-transaction-0.1"] = "uak-kernel-transaction-0.1"
    transaction_id: str = Field(pattern=r"^UAK-TXN-[0-9]{4}$")
    operation_type: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    object_identity: str = Field(min_length=1, max_length=240)
    steps: tuple[str, ...]
    status: UakTransactionStatus
    committed_hashes: tuple[str, ...] = ()
    rollback_steps: tuple[str, ...] = ()
    rolled_back_hashes: tuple[str, ...] = ()
    transaction_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_transaction(self) -> UakKernelTransaction:
        if not self.steps:
            raise ValueError("UAK transaction requires steps")
        for values in (
            self.steps,
            self.committed_hashes,
            self.rollback_steps,
            self.rolled_back_hashes,
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError("UAK transaction values must be unique and sorted")
        if self.status is UakTransactionStatus.COMMITTED:
            if len(self.committed_hashes) != len(self.steps) or self.rolled_back_hashes:
                raise ValueError("UAK committed transaction must commit every step")
        if self.status is UakTransactionStatus.ROLLED_BACK:
            if not self.rollback_steps or not self.rolled_back_hashes or self.committed_hashes:
                raise ValueError("UAK rolled-back transaction must have rollback evidence only")
        if self.transaction_hash != _kernel_transaction_hash(self):
            raise ValueError("UAK kernel transaction hash does not match canonical content")
        return self


class UakPlatformCheckpoint(UakValue):
    schema_version: Literal["uak-platform-checkpoint-0.1"] = "uak-platform-checkpoint-0.1"
    checkpoint_id: str = Field(pattern=r"^UAK-CHK-[0-9]{4}$")
    checkpoint_kind: UakCheckpointKind
    required_steps: tuple[str, ...]
    completed_steps: tuple[str, ...]
    status: UakCheckpointStatus
    missing_steps: tuple[str, ...] = ()
    state_preserved: bool = True
    checkpoint_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_checkpoint(self) -> UakPlatformCheckpoint:
        if tuple(dict.fromkeys(self.required_steps)) != self.required_steps:
            raise ValueError("UAK checkpoint required steps must be unique")
        if tuple(dict.fromkeys(self.completed_steps)) != self.completed_steps:
            raise ValueError("UAK checkpoint completed steps must be unique")
        if not set(self.completed_steps).issubset(set(self.required_steps)):
            raise ValueError("UAK checkpoint completed steps must be required steps")
        expected_missing = tuple(
            step for step in self.required_steps if step not in self.completed_steps
        )
        if expected_missing != self.missing_steps:
            raise ValueError("UAK checkpoint missing steps must match required sequence")
        expected_status = (
            UakCheckpointStatus.READY if not self.missing_steps else UakCheckpointStatus.BLOCKED
        )
        if self.status is not expected_status:
            raise ValueError("UAK checkpoint status must match missing steps")
        if not self.state_preserved:
            raise ValueError("UAK checkpoint must preserve platform state")
        if self.checkpoint_hash != _platform_checkpoint_hash(self):
            raise ValueError("UAK platform checkpoint hash does not match canonical content")
        return self


class UakPluginRegistration(UakValue):
    schema_version: Literal["uak-plugin-registration-0.1"] = "uak-plugin-registration-0.1"
    plugin_id: str = Field(pattern=r"^UAK-PLG-[0-9]{4}$")
    plugin_key: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,159}$")
    category: UakPluginCategory
    version: str = Field(min_length=1, max_length=80)
    capability_refs: tuple[str, ...]
    extension_points: tuple[UakSubsystem, ...]
    signed_artifact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    modifies_kernel: bool = False
    registration_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_plugin(self) -> UakPluginRegistration:
        if tuple(sorted(set(self.capability_refs))) != self.capability_refs:
            raise ValueError("UAK plugin capabilities must be unique and sorted")
        if (
            tuple(sorted(set(self.extension_points), key=lambda item: item.value))
            != self.extension_points
        ):
            raise ValueError("UAK plugin extension points must be unique and sorted")
        if not self.capability_refs or not self.extension_points:
            raise ValueError("UAK plugin registration requires capabilities and extension points")
        if self.modifies_kernel:
            raise ValueError("UAK plugins may extend but never modify the kernel")
        if self.registration_hash != _plugin_registration_hash(self):
            raise ValueError("UAK plugin registration hash does not match canonical content")
        return self


class UakAiSessionBoundary(UakValue):
    schema_version: Literal["uak-ai-session-boundary-0.1"] = "uak-ai-session-boundary-0.1"
    ai_session_id: str = Field(pattern=r"^UAK-AI-[0-9]{4}$")
    model_ref: str = Field(min_length=1, max_length=160)
    approved_context_refs: tuple[str, ...]
    approved_registry_refs: tuple[str, ...]
    approved_object_refs: tuple[str, ...] = ()
    approved_template_refs: tuple[str, ...] = ()
    approved_permission_refs: tuple[str, ...]
    unrestricted_platform_access: bool = False
    boundary_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_ai_boundary(self) -> UakAiSessionBoundary:
        for values in (
            self.approved_context_refs,
            self.approved_registry_refs,
            self.approved_object_refs,
            self.approved_template_refs,
            self.approved_permission_refs,
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError("UAK AI session refs must be unique and sorted")
        if not self.approved_context_refs or not self.approved_registry_refs:
            raise ValueError("UAK AI session requires approved context and registry")
        if not self.approved_permission_refs:
            raise ValueError("UAK AI session requires approved permissions")
        if self.unrestricted_platform_access:
            raise ValueError("UAK AI sessions may not have unrestricted platform access")
        if self.boundary_hash != _ai_session_boundary_hash(self):
            raise ValueError("UAK AI session boundary hash does not match canonical content")
        return self


class UakWorkspaceHierarchy(UakValue):
    schema_version: Literal["uak-workspace-hierarchy-0.1"] = "uak-workspace-hierarchy-0.1"
    hierarchy_id: str = Field(pattern=r"^UAK-WS-[0-9]{4}$")
    tenant_ref: str = Field(min_length=1, max_length=160)
    workspace_ref: str = Field(min_length=1, max_length=160)
    portfolio_ref: str = Field(min_length=1, max_length=160)
    project_ref: str = Field(min_length=1, max_length=160)
    manifest_ref: str = Field(min_length=1, max_length=160)
    reusable_knowledge_refs: tuple[str, ...] = ()
    isolation_guaranteed: bool = True
    customer_data_shared: bool = False
    hierarchy_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_hierarchy(self) -> UakWorkspaceHierarchy:
        if tuple(sorted(set(self.reusable_knowledge_refs))) != self.reusable_knowledge_refs:
            raise ValueError("UAK reusable knowledge refs must be unique and sorted")
        if not self.isolation_guaranteed:
            raise ValueError("UAK multi-workspace isolation must be guaranteed")
        if self.customer_data_shared:
            raise ValueError("UAK multi-project intelligence may not share customer data")
        if self.hierarchy_hash != _workspace_hierarchy_hash(self):
            raise ValueError("UAK workspace hierarchy hash does not match canonical content")
        return self


class UakSchedulePlan(UakValue):
    schema_version: Literal["uak-schedule-plan-0.1"] = "uak-schedule-plan-0.1"
    schedule_id: str = Field(pattern=r"^UAK-SCH-[0-9]{4}$")
    work_type: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    object_identity: str = Field(min_length=1, max_length=240)
    dependencies: tuple[str, ...] = ()
    unsatisfied_dependencies: tuple[str, ...] = ()
    resource_claims: dict[str, float]
    status: UakScheduleStatus
    dependency_aware: bool = True
    schedule_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_schedule(self) -> UakSchedulePlan:
        if tuple(sorted(set(self.dependencies))) != self.dependencies:
            raise ValueError("UAK schedule dependencies must be unique and sorted")
        if tuple(sorted(set(self.unsatisfied_dependencies))) != self.unsatisfied_dependencies:
            raise ValueError("UAK unsatisfied dependencies must be unique and sorted")
        if not set(self.unsatisfied_dependencies).issubset(set(self.dependencies)):
            raise ValueError("UAK unsatisfied dependencies must be declared dependencies")
        if any(value <= 0 for value in self.resource_claims.values()):
            raise ValueError("UAK resource claims must be positive")
        expected_status = (
            UakScheduleStatus.BLOCKED
            if self.unsatisfied_dependencies
            else UakScheduleStatus.DISPATCHABLE
        )
        if self.status is not expected_status:
            raise ValueError("UAK schedule status must match dependency readiness")
        if not self.dependency_aware:
            raise ValueError("UAK scheduling must be dependency-aware")
        if self.schedule_hash != _schedule_plan_hash(self):
            raise ValueError("UAK schedule plan hash does not match canonical content")
        return self


class UakResourceAllocation(UakValue):
    schema_version: Literal["uak-resource-allocation-0.1"] = "uak-resource-allocation-0.1"
    allocation_id: str = Field(pattern=r"^UAK-RES-[0-9]{4}$")
    schedule_ref: str = Field(min_length=1, max_length=120)
    requested_resources: dict[str, float]
    allocated_resources: dict[str, float]
    status: UakResourceAllocationStatus
    dynamic_allocation: bool = True
    allocation_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_allocation(self) -> UakResourceAllocation:
        if any(value <= 0 for value in self.requested_resources.values()):
            raise ValueError("UAK requested resources must be positive")
        if any(value < 0 for value in self.allocated_resources.values()):
            raise ValueError("UAK allocated resources may not be negative")
        fully_allocated = all(
            self.allocated_resources.get(key, 0.0) >= value
            for key, value in self.requested_resources.items()
        )
        expected_status = (
            UakResourceAllocationStatus.ALLOCATED
            if fully_allocated
            else UakResourceAllocationStatus.INSUFFICIENT
        )
        if self.status is not expected_status:
            raise ValueError("UAK resource allocation status must match capacity")
        if not self.dynamic_allocation:
            raise ValueError("UAK resource allocation must be dynamic")
        if self.allocation_hash != _resource_allocation_hash(self):
            raise ValueError("UAK resource allocation hash does not match canonical content")
        return self


class UakSdkContract(UakValue):
    schema_version: Literal["uak-sdk-contract-0.1"] = "uak-sdk-contract-0.1"
    sdk_id: str = Field(pattern=r"^UAK-SDK-[0-9]{4}$")
    language: UakSdkLanguage
    contract_version: str = Field(min_length=1, max_length=80)
    api_surfaces: tuple[str, ...]
    canonical_contract_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    package_ref: str = Field(min_length=1, max_length=240)
    sdk_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_sdk(self) -> UakSdkContract:
        if tuple(sorted(set(self.api_surfaces))) != self.api_surfaces:
            raise ValueError("UAK SDK API surfaces must be unique and sorted")
        if not self.api_surfaces:
            raise ValueError("UAK SDK contract requires API surfaces")
        if self.sdk_hash != _sdk_contract_hash(self):
            raise ValueError("UAK SDK contract hash does not match canonical content")
        return self


class UakRegistrySnapshot(UakValue):
    schema_version: Literal["uak-registry-snapshot-0.1"] = "uak-registry-snapshot-0.1"
    registry_snapshot_id: str = Field(pattern=r"^UAK-REG-[0-9]{4}$")
    updl_registry_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    object_registry_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    rule_registry_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    generator_registry_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    template_registry_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_registry_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    execution_outside_registry_allowed: bool = False
    registry_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_registry(self) -> UakRegistrySnapshot:
        if self.execution_outside_registry_allowed:
            raise ValueError("UAK kernel may not execute outside the registry")
        if self.registry_hash != _registry_snapshot_hash(self):
            raise ValueError("UAK registry snapshot hash does not match canonical content")
        return self


class UakSecurityEnvelope(UakValue):
    schema_version: Literal["uak-security-envelope-0.1"] = "uak-security-envelope-0.1"
    security_id: str = Field(pattern=r"^UAK-SEC-[0-9]{4}$")
    actor_identity_ref: str = Field(min_length=1, max_length=200)
    authorization_policy_refs: tuple[str, ...]
    certificate_refs: tuple[str, ...] = ()
    secret_refs: tuple[str, ...] = ()
    encryption_required: bool = True
    secrets_redacted: bool = True
    policy_enforced: bool = True
    security_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_security(self) -> UakSecurityEnvelope:
        for values in (self.authorization_policy_refs, self.certificate_refs, self.secret_refs):
            if tuple(sorted(set(values))) != values:
                raise ValueError("UAK security refs must be unique and sorted")
        if not self.authorization_policy_refs:
            raise ValueError("UAK security envelope requires authorization policies")
        if not self.encryption_required or not self.secrets_redacted or not self.policy_enforced:
            raise ValueError("UAK security envelope must enforce encryption, redaction, and policy")
        if self.security_hash != _security_envelope_hash(self):
            raise ValueError("UAK security envelope hash does not match canonical content")
        return self


class UakDeploymentCoordination(UakValue):
    schema_version: Literal["uak-deployment-coordination-0.1"] = (
        "uak-deployment-coordination-0.1"
    )
    deployment_coordination_id: str = Field(pattern=r"^UAK-DEP-[0-9]{4}$")
    environment: UakDeploymentEnvironment
    manifest_ref: str = Field(min_length=1, max_length=200)
    deployment_provider_ref: str = Field(min_length=1, max_length=200)
    runtime_ref: str = Field(min_length=1, max_length=200)
    deployment_hashes: tuple[str, ...]
    manifest_aware: bool = True
    coordination_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_deployment(self) -> UakDeploymentCoordination:
        if tuple(sorted(set(self.deployment_hashes))) != self.deployment_hashes:
            raise ValueError("UAK deployment hashes must be unique and sorted")
        if not self.deployment_hashes:
            raise ValueError("UAK deployment coordination requires deployment hashes")
        if not self.manifest_aware:
            raise ValueError("UAK deployments must remain Manifest-aware")
        if self.coordination_hash != _deployment_coordination_hash(self):
            raise ValueError("UAK deployment coordination hash does not match canonical content")
        return self


class UakMonitoringAggregate(UakValue):
    schema_version: Literal["uak-monitoring-aggregate-0.1"] = "uak-monitoring-aggregate-0.1"
    monitoring_id: str = Field(pattern=r"^UAK-MON-[0-9]{4}$")
    metrics_by_domain: dict[str, float]
    source_record_hashes: tuple[str, ...]
    unified_operational_view: bool = True
    monitoring_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_monitoring(self) -> UakMonitoringAggregate:
        required_domains = {"runtime", "generation", "ai", "governance", "infrastructure"}
        if not required_domains.issubset(set(self.metrics_by_domain)):
            raise ValueError(
                "UAK monitoring requires runtime/generation/AI/governance/infrastructure"
            )
        if any(value < 0 or value > 100 for value in self.metrics_by_domain.values()):
            raise ValueError("UAK monitoring metrics must be between 0 and 100")
        if tuple(sorted(set(self.source_record_hashes))) != self.source_record_hashes:
            raise ValueError("UAK monitoring sources must be unique and sorted")
        if not self.source_record_hashes:
            raise ValueError("UAK monitoring requires source records")
        if not self.unified_operational_view:
            raise ValueError("UAK monitoring must provide a unified operational view")
        if self.monitoring_hash != _monitoring_aggregate_hash(self):
            raise ValueError("UAK monitoring aggregate hash does not match canonical content")
        return self


def subsystem_registration(
    *,
    index: int,
    subsystem: UakSubsystem,
    implementation_ref: str,
    capabilities: tuple[str, ...],
    dependencies: tuple[UakSubsystem, ...] = (),
) -> UakSubsystemRegistration:
    provisional = UakSubsystemRegistration.model_construct(
        schema_version="uak-subsystem-registration-0.1",
        subsystem_id=f"UAK-SUB-{index:04d}",
        subsystem=subsystem,
        implementation_ref=implementation_ref,
        capabilities=tuple(sorted(set(capabilities))),
        dependencies=tuple(sorted(set(dependencies), key=lambda item: item.value)),
        replaceable=True,
        direct_subsystem_communication_allowed=False,
        registration_hash="0" * 64,
    )
    return UakSubsystemRegistration(
        **provisional.model_dump(exclude={"registration_hash"}),
        registration_hash=_subsystem_registration_hash(provisional),
    )


def kernel_event(
    *,
    index: int,
    event_type: str,
    source_subsystem: UakSubsystem,
    target_subsystem: UakSubsystem,
    object_identity: str,
    payload_hash: str,
    causation_hash: str | None = None,
) -> UakKernelEvent:
    provisional = UakKernelEvent.model_construct(
        schema_version="uak-kernel-event-0.1",
        event_id=f"UAK-EVT-{index:04d}",
        event_type=event_type,
        source_subsystem=source_subsystem,
        target_subsystem=target_subsystem,
        object_identity=object_identity,
        payload_hash=payload_hash,
        causation_hash=causation_hash,
        routed_by_kernel=True,
        event_hash="0" * 64,
    )
    return UakKernelEvent(
        **provisional.model_dump(exclude={"event_hash"}),
        event_hash=_kernel_event_hash(provisional),
    )


def lifecycle_snapshot(
    *,
    index: int,
    project_id: str,
    object_identity: str,
    state: UakLifecycleState,
    triggering_event_hash: str,
) -> UakLifecycleSnapshot:
    provisional = UakLifecycleSnapshot.model_construct(
        schema_version="uak-lifecycle-snapshot-0.1",
        lifecycle_id=f"UAK-LIFE-{index:04d}",
        project_id=project_id,
        object_identity=object_identity,
        state=state,
        triggering_event_hash=triggering_event_hash,
        lifecycle_hash="0" * 64,
    )
    return UakLifecycleSnapshot(
        **provisional.model_dump(exclude={"lifecycle_hash"}),
        lifecycle_hash=_lifecycle_snapshot_hash(provisional),
    )


def kernel_transaction(
    *,
    index: int,
    operation_type: str,
    object_identity: str,
    steps: tuple[str, ...],
    committed_hashes: tuple[str, ...] = (),
    rollback_steps: tuple[str, ...] = (),
    rolled_back_hashes: tuple[str, ...] = (),
) -> UakKernelTransaction:
    normalized_committed = tuple(sorted(set(committed_hashes)))
    normalized_rolled_back = tuple(sorted(set(rolled_back_hashes)))
    status = (
        UakTransactionStatus.COMMITTED
        if len(normalized_committed) == len(set(steps)) and not normalized_rolled_back
        else UakTransactionStatus.ROLLED_BACK
    )
    provisional = UakKernelTransaction.model_construct(
        schema_version="uak-kernel-transaction-0.1",
        transaction_id=f"UAK-TXN-{index:04d}",
        operation_type=operation_type,
        object_identity=object_identity,
        steps=tuple(sorted(set(steps))),
        status=status,
        committed_hashes=normalized_committed,
        rollback_steps=tuple(sorted(set(rollback_steps))),
        rolled_back_hashes=normalized_rolled_back,
        transaction_hash="0" * 64,
    )
    return UakKernelTransaction(
        **provisional.model_dump(exclude={"transaction_hash"}),
        transaction_hash=_kernel_transaction_hash(provisional),
    )


def platform_checkpoint(
    *,
    index: int,
    checkpoint_kind: UakCheckpointKind,
    completed_steps: tuple[str, ...],
) -> UakPlatformCheckpoint:
    required_steps = _required_checkpoint_steps(checkpoint_kind)
    missing_steps = tuple(step for step in required_steps if step not in set(completed_steps))
    provisional = UakPlatformCheckpoint.model_construct(
        schema_version="uak-platform-checkpoint-0.1",
        checkpoint_id=f"UAK-CHK-{index:04d}",
        checkpoint_kind=checkpoint_kind,
        required_steps=required_steps,
        completed_steps=tuple(step for step in required_steps if step in set(completed_steps)),
        status=UakCheckpointStatus.READY if not missing_steps else UakCheckpointStatus.BLOCKED,
        missing_steps=missing_steps,
        state_preserved=True,
        checkpoint_hash="0" * 64,
    )
    return UakPlatformCheckpoint(
        **provisional.model_dump(exclude={"checkpoint_hash"}),
        checkpoint_hash=_platform_checkpoint_hash(provisional),
    )


def plugin_registration(
    *,
    index: int,
    plugin_key: str,
    category: UakPluginCategory,
    version: str,
    capability_refs: tuple[str, ...],
    extension_points: tuple[UakSubsystem, ...],
    signed_artifact_hash: str,
) -> UakPluginRegistration:
    provisional = UakPluginRegistration.model_construct(
        schema_version="uak-plugin-registration-0.1",
        plugin_id=f"UAK-PLG-{index:04d}",
        plugin_key=plugin_key,
        category=category,
        version=version,
        capability_refs=tuple(sorted(set(capability_refs))),
        extension_points=tuple(sorted(set(extension_points), key=lambda item: item.value)),
        signed_artifact_hash=signed_artifact_hash,
        modifies_kernel=False,
        registration_hash="0" * 64,
    )
    return UakPluginRegistration(
        **provisional.model_dump(exclude={"registration_hash"}),
        registration_hash=_plugin_registration_hash(provisional),
    )


def ai_session_boundary(
    *,
    index: int,
    model_ref: str,
    approved_context_refs: tuple[str, ...],
    approved_registry_refs: tuple[str, ...],
    approved_permission_refs: tuple[str, ...],
    approved_object_refs: tuple[str, ...] = (),
    approved_template_refs: tuple[str, ...] = (),
) -> UakAiSessionBoundary:
    provisional = UakAiSessionBoundary.model_construct(
        schema_version="uak-ai-session-boundary-0.1",
        ai_session_id=f"UAK-AI-{index:04d}",
        model_ref=model_ref,
        approved_context_refs=tuple(sorted(set(approved_context_refs))),
        approved_registry_refs=tuple(sorted(set(approved_registry_refs))),
        approved_object_refs=tuple(sorted(set(approved_object_refs))),
        approved_template_refs=tuple(sorted(set(approved_template_refs))),
        approved_permission_refs=tuple(sorted(set(approved_permission_refs))),
        unrestricted_platform_access=False,
        boundary_hash="0" * 64,
    )
    return UakAiSessionBoundary(
        **provisional.model_dump(exclude={"boundary_hash"}),
        boundary_hash=_ai_session_boundary_hash(provisional),
    )


def workspace_hierarchy(
    *,
    index: int,
    tenant_ref: str,
    workspace_ref: str,
    portfolio_ref: str,
    project_ref: str,
    manifest_ref: str,
    reusable_knowledge_refs: tuple[str, ...] = (),
) -> UakWorkspaceHierarchy:
    provisional = UakWorkspaceHierarchy.model_construct(
        schema_version="uak-workspace-hierarchy-0.1",
        hierarchy_id=f"UAK-WS-{index:04d}",
        tenant_ref=tenant_ref,
        workspace_ref=workspace_ref,
        portfolio_ref=portfolio_ref,
        project_ref=project_ref,
        manifest_ref=manifest_ref,
        reusable_knowledge_refs=tuple(sorted(set(reusable_knowledge_refs))),
        isolation_guaranteed=True,
        customer_data_shared=False,
        hierarchy_hash="0" * 64,
    )
    return UakWorkspaceHierarchy(
        **provisional.model_dump(exclude={"hierarchy_hash"}),
        hierarchy_hash=_workspace_hierarchy_hash(provisional),
    )


def schedule_plan(
    *,
    index: int,
    work_type: str,
    object_identity: str,
    resource_claims: dict[str, float],
    dependencies: tuple[str, ...] = (),
    unsatisfied_dependencies: tuple[str, ...] = (),
) -> UakSchedulePlan:
    provisional = UakSchedulePlan.model_construct(
        schema_version="uak-schedule-plan-0.1",
        schedule_id=f"UAK-SCH-{index:04d}",
        work_type=work_type,
        object_identity=object_identity,
        dependencies=tuple(sorted(set(dependencies))),
        unsatisfied_dependencies=tuple(sorted(set(unsatisfied_dependencies))),
        resource_claims=dict(sorted(resource_claims.items())),
        status=UakScheduleStatus.BLOCKED
        if unsatisfied_dependencies
        else UakScheduleStatus.DISPATCHABLE,
        dependency_aware=True,
        schedule_hash="0" * 64,
    )
    return UakSchedulePlan(
        **provisional.model_dump(exclude={"schedule_hash"}),
        schedule_hash=_schedule_plan_hash(provisional),
    )


def resource_allocation(
    *,
    index: int,
    schedule_ref: str,
    requested_resources: dict[str, float],
    allocated_resources: dict[str, float],
) -> UakResourceAllocation:
    normalized_requested = dict(sorted(requested_resources.items()))
    normalized_allocated = dict(sorted(allocated_resources.items()))
    fully_allocated = all(
        normalized_allocated.get(key, 0.0) >= value
        for key, value in normalized_requested.items()
    )
    provisional = UakResourceAllocation.model_construct(
        schema_version="uak-resource-allocation-0.1",
        allocation_id=f"UAK-RES-{index:04d}",
        schedule_ref=schedule_ref,
        requested_resources=normalized_requested,
        allocated_resources=normalized_allocated,
        status=UakResourceAllocationStatus.ALLOCATED
        if fully_allocated
        else UakResourceAllocationStatus.INSUFFICIENT,
        dynamic_allocation=True,
        allocation_hash="0" * 64,
    )
    return UakResourceAllocation(
        **provisional.model_dump(exclude={"allocation_hash"}),
        allocation_hash=_resource_allocation_hash(provisional),
    )


def sdk_contract(
    *,
    index: int,
    language: UakSdkLanguage,
    contract_version: str,
    api_surfaces: tuple[str, ...],
    canonical_contract_hash: str,
    package_ref: str,
) -> UakSdkContract:
    provisional = UakSdkContract.model_construct(
        schema_version="uak-sdk-contract-0.1",
        sdk_id=f"UAK-SDK-{index:04d}",
        language=language,
        contract_version=contract_version,
        api_surfaces=tuple(sorted(set(api_surfaces))),
        canonical_contract_hash=canonical_contract_hash,
        package_ref=package_ref,
        sdk_hash="0" * 64,
    )
    return UakSdkContract(
        **provisional.model_dump(exclude={"sdk_hash"}),
        sdk_hash=_sdk_contract_hash(provisional),
    )


def registry_snapshot(
    *,
    index: int,
    updl_registry_hash: str,
    object_registry_hash: str,
    rule_registry_hash: str,
    generator_registry_hash: str,
    template_registry_hash: str,
    policy_registry_hash: str,
) -> UakRegistrySnapshot:
    provisional = UakRegistrySnapshot.model_construct(
        schema_version="uak-registry-snapshot-0.1",
        registry_snapshot_id=f"UAK-REG-{index:04d}",
        updl_registry_hash=updl_registry_hash,
        object_registry_hash=object_registry_hash,
        rule_registry_hash=rule_registry_hash,
        generator_registry_hash=generator_registry_hash,
        template_registry_hash=template_registry_hash,
        policy_registry_hash=policy_registry_hash,
        execution_outside_registry_allowed=False,
        registry_hash="0" * 64,
    )
    return UakRegistrySnapshot(
        **provisional.model_dump(exclude={"registry_hash"}),
        registry_hash=_registry_snapshot_hash(provisional),
    )


def security_envelope(
    *,
    index: int,
    actor_identity_ref: str,
    authorization_policy_refs: tuple[str, ...],
    certificate_refs: tuple[str, ...] = (),
    secret_refs: tuple[str, ...] = (),
) -> UakSecurityEnvelope:
    provisional = UakSecurityEnvelope.model_construct(
        schema_version="uak-security-envelope-0.1",
        security_id=f"UAK-SEC-{index:04d}",
        actor_identity_ref=actor_identity_ref,
        authorization_policy_refs=tuple(sorted(set(authorization_policy_refs))),
        certificate_refs=tuple(sorted(set(certificate_refs))),
        secret_refs=tuple(sorted(set(secret_refs))),
        encryption_required=True,
        secrets_redacted=True,
        policy_enforced=True,
        security_hash="0" * 64,
    )
    return UakSecurityEnvelope(
        **provisional.model_dump(exclude={"security_hash"}),
        security_hash=_security_envelope_hash(provisional),
    )


def deployment_coordination(
    *,
    index: int,
    environment: UakDeploymentEnvironment,
    manifest_ref: str,
    deployment_provider_ref: str,
    runtime_ref: str,
    deployment_hashes: tuple[str, ...],
) -> UakDeploymentCoordination:
    provisional = UakDeploymentCoordination.model_construct(
        schema_version="uak-deployment-coordination-0.1",
        deployment_coordination_id=f"UAK-DEP-{index:04d}",
        environment=environment,
        manifest_ref=manifest_ref,
        deployment_provider_ref=deployment_provider_ref,
        runtime_ref=runtime_ref,
        deployment_hashes=tuple(sorted(set(deployment_hashes))),
        manifest_aware=True,
        coordination_hash="0" * 64,
    )
    return UakDeploymentCoordination(
        **provisional.model_dump(exclude={"coordination_hash"}),
        coordination_hash=_deployment_coordination_hash(provisional),
    )


def monitoring_aggregate(
    *,
    index: int,
    metrics_by_domain: dict[str, float],
    source_record_hashes: tuple[str, ...],
) -> UakMonitoringAggregate:
    provisional = UakMonitoringAggregate.model_construct(
        schema_version="uak-monitoring-aggregate-0.1",
        monitoring_id=f"UAK-MON-{index:04d}",
        metrics_by_domain=dict(sorted(metrics_by_domain.items())),
        source_record_hashes=tuple(sorted(set(source_record_hashes))),
        unified_operational_view=True,
        monitoring_hash="0" * 64,
    )
    return UakMonitoringAggregate(
        **provisional.model_dump(exclude={"monitoring_hash"}),
        monitoring_hash=_monitoring_aggregate_hash(provisional),
    )


def _required_checkpoint_steps(kind: UakCheckpointKind) -> tuple[str, ...]:
    if kind is UakCheckpointKind.STARTUP:
        return (
            "load_registry",
            "load_policies",
            "load_templates",
            "load_plugins",
            "load_knowledge_graph",
            "initialize_ai_providers",
            "initialize_runtime",
            "accept_requests",
        )
    return (
        "complete_transactions",
        "persist_events",
        "preserve_state",
        "synchronize_runtime",
        "write_recovery_checkpoints",
    )


def _subsystem_registration_hash(value: UakSubsystemRegistration) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"registration_hash"}))


def _kernel_event_hash(value: UakKernelEvent) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"event_hash"}))


def _lifecycle_snapshot_hash(value: UakLifecycleSnapshot) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"lifecycle_hash"}))


def _kernel_transaction_hash(value: UakKernelTransaction) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"transaction_hash"}))


def _platform_checkpoint_hash(value: UakPlatformCheckpoint) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"checkpoint_hash"}))


def _plugin_registration_hash(value: UakPluginRegistration) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"registration_hash"}))


def _ai_session_boundary_hash(value: UakAiSessionBoundary) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"boundary_hash"}))


def _workspace_hierarchy_hash(value: UakWorkspaceHierarchy) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"hierarchy_hash"}))


def _schedule_plan_hash(value: UakSchedulePlan) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"schedule_hash"}))


def _resource_allocation_hash(value: UakResourceAllocation) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"allocation_hash"}))


def _sdk_contract_hash(value: UakSdkContract) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"sdk_hash"}))


def _registry_snapshot_hash(value: UakRegistrySnapshot) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"registry_hash"}))


def _security_envelope_hash(value: UakSecurityEnvelope) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"security_hash"}))


def _deployment_coordination_hash(value: UakDeploymentCoordination) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"coordination_hash"}))


def _monitoring_aggregate_hash(value: UakMonitoringAggregate) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"monitoring_hash"}))
