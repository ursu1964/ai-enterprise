import pytest
from pydantic import ValidationError

from ai_enterprise.domain.r9_uak import (
    UakCheckpointKind,
    UakCheckpointStatus,
    UakDeploymentEnvironment,
    UakLifecycleState,
    UakPluginCategory,
    UakResourceAllocationStatus,
    UakScheduleStatus,
    UakSdkLanguage,
    UakSubsystem,
    UakTransactionStatus,
    ai_session_boundary,
    deployment_coordination,
    kernel_event,
    kernel_transaction,
    lifecycle_snapshot,
    monitoring_aggregate,
    platform_checkpoint,
    plugin_registration,
    registry_snapshot,
    resource_allocation,
    schedule_plan,
    sdk_contract,
    security_envelope,
    subsystem_registration,
    workspace_hierarchy,
)


def test_r9_uak_subsystem_event_lifecycle_transaction_and_checkpoint_are_hashed() -> None:
    subsystem = subsystem_registration(
        index=1,
        subsystem=UakSubsystem.TRANSFORMATION_MANAGER,
        implementation_ref="ai_enterprise.r5.umte",
        capabilities=(
            "schedule_transformations",
            "dependency_ordering",
            "schedule_transformations",
        ),
        dependencies=(UakSubsystem.REGISTRY_MANAGER, UakSubsystem.MANIFEST_MANAGER),
    )
    event = kernel_event(
        index=1,
        event_type="manifest.updated",
        source_subsystem=UakSubsystem.MANIFEST_MANAGER,
        target_subsystem=UakSubsystem.TRANSFORMATION_MANAGER,
        object_identity="manifest:project-1:v2",
        payload_hash="a" * 64,
    )
    lifecycle = lifecycle_snapshot(
        index=1,
        project_id="project-1",
        object_identity=event.object_identity,
        state=UakLifecycleState.TRANSFORMED,
        triggering_event_hash=event.event_hash,
    )
    transaction = kernel_transaction(
        index=1,
        operation_type="manifest.update",
        object_identity=event.object_identity,
        steps=("validate", "transform", "register"),
        committed_hashes=("b" * 64, "c" * 64, "d" * 64),
    )
    checkpoint = platform_checkpoint(
        index=1,
        checkpoint_kind=UakCheckpointKind.STARTUP,
        completed_steps=(
            "load_registry",
            "load_policies",
            "load_templates",
            "load_plugins",
            "load_knowledge_graph",
            "initialize_ai_providers",
            "initialize_runtime",
            "accept_requests",
        ),
    )

    assert subsystem.capabilities == ("dependency_ordering", "schedule_transformations")
    assert subsystem.dependencies == (
        UakSubsystem.MANIFEST_MANAGER,
        UakSubsystem.REGISTRY_MANAGER,
    )
    assert subsystem.direct_subsystem_communication_allowed is False
    assert event.routed_by_kernel is True
    assert lifecycle.state is UakLifecycleState.TRANSFORMED
    assert transaction.status is UakTransactionStatus.COMMITTED
    assert checkpoint.status is UakCheckpointStatus.READY
    assert checkpoint.missing_steps == ()


def test_r9_uak_plugin_registration_and_ai_session_boundaries_are_governed() -> None:
    plugin = plugin_registration(
        index=1,
        plugin_key="uagf.react-pack",
        category=UakPluginCategory.GENERATOR,
        version="1.0.0",
        capability_refs=("generate.react", "validate.typescript", "generate.react"),
        extension_points=(UakSubsystem.ARTIFACT_MANAGER, UakSubsystem.PLUGIN_MANAGER),
        signed_artifact_hash="f" * 64,
    )
    boundary = ai_session_boundary(
        index=1,
        model_ref="openai:gpt-5.6",
        approved_context_refs=("manifest:project-1:v2",),
        approved_registry_refs=("registry:updl:v1",),
        approved_object_refs=("object:customer", "object:order"),
        approved_template_refs=("template:service.react",),
        approved_permission_refs=("ai.generate.report", "ai.summarize.risk"),
    )

    assert plugin.modifies_kernel is False
    assert plugin.capability_refs == ("generate.react", "validate.typescript")
    assert plugin.extension_points == (
        UakSubsystem.ARTIFACT_MANAGER,
        UakSubsystem.PLUGIN_MANAGER,
    )
    assert boundary.unrestricted_platform_access is False
    assert boundary.approved_permission_refs == ("ai.generate.report", "ai.summarize.risk")

    with pytest.raises(ValidationError, match="never modify the kernel"):
        type(plugin).model_validate({**plugin.model_dump(mode="json"), "modifies_kernel": True})

    with pytest.raises(ValidationError, match="unrestricted platform access"):
        type(boundary).model_validate(
            {**boundary.model_dump(mode="json"), "unrestricted_platform_access": True}
        )

    with pytest.raises(ValidationError, match="approved context and registry"):
        ai_session_boundary(
            index=2,
            model_ref="openai:gpt-5.6",
            approved_context_refs=(),
            approved_registry_refs=("registry:updl:v1",),
            approved_permission_refs=("ai.generate.report",),
        )


def test_r9_uak_workspace_scheduling_resource_and_sdk_records_are_governed() -> None:
    hierarchy = workspace_hierarchy(
        index=1,
        tenant_ref="tenant:acme",
        workspace_ref="workspace:engineering",
        portfolio_ref="portfolio:commerce",
        project_ref="project:orders",
        manifest_ref="manifest:orders:v2",
        reusable_knowledge_refs=("pattern:commerce", "template:order-service", "pattern:commerce"),
    )
    blocked_schedule = schedule_plan(
        index=1,
        work_type="artifact.generation",
        object_identity="manifest:orders:v2",
        dependencies=("transform:orders", "validate:orders"),
        unsatisfied_dependencies=("validate:orders",),
        resource_claims={"compute": 4.0, "memory": 8.0},
    )
    dispatchable_schedule = schedule_plan(
        index=2,
        work_type="governance.validation",
        object_identity="manifest:orders:v2",
        dependencies=("transform:orders",),
        resource_claims={"compute": 1.0},
    )
    allocation = resource_allocation(
        index=1,
        schedule_ref=dispatchable_schedule.schedule_id,
        requested_resources={"compute": 1.0, "memory": 2.0},
        allocated_resources={"compute": 1.0, "memory": 2.0},
    )
    insufficient = resource_allocation(
        index=2,
        schedule_ref=blocked_schedule.schedule_id,
        requested_resources={"compute": 4.0},
        allocated_resources={"compute": 2.0},
    )
    sdk = sdk_contract(
        index=1,
        language=UakSdkLanguage.PYTHON,
        contract_version="1.0",
        api_surfaces=("governance", "manifest", "runtime", "governance"),
        canonical_contract_hash="1" * 64,
        package_ref="pypi://ai-enterprise-kernel-sdk@1.0",
    )

    assert hierarchy.isolation_guaranteed is True
    assert hierarchy.customer_data_shared is False
    assert hierarchy.reusable_knowledge_refs == ("pattern:commerce", "template:order-service")
    assert blocked_schedule.status is UakScheduleStatus.BLOCKED
    assert dispatchable_schedule.status is UakScheduleStatus.DISPATCHABLE
    assert allocation.status is UakResourceAllocationStatus.ALLOCATED
    assert insufficient.status is UakResourceAllocationStatus.INSUFFICIENT
    assert sdk.api_surfaces == ("governance", "manifest", "runtime")

    with pytest.raises(ValidationError, match="may not share customer data"):
        type(hierarchy).model_validate(
            {**hierarchy.model_dump(mode="json"), "customer_data_shared": True}
        )

    with pytest.raises(ValidationError, match="declared dependencies"):
        schedule_plan(
            index=3,
            work_type="artifact.generation",
            object_identity="manifest:orders:v2",
            dependencies=("transform:orders",),
            unsatisfied_dependencies=("validate:orders",),
            resource_claims={"compute": 1.0},
        )

    with pytest.raises(ValidationError, match="must be dynamic"):
        type(allocation).model_validate(
            {**allocation.model_dump(mode="json"), "dynamic_allocation": False}
        )


def test_r9_uak_registry_security_deployment_and_monitoring_managers_are_governed() -> None:
    registry = registry_snapshot(
        index=1,
        updl_registry_hash="1" * 64,
        object_registry_hash="2" * 64,
        rule_registry_hash="3" * 64,
        generator_registry_hash="4" * 64,
        template_registry_hash="5" * 64,
        policy_registry_hash="6" * 64,
    )
    security = security_envelope(
        index=1,
        actor_identity_ref="actor:platform-admin",
        authorization_policy_refs=("policy:kernel-admin", "policy:kernel-admin"),
        certificate_refs=("cert:platform",),
        secret_refs=("secret:provider-token",),
    )
    deployment = deployment_coordination(
        index=1,
        environment=UakDeploymentEnvironment.PRODUCTION,
        manifest_ref="manifest:orders:v2",
        deployment_provider_ref="provider:kubernetes",
        runtime_ref="runtime:orders:prod",
        deployment_hashes=("7" * 64, "7" * 64),
    )
    monitoring = monitoring_aggregate(
        index=1,
        metrics_by_domain={
            "runtime": 92.0,
            "generation": 88.0,
            "ai": 80.0,
            "governance": 97.0,
            "infrastructure": 84.0,
        },
        source_record_hashes=(registry.registry_hash, security.security_hash),
    )

    assert registry.execution_outside_registry_allowed is False
    assert security.secrets_redacted is True
    assert security.authorization_policy_refs == ("policy:kernel-admin",)
    assert deployment.manifest_aware is True
    assert deployment.deployment_hashes == ("7" * 64,)
    assert monitoring.unified_operational_view is True

    with pytest.raises(ValidationError, match="outside the registry"):
        type(registry).model_validate(
            {**registry.model_dump(mode="json"), "execution_outside_registry_allowed": True}
        )

    with pytest.raises(ValidationError, match="encryption, redaction, and policy"):
        type(security).model_validate(
            {**security.model_dump(mode="json"), "secrets_redacted": False}
        )

    with pytest.raises(ValidationError, match="Manifest-aware"):
        type(deployment).model_validate(
            {**deployment.model_dump(mode="json"), "manifest_aware": False}
        )

    with pytest.raises(ValidationError, match="runtime/generation/AI/governance/infrastructure"):
        monitoring_aggregate(
            index=2,
            metrics_by_domain={"runtime": 92.0},
            source_record_hashes=(registry.registry_hash,),
        )


def test_r9_uak_rejects_direct_subsystem_access_partial_transactions_and_bad_checkpoints() -> None:
    subsystem = subsystem_registration(
        index=1,
        subsystem=UakSubsystem.ARTIFACT_MANAGER,
        implementation_ref="ai_enterprise.r6.uagf",
        capabilities=("render",),
    )
    with pytest.raises(ValidationError, match="through the kernel"):
        type(subsystem).model_validate(
            {
                **subsystem.model_dump(mode="json"),
                "direct_subsystem_communication_allowed": True,
            }
        )

    with pytest.raises(ValidationError, match="distinct source and target"):
        kernel_event(
            index=1,
            event_type="generation.completed",
            source_subsystem=UakSubsystem.ARTIFACT_MANAGER,
            target_subsystem=UakSubsystem.ARTIFACT_MANAGER,
            object_identity="artifact:api",
            payload_hash="a" * 64,
        )

    transaction = kernel_transaction(
        index=1,
        operation_type="manifest.update",
        object_identity="manifest:project-1:v2",
        steps=("validate", "transform"),
        rollback_steps=("rollback_transform",),
        rolled_back_hashes=("e" * 64,),
    )
    assert transaction.status is UakTransactionStatus.ROLLED_BACK

    with pytest.raises(ValidationError, match="commit every step"):
        type(transaction).model_validate(
            {
                **transaction.model_dump(mode="json"),
                "status": "committed",
                "committed_hashes": ("e" * 64,),
                "rolled_back_hashes": (),
            }
        )

    checkpoint = platform_checkpoint(
        index=1,
        checkpoint_kind=UakCheckpointKind.SHUTDOWN,
        completed_steps=("complete_transactions", "persist_events"),
    )
    assert checkpoint.status is UakCheckpointStatus.BLOCKED
    assert checkpoint.missing_steps == (
        "preserve_state",
        "synchronize_runtime",
        "write_recovery_checkpoints",
    )

    with pytest.raises(ValidationError, match="preserve platform state"):
        type(checkpoint).model_validate(
            {**checkpoint.model_dump(mode="json"), "state_preserved": False}
        )
