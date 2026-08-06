from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_enterprise.domain.specification.kernel import specification_hash


class UermValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class UermDeploymentStatus(StrEnum):
    REGISTERED = "registered"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    RETIRED = "retired"


class UermHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class UermCompatibilityStatus(StrEnum):
    COMPATIBLE = "compatible"
    OUTDATED = "outdated"
    INCOMPATIBLE = "incompatible"


class UermWorkflowStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class UermErrorSeverity(StrEnum):
    INFORMATION = "information"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class UermErrorCategory(StrEnum):
    AUTHORIZATION = "authorization"
    VALIDATION = "validation"
    BUSINESS_RULE = "business_rule"
    WORKFLOW = "workflow"
    INTEGRATION = "integration"
    SYSTEM = "system"


class UermRecoveryStrategy(StrEnum):
    RETRY = "retry"
    ROLLBACK = "rollback"
    COMPENSATION = "compensation"
    TIMEOUT = "timeout"
    CIRCUIT_BREAKER = "circuit_breaker"
    ESCALATION = "escalation"


class UermRecoveryStatus(StrEnum):
    PLANNED = "planned"
    EXECUTED = "executed"
    ESCALATED = "escalated"


class UermRuntimeProviderKind(StrEnum):
    EVENT_BUS = "event_bus"
    DEPLOYMENT_RUNTIME = "deployment_runtime"
    POLICY_ENGINE = "policy_engine"
    AI_SERVICE = "ai_service"
    PLUGIN_RUNTIME = "plugin_runtime"


class UermRuntimeProviderStatus(StrEnum):
    REGISTERED = "registered"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class UermPolicyDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class UermRuntimeDispatchStatus(StrEnum):
    ACCEPTED = "accepted"
    DELIVERED = "delivered"
    FAILED = "failed"


class UermRuntimeAiRequestStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class UermRuntimeUpgradeStatus(StrEnum):
    PLANNED = "planned"
    BLOCKED = "blocked"


class UermRuntimeProvider(UermValue):
    schema_version: Literal["uerm-runtime-provider-0.1"] = "uerm-runtime-provider-0.1"
    provider_id: str = Field(pattern=r"^UERM-PROV-[0-9]{4}$")
    project_id: str = Field(min_length=1)
    kind: UermRuntimeProviderKind
    name: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,119}$")
    version: str = Field(min_length=1, max_length=80)
    status: UermRuntimeProviderStatus
    capabilities: tuple[str, ...] = ()
    endpoint_ref: str | None = Field(default=None, max_length=300)
    configuration: dict[str, object] = {}
    provider_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_provider(self) -> UermRuntimeProvider:
        if tuple(sorted(set(self.capabilities))) != self.capabilities:
            raise ValueError("UERM runtime provider capabilities must be unique and sorted")
        if self.provider_hash != _runtime_provider_hash(self):
            raise ValueError("UERM runtime provider hash does not match canonical content")
        return self


class UermPolicyEvaluation(UermValue):
    schema_version: Literal["uerm-policy-evaluation-0.1"] = "uerm-policy-evaluation-0.1"
    evaluation_id: str = Field(pattern=r"^UERM-POL-[0-9]{4}$")
    deployment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    context_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    action: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    resource: str = Field(min_length=1, max_length=200)
    decision: UermPolicyDecision
    matched_policies: tuple[str, ...] = ()
    reason: str = Field(min_length=1, max_length=500)
    evaluation_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_evaluation(self) -> UermPolicyEvaluation:
        if tuple(sorted(set(self.matched_policies))) != self.matched_policies:
            raise ValueError("UERM matched policies must be unique and sorted")
        if self.evaluation_hash != _policy_evaluation_hash(self):
            raise ValueError("UERM policy evaluation hash does not match canonical content")
        return self


class UermEventDispatch(UermValue):
    schema_version: Literal["uerm-event-dispatch-0.1"] = "uerm-event-dispatch-0.1"
    dispatch_id: str = Field(pattern=r"^UERM-DISP-[0-9]{4}$")
    event_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: UermRuntimeDispatchStatus
    subscriber_refs: tuple[str, ...] = ()
    dispatch_document: dict[str, object]
    dispatch_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_dispatch(self) -> UermEventDispatch:
        if tuple(sorted(set(self.subscriber_refs))) != self.subscriber_refs:
            raise ValueError("UERM event subscribers must be unique and sorted")
        if self.dispatch_hash != _event_dispatch_hash(self):
            raise ValueError("UERM event dispatch hash does not match canonical content")
        return self


class UermDeploymentRuntimeSync(UermValue):
    schema_version: Literal["uerm-deployment-runtime-sync-0.1"] = (
        "uerm-deployment-runtime-sync-0.1"
    )
    sync_id: str = Field(pattern=r"^UERM-SYNC-[0-9]{4}$")
    deployment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: UermRuntimeDispatchStatus
    runtime_document: dict[str, object]
    sync_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_sync(self) -> UermDeploymentRuntimeSync:
        if self.sync_hash != _deployment_runtime_sync_hash(self):
            raise ValueError("UERM deployment runtime sync hash does not match canonical content")
        return self


class UermRuntimeAiRequest(UermValue):
    schema_version: Literal["uerm-runtime-ai-request-0.1"] = "uerm-runtime-ai-request-0.1"
    ai_request_id: str = Field(pattern=r"^UERM-AI-[0-9]{4}$")
    deployment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    context_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_evaluation_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    capability: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    prompt: str = Field(min_length=1, max_length=1200)
    status: UermRuntimeAiRequestStatus
    response_document: dict[str, object]
    request_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_ai_request(self) -> UermRuntimeAiRequest:
        if self.request_hash != _runtime_ai_request_hash(self):
            raise ValueError("UERM runtime AI request hash does not match canonical content")
        return self


class UermPluginBinding(UermValue):
    schema_version: Literal["uerm-plugin-binding-0.1"] = "uerm-plugin-binding-0.1"
    binding_id: str = Field(pattern=r"^UERM-PLUG-[0-9]{4}$")
    deployment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    plugin_name: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,119}$")
    plugin_version: str = Field(min_length=1, max_length=80)
    requested_capabilities: tuple[str, ...] = ()
    compatibility_status: UermCompatibilityStatus
    findings: tuple[str, ...] = ()
    binding_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_binding(self) -> UermPluginBinding:
        if tuple(sorted(set(self.requested_capabilities))) != self.requested_capabilities:
            raise ValueError("UERM plugin capabilities must be unique and sorted")
        if tuple(sorted(set(self.findings))) != self.findings:
            raise ValueError("UERM plugin findings must be unique and sorted")
        if self.binding_hash != _plugin_binding_hash(self):
            raise ValueError("UERM plugin binding hash does not match canonical content")
        return self


class UermRuntimeConfigurationSnapshot(UermValue):
    schema_version: Literal["uerm-runtime-configuration-0.1"] = (
        "uerm-runtime-configuration-0.1"
    )
    configuration_id: str = Field(pattern=r"^UERM-CFG-[0-9]{4}$")
    deployment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_version: str = Field(min_length=1, max_length=120)
    configuration_document: dict[str, object]
    feature_flags: dict[str, bool] = {}
    sensitive_keys: tuple[str, ...] = ()
    configuration_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_configuration(self) -> UermRuntimeConfigurationSnapshot:
        if tuple(sorted(set(self.sensitive_keys))) != self.sensitive_keys:
            raise ValueError("UERM sensitive configuration keys must be unique and sorted")
        if self.configuration_hash != _runtime_configuration_hash(self):
            raise ValueError("UERM runtime configuration hash does not match canonical content")
        return self


class UermRuntimeAuditRecord(UermValue):
    schema_version: Literal["uerm-runtime-audit-record-0.1"] = (
        "uerm-runtime-audit-record-0.1"
    )
    audit_id: str = Field(pattern=r"^UERM-AUD-[0-9]{4}$")
    deployment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    actor: str = Field(min_length=1, max_length=200)
    action: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    affected_object: str = Field(min_length=1, max_length=200)
    previous_value_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    new_value_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    correlation_id: str = Field(pattern=r"^[a-zA-Z0-9._:-]{8,128}$")
    manifest_rule_ref: str = Field(min_length=1, max_length=200)
    audit_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_audit(self) -> UermRuntimeAuditRecord:
        if self.audit_hash != _runtime_audit_record_hash(self):
            raise ValueError("UERM runtime audit hash does not match canonical content")
        return self


class UermRuntimeTelemetryBatch(UermValue):
    schema_version: Literal["uerm-runtime-telemetry-batch-0.1"] = (
        "uerm-runtime-telemetry-batch-0.1"
    )
    telemetry_id: str = Field(pattern=r"^UERM-TEL-[0-9]{4}$")
    deployment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    metrics: dict[str, float] = {}
    trace_ids: tuple[str, ...] = ()
    log_signatures: tuple[str, ...] = ()
    performance_indicators: dict[str, float] = {}
    telemetry_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_telemetry(self) -> UermRuntimeTelemetryBatch:
        if tuple(sorted(set(self.trace_ids))) != self.trace_ids:
            raise ValueError("UERM telemetry trace identifiers must be unique and sorted")
        if tuple(sorted(set(self.log_signatures))) != self.log_signatures:
            raise ValueError("UERM telemetry log signatures must be unique and sorted")
        if self.telemetry_hash != _runtime_telemetry_batch_hash(self):
            raise ValueError("UERM runtime telemetry hash does not match canonical content")
        return self


class UermRuntimeGovernanceTrace(UermValue):
    schema_version: Literal["uerm-runtime-governance-trace-0.1"] = (
        "uerm-runtime-governance-trace-0.1"
    )
    governance_trace_id: str = Field(pattern=r"^UERM-GOV-[0-9]{4}$")
    deployment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_action_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    business_rule_ref: str = Field(min_length=1, max_length=200)
    registry_rule_ref: str = Field(min_length=1, max_length=200)
    manifest_object_ref: str = Field(min_length=1, max_length=200)
    requirement_ref: str = Field(min_length=1, max_length=200)
    trace_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_trace(self) -> UermRuntimeGovernanceTrace:
        if self.trace_hash != _runtime_governance_trace_hash(self):
            raise ValueError("UERM runtime governance trace hash does not match canonical content")
        return self


class UermRuntimeSynchronizationReport(UermValue):
    schema_version: Literal["uerm-runtime-synchronization-report-0.1"] = (
        "uerm-runtime-synchronization-report-0.1"
    )
    synchronization_id: str = Field(pattern=r"^UERM-RSYNC-[0-9]{4}$")
    deployment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_manifest_version: str = Field(min_length=1, max_length=120)
    current_manifest_version: str = Field(min_length=1, max_length=120)
    runtime_application_version: str = Field(min_length=1, max_length=120)
    current_application_version: str = Field(min_length=1, max_length=120)
    status: UermCompatibilityStatus
    findings: tuple[str, ...] = ()
    observed_runtime_document: dict[str, object]
    report_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_report(self) -> UermRuntimeSynchronizationReport:
        if tuple(sorted(set(self.findings))) != self.findings:
            raise ValueError("UERM runtime synchronization findings must be unique and sorted")
        if self.report_hash != _runtime_synchronization_report_hash(self):
            raise ValueError(
                "UERM runtime synchronization report hash does not match canonical content"
            )
        return self


class UermRuntimeUpgradePlan(UermValue):
    schema_version: Literal["uerm-runtime-upgrade-plan-0.1"] = (
        "uerm-runtime-upgrade-plan-0.1"
    )
    upgrade_plan_id: str = Field(pattern=r"^UERM-UPG-[0-9]{4}$")
    deployment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    synchronization_report_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    from_manifest_version: str = Field(min_length=1, max_length=120)
    to_manifest_version: str = Field(min_length=1, max_length=120)
    from_application_version: str = Field(min_length=1, max_length=120)
    to_application_version: str = Field(min_length=1, max_length=120)
    status: UermRuntimeUpgradeStatus
    steps: tuple[dict[str, object], ...]
    blocked_by: tuple[str, ...] = ()
    plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_plan(self) -> UermRuntimeUpgradePlan:
        if tuple(sorted(set(self.blocked_by))) != self.blocked_by:
            raise ValueError("UERM runtime upgrade blockers must be unique and sorted")
        if self.plan_hash != _runtime_upgrade_plan_hash(self):
            raise ValueError("UERM runtime upgrade plan hash does not match canonical content")
        return self


class UermRuntimeContext(UermValue):
    request_id: str = Field(pattern=r"^[a-zA-Z0-9._:-]{8,128}$")
    correlation_id: str = Field(pattern=r"^[a-zA-Z0-9._:-]{8,128}$")
    tenant: str = Field(min_length=1, max_length=120)
    user: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=120)
    permissions: tuple[str, ...] = ()
    session_id: str | None = Field(default=None, max_length=160)
    locale: str = Field(default="en-US", min_length=2, max_length=20)
    time_zone: str = Field(default="UTC", min_length=1, max_length=80)
    manifest_version: str = Field(min_length=1, max_length=120)
    application_version: str = Field(min_length=1, max_length=120)
    context_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_context(self) -> UermRuntimeContext:
        if tuple(sorted(set(self.permissions))) != self.permissions:
            raise ValueError("UERM permissions must be unique and sorted")
        if self.context_hash != _runtime_context_hash(self):
            raise ValueError("UERM runtime context hash does not match canonical content")
        return self


class UermRuntimeDeployment(UermValue):
    schema_version: Literal["uerm-runtime-deployment-0.1"] = "uerm-runtime-deployment-0.1"
    deployment_id: str = Field(pattern=r"^UERM-DEP-[0-9]{4}$")
    project_id: str = Field(min_length=1)
    r6_build_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    r6_manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    service_identity: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,179}$")
    environment: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,79}$")
    manifest_version: str = Field(min_length=1, max_length=120)
    application_version: str = Field(min_length=1, max_length=120)
    template_version: str = Field(min_length=1, max_length=80)
    generator_pack_id: str = Field(pattern=r"^[a-z][a-z0-9.-]{2,119}$")
    generator_pack_version: str = Field(pattern=r"^[0-9]+\.[0-9]+$")
    artifact_count: int = Field(ge=1)
    deployment_location: str = Field(min_length=1, max_length=300)
    endpoint_urls: tuple[str, ...] = ()
    dependency_service_ids: tuple[str, ...] = ()
    status: UermDeploymentStatus
    deployment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_deployment(self) -> UermRuntimeDeployment:
        if tuple(sorted(set(self.endpoint_urls))) != self.endpoint_urls:
            raise ValueError("UERM endpoint URLs must be unique and sorted")
        if tuple(sorted(set(self.dependency_service_ids))) != self.dependency_service_ids:
            raise ValueError("UERM dependency service identifiers must be unique and sorted")
        legacy_hash_allowed = (
            self.template_version == "1.0" and self.deployment_location == "unassigned"
        )
        valid_hashes = {_runtime_deployment_hash(self)}
        if legacy_hash_allowed:
            valid_hashes.add(_runtime_deployment_legacy_hash(self))
        if self.deployment_hash not in valid_hashes:
            raise ValueError("UERM runtime deployment hash does not match canonical content")
        return self


class UermHealthReport(UermValue):
    schema_version: Literal["uerm-health-report-0.1"] = "uerm-health-report-0.1"
    deployment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: UermHealthStatus
    checks: dict[str, UermHealthStatus]
    metrics: dict[str, float] = {}
    report_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_report(self) -> UermHealthReport:
        expected = (
            UermHealthStatus.UNHEALTHY
            if any(status is UermHealthStatus.UNHEALTHY for status in self.checks.values())
            else UermHealthStatus.DEGRADED
            if any(status is UermHealthStatus.DEGRADED for status in self.checks.values())
            else UermHealthStatus.HEALTHY
        )
        if self.status is not expected:
            raise ValueError("UERM health status must match component checks")
        if self.report_hash != _health_report_hash(self):
            raise ValueError("UERM health report hash does not match canonical content")
        return self


class UermRuntimeEvent(UermValue):
    schema_version: Literal["uerm-runtime-event-0.1"] = "uerm-runtime-event-0.1"
    event_id: str = Field(pattern=r"^UERM-EVT-[0-9]{4}$")
    deployment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_type: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,119}$")
    context: UermRuntimeContext
    payload: dict[str, object]
    manifest_rule_ref: str = Field(min_length=1, max_length=200)
    event_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_event(self) -> UermRuntimeEvent:
        if self.event_hash != _runtime_event_hash(self):
            raise ValueError("UERM runtime event hash does not match canonical content")
        return self


class UermCompatibilityReport(UermValue):
    schema_version: Literal["uerm-compatibility-report-0.1"] = (
        "uerm-compatibility-report-0.1"
    )
    deployment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_manifest_version: str = Field(min_length=1, max_length=120)
    current_manifest_version: str = Field(min_length=1, max_length=120)
    runtime_application_version: str = Field(min_length=1, max_length=120)
    current_application_version: str = Field(min_length=1, max_length=120)
    status: UermCompatibilityStatus
    findings: tuple[str, ...] = ()
    report_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_report(self) -> UermCompatibilityReport:
        if tuple(sorted(set(self.findings))) != self.findings:
            raise ValueError("UERM compatibility findings must be unique and sorted")
        if self.report_hash != _compatibility_report_hash(self):
            raise ValueError("UERM compatibility report hash does not match canonical content")
        return self


class UermWorkflowInstance(UermValue):
    schema_version: Literal["uerm-workflow-instance-0.1"] = "uerm-workflow-instance-0.1"
    workflow_instance_id: str = Field(pattern=r"^UERM-WF-[0-9]{4}$")
    deployment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    workflow_key: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,179}$")
    previous_state: str | None = Field(default=None, max_length=120)
    current_state: str = Field(min_length=1, max_length=120)
    allowed_transitions: dict[str, tuple[str, ...]]
    responsible_actor: str = Field(min_length=1, max_length=200)
    context: UermRuntimeContext
    audit_history: tuple[dict[str, object], ...] = ()
    pending_actions: tuple[str, ...] = ()
    status: UermWorkflowStatus
    instance_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_instance(self) -> UermWorkflowInstance:
        normalized = {
            state: tuple(sorted(set(targets)))
            for state, targets in sorted(self.allowed_transitions.items())
        }
        if self.allowed_transitions != normalized:
            raise ValueError("UERM workflow transitions must be unique and sorted")
        if tuple(sorted(set(self.pending_actions))) != self.pending_actions:
            raise ValueError("UERM pending workflow actions must be unique and sorted")
        if self.instance_hash != _workflow_instance_hash(self):
            raise ValueError("UERM workflow instance hash does not match canonical content")
        return self


class UermRuntimeError(UermValue):
    schema_version: Literal["uerm-runtime-error-0.1"] = "uerm-runtime-error-0.1"
    error_id: str = Field(pattern=r"^UERM-ERR-[0-9]{4}$")
    deployment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    severity: UermErrorSeverity
    category: UermErrorCategory
    source: str = Field(min_length=1, max_length=200)
    correlation_id: str = Field(pattern=r"^[a-zA-Z0-9._:-]{8,128}$")
    message: str = Field(min_length=1, max_length=500)
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_.-]{2,119}$")
    recovery_guidance: str = Field(min_length=1, max_length=500)
    context_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    error_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_error(self) -> UermRuntimeError:
        if self.error_hash != _runtime_error_hash(self):
            raise ValueError("UERM runtime error hash does not match canonical content")
        return self


class UermRecoveryAction(UermValue):
    schema_version: Literal["uerm-recovery-action-0.1"] = "uerm-recovery-action-0.1"
    recovery_id: str = Field(pattern=r"^UERM-REC-[0-9]{4}$")
    error_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    strategy: UermRecoveryStrategy
    status: UermRecoveryStatus
    policy_document: dict[str, object]
    action_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_action(self) -> UermRecoveryAction:
        if self.action_hash != _recovery_action_hash(self):
            raise ValueError("UERM recovery action hash does not match canonical content")
        return self


class UermDigitalTwinSnapshot(UermValue):
    schema_version: Literal["uerm-digital-twin-snapshot-0.1"] = (
        "uerm-digital-twin-snapshot-0.1"
    )
    snapshot_id: str = Field(pattern=r"^UERM-TWIN-[0-9]{4}$")
    deployment_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    topology: dict[str, object]
    dependencies: tuple[str, ...] = ()
    health_status: UermHealthStatus
    metrics: dict[str, float] = {}
    configuration: dict[str, object] = {}
    active_workflows: tuple[str, ...] = ()
    event_flows: tuple[str, ...] = ()
    snapshot_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_snapshot(self) -> UermDigitalTwinSnapshot:
        if tuple(sorted(set(self.dependencies))) != self.dependencies:
            raise ValueError("UERM digital twin dependencies must be unique and sorted")
        if tuple(sorted(set(self.active_workflows))) != self.active_workflows:
            raise ValueError("UERM active workflows must be unique and sorted")
        if tuple(sorted(set(self.event_flows))) != self.event_flows:
            raise ValueError("UERM event flows must be unique and sorted")
        if self.snapshot_hash != _digital_twin_snapshot_hash(self):
            raise ValueError("UERM digital twin snapshot hash does not match canonical content")
        return self


def runtime_context(
    *,
    request_id: str,
    correlation_id: str,
    tenant: str,
    user: str,
    role: str,
    permissions: tuple[str, ...],
    manifest_version: str,
    application_version: str,
    session_id: str | None = None,
    locale: str = "en-US",
    time_zone: str = "UTC",
) -> UermRuntimeContext:
    normalized_permissions = tuple(sorted(set(permissions)))
    provisional = UermRuntimeContext.model_construct(
        request_id=request_id,
        correlation_id=correlation_id,
        tenant=tenant,
        user=user,
        role=role,
        permissions=normalized_permissions,
        session_id=session_id,
        locale=locale,
        time_zone=time_zone,
        manifest_version=manifest_version,
        application_version=application_version,
        context_hash="0" * 64,
    )
    return UermRuntimeContext(
        request_id=request_id,
        correlation_id=correlation_id,
        tenant=tenant,
        user=user,
        role=role,
        permissions=normalized_permissions,
        session_id=session_id,
        locale=locale,
        time_zone=time_zone,
        manifest_version=manifest_version,
        application_version=application_version,
        context_hash=_runtime_context_hash(provisional),
    )


def register_runtime_deployment(
    *,
    index: int,
    project_id: str,
    r6_build_hash: str,
    r6_manifest_hash: str,
    service_identity: str,
    environment: str,
    manifest_version: str,
    application_version: str,
    generator_pack_id: str,
    generator_pack_version: str,
    artifact_count: int,
    template_version: str = "1.0",
    deployment_location: str = "unassigned",
    endpoint_urls: tuple[str, ...] = (),
    dependency_service_ids: tuple[str, ...] = (),
) -> UermRuntimeDeployment:
    endpoints = tuple(sorted(set(endpoint_urls)))
    dependencies = tuple(sorted(set(dependency_service_ids)))
    provisional = UermRuntimeDeployment.model_construct(
        schema_version="uerm-runtime-deployment-0.1",
        deployment_id=f"UERM-DEP-{index:04d}",
        project_id=project_id,
        r6_build_hash=r6_build_hash,
        r6_manifest_hash=r6_manifest_hash,
        service_identity=service_identity,
        environment=environment,
        manifest_version=manifest_version,
        application_version=application_version,
        template_version=template_version,
        generator_pack_id=generator_pack_id,
        generator_pack_version=generator_pack_version,
        artifact_count=artifact_count,
        deployment_location=deployment_location,
        endpoint_urls=endpoints,
        dependency_service_ids=dependencies,
        status=UermDeploymentStatus.REGISTERED,
        deployment_hash="0" * 64,
    )
    return UermRuntimeDeployment(
        deployment_id=f"UERM-DEP-{index:04d}",
        project_id=project_id,
        r6_build_hash=r6_build_hash,
        r6_manifest_hash=r6_manifest_hash,
        service_identity=service_identity,
        environment=environment,
        manifest_version=manifest_version,
        application_version=application_version,
        template_version=template_version,
        generator_pack_id=generator_pack_id,
        generator_pack_version=generator_pack_version,
        artifact_count=artifact_count,
        deployment_location=deployment_location,
        endpoint_urls=endpoints,
        dependency_service_ids=dependencies,
        status=UermDeploymentStatus.REGISTERED,
        deployment_hash=_runtime_deployment_hash(provisional),
    )


def assess_runtime_compatibility(
    *,
    deployment: UermRuntimeDeployment,
    current_manifest_version: str,
    current_application_version: str,
) -> UermCompatibilityReport:
    findings: list[str] = []
    if deployment.manifest_version != current_manifest_version:
        findings.append("manifest_version_mismatch")
    if deployment.application_version != current_application_version:
        findings.append("application_version_mismatch")
    status = UermCompatibilityStatus.COMPATIBLE
    if findings:
        status = UermCompatibilityStatus.OUTDATED
    if deployment.status is UermDeploymentStatus.RETIRED:
        findings.append("deployment_retired")
        status = UermCompatibilityStatus.INCOMPATIBLE
    normalized_findings = tuple(sorted(set(findings)))
    provisional = UermCompatibilityReport.model_construct(
        schema_version="uerm-compatibility-report-0.1",
        deployment_hash=deployment.deployment_hash,
        runtime_manifest_version=deployment.manifest_version,
        current_manifest_version=current_manifest_version,
        runtime_application_version=deployment.application_version,
        current_application_version=current_application_version,
        status=status,
        findings=normalized_findings,
        report_hash="0" * 64,
    )
    return UermCompatibilityReport(
        deployment_hash=deployment.deployment_hash,
        runtime_manifest_version=deployment.manifest_version,
        current_manifest_version=current_manifest_version,
        runtime_application_version=deployment.application_version,
        current_application_version=current_application_version,
        status=status,
        findings=normalized_findings,
        report_hash=_compatibility_report_hash(provisional),
    )


def start_workflow_instance(
    *,
    index: int,
    deployment_hash: str,
    workflow_key: str,
    initial_state: str,
    allowed_transitions: dict[str, tuple[str, ...]],
    responsible_actor: str,
    context: UermRuntimeContext,
    pending_actions: tuple[str, ...] = (),
) -> UermWorkflowInstance:
    normalized_transitions = _normalize_transitions(allowed_transitions)
    normalized_pending = tuple(sorted(set(pending_actions)))
    provisional = UermWorkflowInstance.model_construct(
        schema_version="uerm-workflow-instance-0.1",
        workflow_instance_id=f"UERM-WF-{index:04d}",
        deployment_hash=deployment_hash,
        workflow_key=workflow_key,
        previous_state=None,
        current_state=initial_state,
        allowed_transitions=normalized_transitions,
        responsible_actor=responsible_actor,
        context=context,
        audit_history=(
            {
                "from": None,
                "to": initial_state,
                "actor": responsible_actor,
                "reason": "workflow_started",
            },
        ),
        pending_actions=normalized_pending,
        status=UermWorkflowStatus.ACTIVE,
        instance_hash="0" * 64,
    )
    return UermWorkflowInstance(
        workflow_instance_id=f"UERM-WF-{index:04d}",
        deployment_hash=deployment_hash,
        workflow_key=workflow_key,
        previous_state=None,
        current_state=initial_state,
        allowed_transitions=normalized_transitions,
        responsible_actor=responsible_actor,
        context=context,
        audit_history=provisional.audit_history,
        pending_actions=normalized_pending,
        status=UermWorkflowStatus.ACTIVE,
        instance_hash=_workflow_instance_hash(provisional),
    )


def transition_workflow_instance(
    instance: UermWorkflowInstance,
    *,
    next_state: str,
    actor: str,
    reason: str,
    pending_actions: tuple[str, ...] = (),
) -> UermWorkflowInstance:
    allowed = instance.allowed_transitions.get(instance.current_state, ())
    if next_state not in allowed:
        raise ValueError("UERM workflow transition is not allowed")
    normalized_pending = tuple(sorted(set(pending_actions)))
    status = UermWorkflowStatus.COMPLETED if not instance.allowed_transitions.get(next_state) else (
        UermWorkflowStatus.ACTIVE
    )
    audit_history = (
        *instance.audit_history,
        {
            "from": instance.current_state,
            "to": next_state,
            "actor": actor,
            "reason": reason,
        },
    )
    provisional = UermWorkflowInstance.model_construct(
        schema_version="uerm-workflow-instance-0.1",
        workflow_instance_id=instance.workflow_instance_id,
        deployment_hash=instance.deployment_hash,
        workflow_key=instance.workflow_key,
        previous_state=instance.current_state,
        current_state=next_state,
        allowed_transitions=instance.allowed_transitions,
        responsible_actor=actor,
        context=instance.context,
        audit_history=audit_history,
        pending_actions=normalized_pending,
        status=status,
        instance_hash="0" * 64,
    )
    return UermWorkflowInstance(
        workflow_instance_id=instance.workflow_instance_id,
        deployment_hash=instance.deployment_hash,
        workflow_key=instance.workflow_key,
        previous_state=instance.current_state,
        current_state=next_state,
        allowed_transitions=instance.allowed_transitions,
        responsible_actor=actor,
        context=instance.context,
        audit_history=audit_history,
        pending_actions=normalized_pending,
        status=status,
        instance_hash=_workflow_instance_hash(provisional),
    )


def runtime_error(
    *,
    index: int,
    deployment_hash: str,
    severity: UermErrorSeverity,
    category: UermErrorCategory,
    source: str,
    correlation_id: str,
    message: str,
    code: str,
    recovery_guidance: str,
    context_hash: str,
) -> UermRuntimeError:
    provisional = UermRuntimeError.model_construct(
        schema_version="uerm-runtime-error-0.1",
        error_id=f"UERM-ERR-{index:04d}",
        deployment_hash=deployment_hash,
        severity=severity,
        category=category,
        source=source,
        correlation_id=correlation_id,
        message=message,
        code=code,
        recovery_guidance=recovery_guidance,
        context_hash=context_hash,
        error_hash="0" * 64,
    )
    return UermRuntimeError(
        error_id=f"UERM-ERR-{index:04d}",
        deployment_hash=deployment_hash,
        severity=severity,
        category=category,
        source=source,
        correlation_id=correlation_id,
        message=message,
        code=code,
        recovery_guidance=recovery_guidance,
        context_hash=context_hash,
        error_hash=_runtime_error_hash(provisional),
    )


def recovery_action(
    *,
    index: int,
    error_hash: str,
    strategy: UermRecoveryStrategy,
    status: UermRecoveryStatus = UermRecoveryStatus.PLANNED,
    policy_document: dict[str, object] | None = None,
) -> UermRecoveryAction:
    policy = {
        "schema_version": "uerm-recovery-policy-0.1",
        "requires_authorized_operator": True,
        "strategy": strategy.value,
    } | (policy_document or {})
    provisional = UermRecoveryAction.model_construct(
        schema_version="uerm-recovery-action-0.1",
        recovery_id=f"UERM-REC-{index:04d}",
        error_hash=error_hash,
        strategy=strategy,
        status=status,
        policy_document=policy,
        action_hash="0" * 64,
    )
    return UermRecoveryAction(
        recovery_id=f"UERM-REC-{index:04d}",
        error_hash=error_hash,
        strategy=strategy,
        status=status,
        policy_document=policy,
        action_hash=_recovery_action_hash(provisional),
    )


def digital_twin_snapshot(
    *,
    index: int,
    deployment: UermRuntimeDeployment,
    health_status: UermHealthStatus,
    metrics: dict[str, float] | None = None,
    configuration: dict[str, object] | None = None,
    active_workflows: tuple[str, ...] = (),
    event_flows: tuple[str, ...] = (),
) -> UermDigitalTwinSnapshot:
    dependencies = tuple(sorted(set(deployment.dependency_service_ids)))
    workflows = tuple(sorted(set(active_workflows)))
    flows = tuple(sorted(set(event_flows)))
    normalized_metrics = dict(sorted((metrics or {}).items()))
    normalized_configuration = dict(sorted((configuration or {}).items()))
    topology = {
        "service_identity": deployment.service_identity,
        "environment": deployment.environment,
        "deployment_location": deployment.deployment_location,
        "endpoints": list(deployment.endpoint_urls),
    }
    provisional = UermDigitalTwinSnapshot.model_construct(
        schema_version="uerm-digital-twin-snapshot-0.1",
        snapshot_id=f"UERM-TWIN-{index:04d}",
        deployment_hash=deployment.deployment_hash,
        topology=topology,
        dependencies=dependencies,
        health_status=health_status,
        metrics=normalized_metrics,
        configuration=normalized_configuration,
        active_workflows=workflows,
        event_flows=flows,
        snapshot_hash="0" * 64,
    )
    return UermDigitalTwinSnapshot(
        snapshot_id=f"UERM-TWIN-{index:04d}",
        deployment_hash=deployment.deployment_hash,
        topology=topology,
        dependencies=dependencies,
        health_status=health_status,
        metrics=normalized_metrics,
        configuration=normalized_configuration,
        active_workflows=workflows,
        event_flows=flows,
        snapshot_hash=_digital_twin_snapshot_hash(provisional),
    )


def runtime_health_report(
    *,
    deployment_hash: str,
    checks: dict[str, UermHealthStatus],
    metrics: dict[str, float] | None = None,
) -> UermHealthReport:
    normalized_checks = dict(sorted(checks.items()))
    status = (
        UermHealthStatus.UNHEALTHY
        if any(value is UermHealthStatus.UNHEALTHY for value in normalized_checks.values())
        else UermHealthStatus.DEGRADED
        if any(value is UermHealthStatus.DEGRADED for value in normalized_checks.values())
        else UermHealthStatus.HEALTHY
    )
    normalized_metrics = dict(sorted((metrics or {}).items()))
    provisional = UermHealthReport.model_construct(
        schema_version="uerm-health-report-0.1",
        deployment_hash=deployment_hash,
        status=status,
        checks=normalized_checks,
        metrics=normalized_metrics,
        report_hash="0" * 64,
    )
    return UermHealthReport(
        deployment_hash=deployment_hash,
        status=status,
        checks=normalized_checks,
        metrics=normalized_metrics,
        report_hash=_health_report_hash(provisional),
    )


def runtime_event(
    *,
    index: int,
    deployment_hash: str,
    event_type: str,
    context: UermRuntimeContext,
    payload: dict[str, object],
    manifest_rule_ref: str,
) -> UermRuntimeEvent:
    provisional = UermRuntimeEvent.model_construct(
        schema_version="uerm-runtime-event-0.1",
        event_id=f"UERM-EVT-{index:04d}",
        deployment_hash=deployment_hash,
        event_type=event_type,
        context=context,
        payload=payload,
        manifest_rule_ref=manifest_rule_ref,
        event_hash="0" * 64,
    )
    return UermRuntimeEvent(
        event_id=f"UERM-EVT-{index:04d}",
        deployment_hash=deployment_hash,
        event_type=event_type,
        context=context,
        payload=payload,
        manifest_rule_ref=manifest_rule_ref,
        event_hash=_runtime_event_hash(provisional),
    )


def register_runtime_provider(
    *,
    index: int,
    project_id: str,
    kind: UermRuntimeProviderKind,
    name: str,
    version: str,
    status: UermRuntimeProviderStatus = UermRuntimeProviderStatus.REGISTERED,
    capabilities: tuple[str, ...] = (),
    endpoint_ref: str | None = None,
    configuration: dict[str, object] | None = None,
) -> UermRuntimeProvider:
    normalized_capabilities = tuple(sorted(set(capabilities)))
    normalized_configuration = dict(sorted((configuration or {}).items()))
    provisional = UermRuntimeProvider.model_construct(
        schema_version="uerm-runtime-provider-0.1",
        provider_id=f"UERM-PROV-{index:04d}",
        project_id=project_id,
        kind=kind,
        name=name,
        version=version,
        status=status,
        capabilities=normalized_capabilities,
        endpoint_ref=endpoint_ref,
        configuration=normalized_configuration,
        provider_hash="0" * 64,
    )
    return UermRuntimeProvider(
        provider_id=f"UERM-PROV-{index:04d}",
        project_id=project_id,
        kind=kind,
        name=name,
        version=version,
        status=status,
        capabilities=normalized_capabilities,
        endpoint_ref=endpoint_ref,
        configuration=normalized_configuration,
        provider_hash=_runtime_provider_hash(provisional),
    )


def evaluate_runtime_policy(
    *,
    index: int,
    deployment_hash: str,
    context: UermRuntimeContext,
    action: str,
    resource: str,
    provider_hash: str | None = None,
    policy_refs: tuple[str, ...] = (),
) -> UermPolicyEvaluation:
    normalized_policies = tuple(sorted(set(policy_refs)))
    allowed = "*" in context.permissions or action in context.permissions
    decision = UermPolicyDecision.ALLOW if allowed else UermPolicyDecision.DENY
    reason = (
        "runtime context permission matched requested action"
        if allowed
        else "runtime context permission did not include requested action"
    )
    provisional = UermPolicyEvaluation.model_construct(
        schema_version="uerm-policy-evaluation-0.1",
        evaluation_id=f"UERM-POL-{index:04d}",
        deployment_hash=deployment_hash,
        provider_hash=provider_hash,
        context_hash=context.context_hash,
        action=action,
        resource=resource,
        decision=decision,
        matched_policies=normalized_policies,
        reason=reason,
        evaluation_hash="0" * 64,
    )
    return UermPolicyEvaluation(
        evaluation_id=f"UERM-POL-{index:04d}",
        deployment_hash=deployment_hash,
        provider_hash=provider_hash,
        context_hash=context.context_hash,
        action=action,
        resource=resource,
        decision=decision,
        matched_policies=normalized_policies,
        reason=reason,
        evaluation_hash=_policy_evaluation_hash(provisional),
    )


def dispatch_runtime_event(
    *,
    index: int,
    event: UermRuntimeEvent,
    provider: UermRuntimeProvider,
    subscriber_refs: tuple[str, ...] = (),
) -> UermEventDispatch:
    if provider.kind is not UermRuntimeProviderKind.EVENT_BUS:
        raise ValueError("UERM event dispatch provider must be an event bus")
    normalized_subscribers = tuple(sorted(set(subscriber_refs)))
    status = (
        UermRuntimeDispatchStatus.DELIVERED
        if provider.status is UermRuntimeProviderStatus.AVAILABLE
        and normalized_subscribers
        else UermRuntimeDispatchStatus.ACCEPTED
    )
    document: dict[str, object] = {
        "event_type": event.event_type,
        "provider": provider.name,
        "provider_kind": provider.kind.value,
        "subscriber_count": len(normalized_subscribers),
    }
    provisional = UermEventDispatch.model_construct(
        schema_version="uerm-event-dispatch-0.1",
        dispatch_id=f"UERM-DISP-{index:04d}",
        event_hash=event.event_hash,
        provider_hash=provider.provider_hash,
        status=status,
        subscriber_refs=normalized_subscribers,
        dispatch_document=document,
        dispatch_hash="0" * 64,
    )
    return UermEventDispatch(
        dispatch_id=f"UERM-DISP-{index:04d}",
        event_hash=event.event_hash,
        provider_hash=provider.provider_hash,
        status=status,
        subscriber_refs=normalized_subscribers,
        dispatch_document=document,
        dispatch_hash=_event_dispatch_hash(provisional),
    )


def sync_runtime_deployment(
    *,
    index: int,
    deployment: UermRuntimeDeployment,
    provider: UermRuntimeProvider,
) -> UermDeploymentRuntimeSync:
    if provider.kind is not UermRuntimeProviderKind.DEPLOYMENT_RUNTIME:
        raise ValueError("UERM deployment sync provider must be a deployment runtime")
    status = (
        UermRuntimeDispatchStatus.DELIVERED
        if provider.status is UermRuntimeProviderStatus.AVAILABLE
        else UermRuntimeDispatchStatus.ACCEPTED
    )
    document: dict[str, object] = {
        "service_identity": deployment.service_identity,
        "environment": deployment.environment,
        "endpoint_urls": list(deployment.endpoint_urls),
        "provider": provider.name,
        "provider_kind": provider.kind.value,
    }
    provisional = UermDeploymentRuntimeSync.model_construct(
        schema_version="uerm-deployment-runtime-sync-0.1",
        sync_id=f"UERM-SYNC-{index:04d}",
        deployment_hash=deployment.deployment_hash,
        provider_hash=provider.provider_hash,
        status=status,
        runtime_document=document,
        sync_hash="0" * 64,
    )
    return UermDeploymentRuntimeSync(
        sync_id=f"UERM-SYNC-{index:04d}",
        deployment_hash=deployment.deployment_hash,
        provider_hash=provider.provider_hash,
        status=status,
        runtime_document=document,
        sync_hash=_deployment_runtime_sync_hash(provisional),
    )


def runtime_ai_request(
    *,
    index: int,
    deployment_hash: str,
    provider: UermRuntimeProvider,
    context: UermRuntimeContext,
    policy_evaluation: UermPolicyEvaluation,
    capability: str,
    prompt: str,
) -> UermRuntimeAiRequest:
    if provider.kind is not UermRuntimeProviderKind.AI_SERVICE:
        raise ValueError("UERM runtime AI provider must be an AI service")
    allowed = (
        policy_evaluation.decision is UermPolicyDecision.ALLOW
        and capability in provider.capabilities
        and provider.status is UermRuntimeProviderStatus.AVAILABLE
    )
    status = (
        UermRuntimeAiRequestStatus.ACCEPTED
        if allowed
        else UermRuntimeAiRequestStatus.REJECTED
    )
    response: dict[str, object] = {
        "capability": capability,
        "provider": provider.name,
        "policy_decision": policy_evaluation.decision.value,
        "realization": "deterministic_runtime_ai_contract",
    }
    if status is UermRuntimeAiRequestStatus.REJECTED:
        response["reason"] = "policy, provider status, or provider capability rejected request"
    provisional = UermRuntimeAiRequest.model_construct(
        schema_version="uerm-runtime-ai-request-0.1",
        ai_request_id=f"UERM-AI-{index:04d}",
        deployment_hash=deployment_hash,
        provider_hash=provider.provider_hash,
        context_hash=context.context_hash,
        policy_evaluation_hash=policy_evaluation.evaluation_hash,
        capability=capability,
        prompt=prompt,
        status=status,
        response_document=response,
        request_hash="0" * 64,
    )
    return UermRuntimeAiRequest(
        ai_request_id=f"UERM-AI-{index:04d}",
        deployment_hash=deployment_hash,
        provider_hash=provider.provider_hash,
        context_hash=context.context_hash,
        policy_evaluation_hash=policy_evaluation.evaluation_hash,
        capability=capability,
        prompt=prompt,
        status=status,
        response_document=response,
        request_hash=_runtime_ai_request_hash(provisional),
    )


def bind_runtime_plugin(
    *,
    index: int,
    deployment_hash: str,
    provider: UermRuntimeProvider,
    plugin_name: str,
    plugin_version: str,
    requested_capabilities: tuple[str, ...] = (),
) -> UermPluginBinding:
    normalized_capabilities = tuple(sorted(set(requested_capabilities)))
    findings: list[str] = []
    if provider.kind is not UermRuntimeProviderKind.PLUGIN_RUNTIME:
        findings.append("provider_kind_mismatch")
    missing = sorted(set(normalized_capabilities) - set(provider.capabilities))
    findings.extend(f"missing_capability:{capability}" for capability in missing)
    status = (
        UermCompatibilityStatus.COMPATIBLE
        if not findings and provider.status is UermRuntimeProviderStatus.AVAILABLE
        else UermCompatibilityStatus.INCOMPATIBLE
    )
    normalized_findings = tuple(sorted(set(findings)))
    provisional = UermPluginBinding.model_construct(
        schema_version="uerm-plugin-binding-0.1",
        binding_id=f"UERM-PLUG-{index:04d}",
        deployment_hash=deployment_hash,
        provider_hash=provider.provider_hash,
        plugin_name=plugin_name,
        plugin_version=plugin_version,
        requested_capabilities=normalized_capabilities,
        compatibility_status=status,
        findings=normalized_findings,
        binding_hash="0" * 64,
    )
    return UermPluginBinding(
        binding_id=f"UERM-PLUG-{index:04d}",
        deployment_hash=deployment_hash,
        provider_hash=provider.provider_hash,
        plugin_name=plugin_name,
        plugin_version=plugin_version,
        requested_capabilities=normalized_capabilities,
        compatibility_status=status,
        findings=normalized_findings,
        binding_hash=_plugin_binding_hash(provisional),
    )


def runtime_configuration_snapshot(
    *,
    index: int,
    deployment_hash: str,
    manifest_version: str,
    configuration: dict[str, object],
    feature_flags: dict[str, bool] | None = None,
) -> UermRuntimeConfigurationSnapshot:
    redacted, sensitive_keys = _redact_sensitive_configuration(configuration)
    normalized_flags = dict(sorted((feature_flags or {}).items()))
    provisional = UermRuntimeConfigurationSnapshot.model_construct(
        schema_version="uerm-runtime-configuration-0.1",
        configuration_id=f"UERM-CFG-{index:04d}",
        deployment_hash=deployment_hash,
        manifest_version=manifest_version,
        configuration_document=redacted,
        feature_flags=normalized_flags,
        sensitive_keys=sensitive_keys,
        configuration_hash="0" * 64,
    )
    return UermRuntimeConfigurationSnapshot(
        configuration_id=f"UERM-CFG-{index:04d}",
        deployment_hash=deployment_hash,
        manifest_version=manifest_version,
        configuration_document=redacted,
        feature_flags=normalized_flags,
        sensitive_keys=sensitive_keys,
        configuration_hash=_runtime_configuration_hash(provisional),
    )


def runtime_audit_record(
    *,
    index: int,
    deployment_hash: str,
    actor: str,
    action: str,
    affected_object: str,
    correlation_id: str,
    manifest_rule_ref: str,
    previous_value: dict[str, object] | None = None,
    new_value: dict[str, object] | None = None,
) -> UermRuntimeAuditRecord:
    previous_value_hash = (
        specification_hash(previous_value) if previous_value is not None else None
    )
    new_value_hash = specification_hash(new_value) if new_value is not None else None
    provisional = UermRuntimeAuditRecord.model_construct(
        schema_version="uerm-runtime-audit-record-0.1",
        audit_id=f"UERM-AUD-{index:04d}",
        deployment_hash=deployment_hash,
        actor=actor,
        action=action,
        affected_object=affected_object,
        previous_value_hash=previous_value_hash,
        new_value_hash=new_value_hash,
        correlation_id=correlation_id,
        manifest_rule_ref=manifest_rule_ref,
        audit_hash="0" * 64,
    )
    return UermRuntimeAuditRecord(
        audit_id=f"UERM-AUD-{index:04d}",
        deployment_hash=deployment_hash,
        actor=actor,
        action=action,
        affected_object=affected_object,
        previous_value_hash=previous_value_hash,
        new_value_hash=new_value_hash,
        correlation_id=correlation_id,
        manifest_rule_ref=manifest_rule_ref,
        audit_hash=_runtime_audit_record_hash(provisional),
    )


def runtime_telemetry_batch(
    *,
    index: int,
    deployment_hash: str,
    metrics: dict[str, float] | None = None,
    trace_ids: tuple[str, ...] = (),
    log_signatures: tuple[str, ...] = (),
    performance_indicators: dict[str, float] | None = None,
) -> UermRuntimeTelemetryBatch:
    normalized_metrics = dict(sorted((metrics or {}).items()))
    normalized_traces = tuple(sorted(set(trace_ids)))
    normalized_logs = tuple(sorted(set(log_signatures)))
    normalized_indicators = dict(sorted((performance_indicators or {}).items()))
    provisional = UermRuntimeTelemetryBatch.model_construct(
        schema_version="uerm-runtime-telemetry-batch-0.1",
        telemetry_id=f"UERM-TEL-{index:04d}",
        deployment_hash=deployment_hash,
        metrics=normalized_metrics,
        trace_ids=normalized_traces,
        log_signatures=normalized_logs,
        performance_indicators=normalized_indicators,
        telemetry_hash="0" * 64,
    )
    return UermRuntimeTelemetryBatch(
        telemetry_id=f"UERM-TEL-{index:04d}",
        deployment_hash=deployment_hash,
        metrics=normalized_metrics,
        trace_ids=normalized_traces,
        log_signatures=normalized_logs,
        performance_indicators=normalized_indicators,
        telemetry_hash=_runtime_telemetry_batch_hash(provisional),
    )


def runtime_governance_trace(
    *,
    index: int,
    deployment_hash: str,
    runtime_action_hash: str,
    business_rule_ref: str,
    registry_rule_ref: str,
    manifest_object_ref: str,
    requirement_ref: str,
) -> UermRuntimeGovernanceTrace:
    provisional = UermRuntimeGovernanceTrace.model_construct(
        schema_version="uerm-runtime-governance-trace-0.1",
        governance_trace_id=f"UERM-GOV-{index:04d}",
        deployment_hash=deployment_hash,
        runtime_action_hash=runtime_action_hash,
        business_rule_ref=business_rule_ref,
        registry_rule_ref=registry_rule_ref,
        manifest_object_ref=manifest_object_ref,
        requirement_ref=requirement_ref,
        trace_hash="0" * 64,
    )
    return UermRuntimeGovernanceTrace(
        governance_trace_id=f"UERM-GOV-{index:04d}",
        deployment_hash=deployment_hash,
        runtime_action_hash=runtime_action_hash,
        business_rule_ref=business_rule_ref,
        registry_rule_ref=registry_rule_ref,
        manifest_object_ref=manifest_object_ref,
        requirement_ref=requirement_ref,
        trace_hash=_runtime_governance_trace_hash(provisional),
    )


def runtime_synchronization_report(
    *,
    index: int,
    deployment: UermRuntimeDeployment,
    current_manifest_version: str,
    current_application_version: str,
    observed_runtime: dict[str, object] | None = None,
) -> UermRuntimeSynchronizationReport:
    observed = dict(sorted((observed_runtime or {}).items()))
    findings = list(
        assess_runtime_compatibility(
            deployment=deployment,
            current_manifest_version=current_manifest_version,
            current_application_version=current_application_version,
        ).findings
    )
    for key in (
        "deprecated_apis",
        "incompatible_services",
        "missing_migrations",
        "obsolete_workflows",
    ):
        if observed.get(key):
            findings.append(key)
    normalized_findings = tuple(sorted(set(findings)))
    status = UermCompatibilityStatus.COMPATIBLE
    if normalized_findings:
        status = UermCompatibilityStatus.OUTDATED
    if any(
        finding in normalized_findings
        for finding in ("incompatible_services", "missing_migrations")
    ):
        status = UermCompatibilityStatus.INCOMPATIBLE
    provisional = UermRuntimeSynchronizationReport.model_construct(
        schema_version="uerm-runtime-synchronization-report-0.1",
        synchronization_id=f"UERM-RSYNC-{index:04d}",
        deployment_hash=deployment.deployment_hash,
        runtime_manifest_version=deployment.manifest_version,
        current_manifest_version=current_manifest_version,
        runtime_application_version=deployment.application_version,
        current_application_version=current_application_version,
        status=status,
        findings=normalized_findings,
        observed_runtime_document=observed,
        report_hash="0" * 64,
    )
    return UermRuntimeSynchronizationReport(
        synchronization_id=f"UERM-RSYNC-{index:04d}",
        deployment_hash=deployment.deployment_hash,
        runtime_manifest_version=deployment.manifest_version,
        current_manifest_version=current_manifest_version,
        runtime_application_version=deployment.application_version,
        current_application_version=current_application_version,
        status=status,
        findings=normalized_findings,
        observed_runtime_document=observed,
        report_hash=_runtime_synchronization_report_hash(provisional),
    )


def runtime_upgrade_plan(
    *,
    index: int,
    deployment: UermRuntimeDeployment,
    synchronization_report: UermRuntimeSynchronizationReport,
) -> UermRuntimeUpgradePlan:
    blockers = tuple(
        sorted(
            finding
            for finding in synchronization_report.findings
            if finding in {"incompatible_services", "missing_migrations"}
        )
    )
    status = UermRuntimeUpgradeStatus.BLOCKED if blockers else UermRuntimeUpgradeStatus.PLANNED
    steps = (
        {
            "step": "impact_analysis",
            "input": synchronization_report.report_hash,
            "output": "manifest-runtime delta",
        },
        {
            "step": "artifact_regeneration",
            "input": synchronization_report.current_manifest_version,
            "output": "new UAGF build candidate",
        },
        {
            "step": "verification",
            "input": "generated artifacts",
            "output": "validation gate report",
        },
        {
            "step": "deployment",
            "input": deployment.deployment_location,
            "output": "versioned runtime rollout",
        },
        {
            "step": "runtime_migration",
            "input": synchronization_report.findings,
            "output": "runtime state migration evidence",
        },
        {
            "step": "validation",
            "input": "post-deployment telemetry",
            "output": "synchronized runtime report",
        },
    )
    provisional = UermRuntimeUpgradePlan.model_construct(
        schema_version="uerm-runtime-upgrade-plan-0.1",
        upgrade_plan_id=f"UERM-UPG-{index:04d}",
        deployment_hash=deployment.deployment_hash,
        synchronization_report_hash=synchronization_report.report_hash,
        from_manifest_version=synchronization_report.runtime_manifest_version,
        to_manifest_version=synchronization_report.current_manifest_version,
        from_application_version=synchronization_report.runtime_application_version,
        to_application_version=synchronization_report.current_application_version,
        status=status,
        steps=steps,
        blocked_by=blockers,
        plan_hash="0" * 64,
    )
    return UermRuntimeUpgradePlan(
        upgrade_plan_id=f"UERM-UPG-{index:04d}",
        deployment_hash=deployment.deployment_hash,
        synchronization_report_hash=synchronization_report.report_hash,
        from_manifest_version=synchronization_report.runtime_manifest_version,
        to_manifest_version=synchronization_report.current_manifest_version,
        from_application_version=synchronization_report.runtime_application_version,
        to_application_version=synchronization_report.current_application_version,
        status=status,
        steps=steps,
        blocked_by=blockers,
        plan_hash=_runtime_upgrade_plan_hash(provisional),
    )


def _normalize_transitions(
    transitions: dict[str, tuple[str, ...]]
) -> dict[str, tuple[str, ...]]:
    return {state: tuple(sorted(set(targets))) for state, targets in sorted(transitions.items())}


def _redact_sensitive_configuration(
    configuration: dict[str, object],
) -> tuple[dict[str, object], tuple[str, ...]]:
    sensitive_markers = ("secret", "password", "token", "credential", "api_key", "key")
    redacted: dict[str, object] = {}
    sensitive: list[str] = []
    for key, value in sorted(configuration.items()):
        lowered = key.lower()
        if any(marker in lowered for marker in sensitive_markers):
            redacted[key] = "<redacted>"
            sensitive.append(key)
        else:
            redacted[key] = value
    return redacted, tuple(sorted(set(sensitive)))


def _runtime_context_hash(context: UermRuntimeContext) -> str:
    return specification_hash(context.model_dump(mode="json", exclude={"context_hash"}))


def _runtime_deployment_hash(deployment: UermRuntimeDeployment) -> str:
    return specification_hash(
        deployment.model_dump(mode="json", exclude={"deployment_hash"})
    )


def _runtime_deployment_legacy_hash(deployment: UermRuntimeDeployment) -> str:
    return specification_hash(
        deployment.model_dump(
            mode="json",
            exclude={
                "deployment_hash",
                "template_version",
                "deployment_location",
            },
        )
    )


def _health_report_hash(report: UermHealthReport) -> str:
    return specification_hash(report.model_dump(mode="json", exclude={"report_hash"}))


def _runtime_event_hash(event: UermRuntimeEvent) -> str:
    return specification_hash(event.model_dump(mode="json", exclude={"event_hash"}))


def _compatibility_report_hash(report: UermCompatibilityReport) -> str:
    return specification_hash(report.model_dump(mode="json", exclude={"report_hash"}))


def _workflow_instance_hash(instance: UermWorkflowInstance) -> str:
    return specification_hash(instance.model_dump(mode="json", exclude={"instance_hash"}))


def _runtime_error_hash(error: UermRuntimeError) -> str:
    return specification_hash(error.model_dump(mode="json", exclude={"error_hash"}))


def _recovery_action_hash(action: UermRecoveryAction) -> str:
    return specification_hash(action.model_dump(mode="json", exclude={"action_hash"}))


def _digital_twin_snapshot_hash(snapshot: UermDigitalTwinSnapshot) -> str:
    return specification_hash(snapshot.model_dump(mode="json", exclude={"snapshot_hash"}))


def _runtime_provider_hash(provider: UermRuntimeProvider) -> str:
    return specification_hash(provider.model_dump(mode="json", exclude={"provider_hash"}))


def _policy_evaluation_hash(evaluation: UermPolicyEvaluation) -> str:
    return specification_hash(evaluation.model_dump(mode="json", exclude={"evaluation_hash"}))


def _event_dispatch_hash(dispatch: UermEventDispatch) -> str:
    return specification_hash(dispatch.model_dump(mode="json", exclude={"dispatch_hash"}))


def _deployment_runtime_sync_hash(sync: UermDeploymentRuntimeSync) -> str:
    return specification_hash(sync.model_dump(mode="json", exclude={"sync_hash"}))


def _runtime_ai_request_hash(request: UermRuntimeAiRequest) -> str:
    return specification_hash(request.model_dump(mode="json", exclude={"request_hash"}))


def _plugin_binding_hash(binding: UermPluginBinding) -> str:
    return specification_hash(binding.model_dump(mode="json", exclude={"binding_hash"}))


def _runtime_configuration_hash(configuration: UermRuntimeConfigurationSnapshot) -> str:
    return specification_hash(
        configuration.model_dump(mode="json", exclude={"configuration_hash"})
    )


def _runtime_audit_record_hash(audit: UermRuntimeAuditRecord) -> str:
    return specification_hash(audit.model_dump(mode="json", exclude={"audit_hash"}))


def _runtime_telemetry_batch_hash(telemetry: UermRuntimeTelemetryBatch) -> str:
    return specification_hash(telemetry.model_dump(mode="json", exclude={"telemetry_hash"}))


def _runtime_governance_trace_hash(trace: UermRuntimeGovernanceTrace) -> str:
    return specification_hash(trace.model_dump(mode="json", exclude={"trace_hash"}))


def _runtime_synchronization_report_hash(
    report: UermRuntimeSynchronizationReport,
) -> str:
    return specification_hash(report.model_dump(mode="json", exclude={"report_hash"}))


def _runtime_upgrade_plan_hash(plan: UermRuntimeUpgradePlan) -> str:
    return specification_hash(plan.model_dump(mode="json", exclude={"plan_hash"}))
