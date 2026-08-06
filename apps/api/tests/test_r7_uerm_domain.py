import pytest
from pydantic import ValidationError

from ai_enterprise.domain.r7_uerm import (
    UermCompatibilityStatus,
    UermDeploymentStatus,
    UermErrorCategory,
    UermErrorSeverity,
    UermHealthStatus,
    UermPolicyDecision,
    UermRecoveryStrategy,
    UermRuntimeAiRequestStatus,
    UermRuntimeDispatchStatus,
    UermRuntimeProviderKind,
    UermRuntimeProviderStatus,
    UermRuntimeUpgradeStatus,
    assess_runtime_compatibility,
    bind_runtime_plugin,
    digital_twin_snapshot,
    dispatch_runtime_event,
    evaluate_runtime_policy,
    recovery_action,
    register_runtime_deployment,
    register_runtime_provider,
    runtime_ai_request,
    runtime_audit_record,
    runtime_configuration_snapshot,
    runtime_context,
    runtime_error,
    runtime_event,
    runtime_governance_trace,
    runtime_health_report,
    runtime_synchronization_report,
    runtime_telemetry_batch,
    runtime_upgrade_plan,
    start_workflow_instance,
    sync_runtime_deployment,
    transition_workflow_instance,
)


def _deployment():
    return register_runtime_deployment(
        index=1,
        project_id="project-1",
        r6_build_hash="a" * 64,
        r6_manifest_hash="b" * 64,
        service_identity="orders.service",
        environment="development",
        manifest_version="manifest-12",
        application_version="1.0.0",
        template_version="template-3",
        generator_pack_id="uagf.core",
        generator_pack_version="1.0",
        artifact_count=12,
        deployment_location="kubernetes://cluster-a/orders",
        endpoint_urls=("https://orders.example.test", "https://orders.example.test"),
        dependency_service_ids=("payments.service", "payments.service"),
    )


def test_r7_uerm_registers_deterministic_runtime_deployment() -> None:
    first = _deployment()
    second = _deployment()

    assert first == second
    assert first.status is UermDeploymentStatus.REGISTERED
    assert first.template_version == "template-3"
    assert first.deployment_location == "kubernetes://cluster-a/orders"
    assert first.endpoint_urls == ("https://orders.example.test",)
    assert first.dependency_service_ids == ("payments.service",)
    assert first.deployment_hash


def test_r7_uerm_health_report_status_is_derived_from_component_checks() -> None:
    deployment = _deployment()

    healthy = runtime_health_report(
        deployment_hash=deployment.deployment_hash,
        checks={"database": UermHealthStatus.HEALTHY, "api": UermHealthStatus.HEALTHY},
        metrics={"response_time_ms": 12.5},
    )
    degraded = runtime_health_report(
        deployment_hash=deployment.deployment_hash,
        checks={"database": UermHealthStatus.HEALTHY, "cache": UermHealthStatus.DEGRADED},
    )
    unhealthy = runtime_health_report(
        deployment_hash=deployment.deployment_hash,
        checks={"database": UermHealthStatus.UNHEALTHY},
    )

    assert healthy.status is UermHealthStatus.HEALTHY
    assert degraded.status is UermHealthStatus.DEGRADED
    assert unhealthy.status is UermHealthStatus.UNHEALTHY


def test_r7_uerm_runtime_events_include_standard_context_and_hashes() -> None:
    deployment = _deployment()
    context = runtime_context(
        request_id="req-00000001",
        correlation_id="corr-00000001",
        tenant="tenant-a",
        user="operator@example.com",
        role="operator",
        permissions=("orders.read", "orders.write", "orders.read"),
        manifest_version=deployment.manifest_version,
        application_version=deployment.application_version,
    )
    event = runtime_event(
        index=1,
        deployment_hash=deployment.deployment_hash,
        event_type="order.created",
        context=context,
        payload={"order_id": "ORD-001"},
        manifest_rule_ref="manifest.object.order",
    )

    assert context.permissions == ("orders.read", "orders.write")
    assert event.event_id == "UERM-EVT-0001"
    assert event.context.context_hash
    assert event.event_hash


def test_r7_uerm_rejects_tampered_runtime_hashes() -> None:
    deployment = _deployment()

    with pytest.raises(ValidationError, match="deployment hash"):
        type(deployment).model_validate(
            {**deployment.model_dump(mode="json"), "deployment_hash": "0" * 64}
        )


def test_r7_uerm_compatibility_detects_outdated_runtime_versions() -> None:
    deployment = _deployment()

    compatible = assess_runtime_compatibility(
        deployment=deployment,
        current_manifest_version=deployment.manifest_version,
        current_application_version=deployment.application_version,
    )
    outdated = assess_runtime_compatibility(
        deployment=deployment,
        current_manifest_version="manifest-13",
        current_application_version="1.1.0",
    )

    assert compatible.status is UermCompatibilityStatus.COMPATIBLE
    assert outdated.status is UermCompatibilityStatus.OUTDATED
    assert outdated.findings == (
        "application_version_mismatch",
        "manifest_version_mismatch",
    )


def test_r7_uerm_workflow_runtime_rejects_illegal_transitions() -> None:
    deployment = _deployment()
    context = runtime_context(
        request_id="req-00000002",
        correlation_id="corr-00000002",
        tenant="tenant-a",
        user="operator@example.com",
        role="operator",
        permissions=("orders.approve",),
        manifest_version=deployment.manifest_version,
        application_version=deployment.application_version,
    )
    instance = start_workflow_instance(
        index=1,
        deployment_hash=deployment.deployment_hash,
        workflow_key="orders.approval",
        initial_state="draft",
        allowed_transitions={"draft": ("submitted",), "submitted": ("approved",)},
        responsible_actor="operator@example.com",
        context=context,
    )
    submitted = transition_workflow_instance(
        instance,
        next_state="submitted",
        actor="operator@example.com",
        reason="submit for approval",
        pending_actions=("approve",),
    )

    assert submitted.previous_state == "draft"
    assert submitted.current_state == "submitted"
    assert submitted.pending_actions == ("approve",)
    with pytest.raises(ValueError, match="not allowed"):
        transition_workflow_instance(
            submitted,
            next_state="draft",
            actor="operator@example.com",
            reason="illegal rollback",
        )


def test_r7_uerm_standard_errors_recovery_and_digital_twin_are_hashed() -> None:
    deployment = _deployment()
    context = runtime_context(
        request_id="req-00000003",
        correlation_id="corr-00000003",
        tenant="tenant-a",
        user="operator@example.com",
        role="operator",
        permissions=("orders.read",),
        manifest_version=deployment.manifest_version,
        application_version=deployment.application_version,
    )
    error = runtime_error(
        index=1,
        deployment_hash=deployment.deployment_hash,
        severity=UermErrorSeverity.ERROR,
        category=UermErrorCategory.WORKFLOW,
        source="orders.approval",
        correlation_id=context.correlation_id,
        message="Workflow transition rejected.",
        code="WORKFLOW.TRANSITION_REJECTED",
        recovery_guidance="Return to an allowed workflow state.",
        context_hash=context.context_hash,
    )
    action = recovery_action(
        index=1,
        error_hash=error.error_hash,
        strategy=UermRecoveryStrategy.ESCALATION,
    )
    twin = digital_twin_snapshot(
        index=1,
        deployment=deployment,
        health_status=UermHealthStatus.DEGRADED,
        metrics={"error_rate": 1.0},
        configuration={"feature.orders": True},
        active_workflows=("UERM-WF-0001",),
        event_flows=("order.created",),
    )

    assert error.error_hash
    assert action.policy_document["strategy"] == "escalation"
    assert twin.topology["service_identity"] == deployment.service_identity
    assert twin.topology["deployment_location"] == deployment.deployment_location
    assert twin.snapshot_hash


def test_r7_uerm_runtime_providers_policy_dispatch_ai_and_plugins_are_realized() -> None:
    deployment = _deployment()
    context = runtime_context(
        request_id="req-00000004",
        correlation_id="corr-00000004",
        tenant="tenant-a",
        user="operator@example.com",
        role="operator",
        permissions=("orders.read", "runtime.ai.invoke"),
        manifest_version=deployment.manifest_version,
        application_version=deployment.application_version,
    )
    event = runtime_event(
        index=1,
        deployment_hash=deployment.deployment_hash,
        event_type="order.created",
        context=context,
        payload={"order_id": "ORD-001"},
        manifest_rule_ref="manifest.object.order",
    )
    event_bus = register_runtime_provider(
        index=1,
        project_id=deployment.project_id,
        kind=UermRuntimeProviderKind.EVENT_BUS,
        name="local.eventbus",
        version="1",
        status=UermRuntimeProviderStatus.AVAILABLE,
        capabilities=("publish", "subscribe", "publish"),
    )
    dispatch = dispatch_runtime_event(
        index=1,
        event=event,
        provider=event_bus,
        subscriber_refs=("billing.service", "billing.service"),
    )

    assert event_bus.capabilities == ("publish", "subscribe")
    assert dispatch.status is UermRuntimeDispatchStatus.DELIVERED
    assert dispatch.subscriber_refs == ("billing.service",)

    deployment_runtime = register_runtime_provider(
        index=2,
        project_id=deployment.project_id,
        kind=UermRuntimeProviderKind.DEPLOYMENT_RUNTIME,
        name="local.mesh",
        version="1",
        status=UermRuntimeProviderStatus.AVAILABLE,
    )
    sync = sync_runtime_deployment(
        index=1,
        deployment=deployment,
        provider=deployment_runtime,
    )

    assert sync.status is UermRuntimeDispatchStatus.DELIVERED
    assert sync.runtime_document["service_identity"] == deployment.service_identity

    policy = evaluate_runtime_policy(
        index=1,
        deployment_hash=deployment.deployment_hash,
        context=context,
        action="runtime.ai.invoke",
        resource="runtime-ai-service",
        provider_hash=None,
        policy_refs=("uerm.policy.runtime-ai",),
    )
    denied = evaluate_runtime_policy(
        index=2,
        deployment_hash=deployment.deployment_hash,
        context=context,
        action="orders.delete",
        resource="orders",
    )

    assert policy.decision is UermPolicyDecision.ALLOW
    assert denied.decision is UermPolicyDecision.DENY

    ai_provider = register_runtime_provider(
        index=3,
        project_id=deployment.project_id,
        kind=UermRuntimeProviderKind.AI_SERVICE,
        name="local.ai",
        version="1",
        status=UermRuntimeProviderStatus.AVAILABLE,
        capabilities=("analyze_runtime",),
    )
    ai_request = runtime_ai_request(
        index=1,
        deployment_hash=deployment.deployment_hash,
        provider=ai_provider,
        context=context,
        policy_evaluation=policy,
        capability="analyze_runtime",
        prompt="Explain recent order runtime behavior.",
    )

    assert ai_request.status is UermRuntimeAiRequestStatus.ACCEPTED
    assert ai_request.response_document["realization"] == "deterministic_runtime_ai_contract"

    plugin_provider = register_runtime_provider(
        index=4,
        project_id=deployment.project_id,
        kind=UermRuntimeProviderKind.PLUGIN_RUNTIME,
        name="local.plugins",
        version="1",
        status=UermRuntimeProviderStatus.AVAILABLE,
        capabilities=("emit_metrics",),
    )
    binding = bind_runtime_plugin(
        index=1,
        deployment_hash=deployment.deployment_hash,
        provider=plugin_provider,
        plugin_name="orders.metrics",
        plugin_version="1",
        requested_capabilities=("emit_metrics",),
    )

    assert binding.compatibility_status is UermCompatibilityStatus.COMPATIBLE
    assert binding.findings == ()


def test_r7_uerm_runtime_configuration_audit_telemetry_and_governance_are_hashed() -> None:
    deployment = _deployment()
    configuration = runtime_configuration_snapshot(
        index=1,
        deployment_hash=deployment.deployment_hash,
        manifest_version=deployment.manifest_version,
        configuration={
            "database_url": "postgresql://runtime.example/orders",
            "api_token": "secret-token",
            "cache_enabled": True,
        },
        feature_flags={"orders.approval": True, "orders.beta": False},
    )
    audit = runtime_audit_record(
        index=1,
        deployment_hash=deployment.deployment_hash,
        actor="operator@example.com",
        action="orders.update",
        affected_object="orders/ORD-001",
        correlation_id="corr-00000005",
        manifest_rule_ref="manifest.object.order",
        previous_value={"status": "draft"},
        new_value={"status": "submitted"},
    )
    telemetry = runtime_telemetry_batch(
        index=1,
        deployment_hash=deployment.deployment_hash,
        metrics={"response_time_ms": 12.5},
        trace_ids=("trace-2", "trace-1", "trace-1"),
        log_signatures=("order.updated",),
        performance_indicators={"throughput_per_minute": 42.0},
    )
    trace = runtime_governance_trace(
        index=1,
        deployment_hash=deployment.deployment_hash,
        runtime_action_hash=audit.audit_hash,
        business_rule_ref="business-rule.orders.status",
        registry_rule_ref="registry.orders.status-transition",
        manifest_object_ref="manifest.object.order",
        requirement_ref="REQ-ORD-001",
    )

    assert configuration.configuration_document["api_token"] == "<redacted>"
    assert configuration.sensitive_keys == ("api_token",)
    assert audit.previous_value_hash
    assert audit.new_value_hash
    assert telemetry.trace_ids == ("trace-1", "trace-2")
    assert trace.runtime_action_hash == audit.audit_hash


def test_r7_uerm_runtime_synchronization_and_upgrade_plans_are_hashed() -> None:
    deployment = _deployment()

    report = runtime_synchronization_report(
        index=1,
        deployment=deployment,
        current_manifest_version="manifest-13",
        current_application_version="1.1.0",
        observed_runtime={
            "deprecated_apis": ["orders.v1"],
            "obsolete_workflows": ["orders.legacy-approval"],
        },
    )
    plan = runtime_upgrade_plan(
        index=1,
        deployment=deployment,
        synchronization_report=report,
    )
    blocked_report = runtime_synchronization_report(
        index=2,
        deployment=deployment,
        current_manifest_version="manifest-13",
        current_application_version="1.1.0",
        observed_runtime={"missing_migrations": ["orders.status-migration"]},
    )
    blocked_plan = runtime_upgrade_plan(
        index=2,
        deployment=deployment,
        synchronization_report=blocked_report,
    )

    assert report.status is UermCompatibilityStatus.OUTDATED
    assert report.findings == (
        "application_version_mismatch",
        "deprecated_apis",
        "manifest_version_mismatch",
        "obsolete_workflows",
    )
    assert plan.status is UermRuntimeUpgradeStatus.PLANNED
    assert plan.steps[0]["step"] == "impact_analysis"
    assert blocked_report.status is UermCompatibilityStatus.INCOMPATIBLE
    assert blocked_plan.status is UermRuntimeUpgradeStatus.BLOCKED
    assert blocked_plan.blocked_by == ("missing_migrations",)
