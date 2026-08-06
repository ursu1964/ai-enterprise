from __future__ import annotations

from ai_enterprise.application.r11_uief_runtime import (
    UiefRecordView,
    analyze_compatibility,
    analyze_integration_impact,
    assess_ecosystem_readiness,
    build_generation_plan,
    build_migration_plan,
    build_sandbox_plan,
    build_test_plan,
    build_topology_map,
    describe_developer_surface,
    generate_integration_documentation,
    r11_deployment_preflight,
    reconcile_integrations,
    summarize_observability,
    validate_security_readiness,
)
from ai_enterprise.config import Settings
from ai_enterprise.domain.r11_uief import (
    UiefCertificationLevel,
    UiefHealthStatus,
    UiefIntegrationDomain,
    connector_registration,
    digital_twin,
    integration_object,
    marketplace_asset,
    retry_policy,
    security_policy,
)


def _view(record_type: str, document: dict[str, object], record_hash: str) -> UiefRecordView:
    return UiefRecordView(
        record_type=record_type,
        record_id=str(
            document.get("integration_id")
            or document.get("connector_id")
            or document.get("contract_id")
            or document.get("mapping_id")
            or document.get("event_id")
            or document.get("retry_policy_id")
            or document.get("security_policy_id")
            or document.get("twin_id")
            or document.get("asset_id")
            or document.get("provider_id")
            or document.get("ai_boundary_id")
            or "record"
        ),
        integration_ref=document.get("integration_ref")
        if isinstance(document.get("integration_ref"), str)
        else None,
        lifecycle_state=document.get("lifecycle_state")
        if isinstance(document.get("lifecycle_state"), str)
        else None,
        health_status=document.get("health") if isinstance(document.get("health"), str) else None,
        record_document=document,
        record_hash=record_hash,
    )


def test_r11_runtime_detects_missing_compatibility_references() -> None:
    integration = integration_object(
        integration_id="UIEF-INT-0001",
        manifest_ref="manifest:orders",
        name="CRM customer sync",
        domain=UiefIntegrationDomain.DATA,
        source_ref="system:crm",
        destination_ref="domain:customer",
        purpose="Synchronize customer data.",
        protocol="rest",
        contract_ref="UIEF-CTR-0001",
        authentication_ref="UIEF-SEC-0001",
        authorization_ref="scope:customer.sync",
        mapping_ref="UIEF-MAP-0001",
        trigger="customer.changed",
        frequency="event-driven",
        error_strategy_ref="error:standard",
        retry_policy_ref="UIEF-RETRY-0001",
        owner_ref="team:integration",
        monitoring_ref="monitor:customer",
        compliance_classification="confidential",
    )

    report = analyze_compatibility(
        [_view("integration", integration.model_dump(mode="json"), integration.integration_hash)]
    )

    assert report.compatible is False
    assert report.findings[0].integration_ref == "UIEF-INT-0001"
    assert "UIEF-CTR-0001" in report.findings[0].findings[0]


def test_r11_runtime_builds_generation_and_certification_test_plans() -> None:
    integration = integration_object(
        integration_id="UIEF-INT-0001",
        manifest_ref="manifest:orders",
        name="Order events",
        domain=UiefIntegrationDomain.EVENT,
        source_ref="system:crm",
        destination_ref="service:orders",
        purpose="Publish order events.",
        protocol="kafka",
        contract_ref="UIEF-CTR-0001",
        authentication_ref="UIEF-SEC-0001",
        authorization_ref="UIEF-SEC-0001",
        mapping_ref="UIEF-MAP-0001",
        trigger="order.changed",
        frequency="streaming",
        error_strategy_ref="error:standard",
        retry_policy_ref="UIEF-RETRY-0001",
        owner_ref="team:integration",
        monitoring_ref="monitor:orders",
        compliance_classification="internal",
    )
    retry = retry_policy(
        retry_policy_id="UIEF-RETRY-0001",
        maximum_attempts=3,
        delay_seconds=1,
        retryable_errors=("timeout",),
        timeout_seconds=30,
        escalation_ref="incident:orders",
        dead_letter_destination="dlq:orders",
    )
    records = [
        _view("integration", integration.model_dump(mode="json"), integration.integration_hash),
        _view("contract", {"contract_id": "UIEF-CTR-0001"}, "a" * 64),
        _view("mapping", {"mapping_id": "UIEF-MAP-0001"}, "b" * 64),
        _view("security_policy", {"security_policy_id": "UIEF-SEC-0001"}, "c" * 64),
        _view("retry_policy", retry.model_dump(mode="json"), retry.retry_hash),
    ]

    generation = build_generation_plan(records)
    tests = build_test_plan(records)

    assert "event_consumer" in generation.artifact_plans[0].artifacts
    assert "event_producer" in generation.artifact_plans[0].artifacts
    assert "contract" in tests.test_plans[0].tests
    assert tests.certification_ready is True


def test_r11_runtime_reconciles_unhealthy_twins_and_summarizes_observability() -> None:
    twin = digital_twin(
        twin_id="UIEF-TWIN-0001",
        integration_ref="UIEF-INT-0001",
        deployed_connector_ref="UIEF-CONN-0001",
        active_version="1.0.0",
        endpoint_ref="endpoint:orders",
        dependency_refs=("contract:orders",),
        health=UiefHealthStatus.DEGRADED,
        performance_metrics={
            "request_count": 100,
            "success_rate": 0.95,
            "error_rate": 0.05,
            "latency": 42,
            "throughput": 10,
            "retry_count": 3,
            "queue_depth": 2,
            "rejected_payloads": 1,
            "contract_violations": 1,
            "dependency_availability": 0.9,
        },
        data_flow_refs=("flow:orders",),
        contract_status="drifted",
        security_status="valid",
    )
    records = [_view("digital_twin", twin.model_dump(mode="json"), twin.twin_hash)]

    reconciliation = reconcile_integrations(records)
    observability = summarize_observability(records)

    assert reconciliation.difference_count == 2
    assert observability.degraded_count == 1
    assert observability.metrics["request_count"] == 100


def test_r11_runtime_builds_live_topology_map_for_integrations_and_twins() -> None:
    integration = integration_object(
        integration_id="UIEF-INT-0001",
        manifest_ref="manifest:orders",
        name="Order events",
        domain=UiefIntegrationDomain.EVENT,
        source_ref="system:crm",
        destination_ref="service:orders",
        purpose="Publish order events.",
        protocol="kafka",
        contract_ref="UIEF-CTR-0001",
        authentication_ref="UIEF-SEC-0001",
        authorization_ref="UIEF-SEC-0001",
        mapping_ref="UIEF-MAP-0001",
        trigger="order.changed",
        frequency="streaming",
        error_strategy_ref="error:standard",
        retry_policy_ref="UIEF-RETRY-0001",
        owner_ref="team:integration",
        monitoring_ref="monitor:orders",
        compliance_classification="internal",
    )
    twin = digital_twin(
        twin_id="UIEF-TWIN-0001",
        integration_ref="UIEF-INT-0001",
        deployed_connector_ref="UIEF-CONN-0001",
        active_version="1.0.0",
        endpoint_ref="endpoint:orders",
        dependency_refs=("contract:orders",),
        health=UiefHealthStatus.HEALTHY,
        performance_metrics={"request_count": 1},
        data_flow_refs=("flow:orders",),
        contract_status="compatible",
        security_status="valid",
    )
    records = [
        _view("integration", integration.model_dump(mode="json"), integration.integration_hash),
        _view("digital_twin", twin.model_dump(mode="json"), twin.twin_hash),
    ]

    topology = build_topology_map(records)
    node_ids = {node.node_id for node in topology.nodes}
    edges = {
        (edge.source, edge.target, edge.relationship, edge.integration_ref)
        for edge in topology.edges
    }

    assert {"UIEF-INT-0001", "system:crm", "service:orders", "UIEF-CONN-0001"}.issubset(
        node_ids
    )
    assert ("system:crm", "UIEF-INT-0001", "feeds", "UIEF-INT-0001") in edges
    assert (
        "UIEF-INT-0001",
        "service:orders",
        "delivers_to",
        "UIEF-INT-0001",
    ) in edges
    assert (
        "UIEF-INT-0001",
        "UIEF-CONN-0001",
        "deployed_as",
        "UIEF-INT-0001",
    ) in edges
    assert topology.topology_hash


def test_r11_runtime_generates_integration_documentation_bundle() -> None:
    integration = integration_object(
        integration_id="UIEF-INT-0001",
        manifest_ref="manifest:orders",
        name="Order events",
        domain=UiefIntegrationDomain.EVENT,
        source_ref="system:crm",
        destination_ref="service:orders",
        purpose="Publish order events.",
        protocol="kafka",
        contract_ref="UIEF-CTR-0001",
        authentication_ref="UIEF-SEC-0001",
        authorization_ref="UIEF-SEC-0001",
        mapping_ref="UIEF-MAP-0001",
        trigger="order.changed",
        frequency="streaming",
        error_strategy_ref="error:standard",
        retry_policy_ref="UIEF-RETRY-0001",
        owner_ref="team:integration",
        monitoring_ref="monitor:orders",
        compliance_classification="internal",
    )
    retry = retry_policy(
        retry_policy_id="UIEF-RETRY-0001",
        maximum_attempts=3,
        delay_seconds=1,
        retryable_errors=("timeout",),
        timeout_seconds=30,
        escalation_ref="incident:orders",
        dead_letter_destination="dlq:orders",
    )
    records = [
        _view("integration", integration.model_dump(mode="json"), integration.integration_hash),
        _view("contract", {"contract_id": "UIEF-CTR-0001"}, "a" * 64),
        _view("mapping", {"mapping_id": "UIEF-MAP-0001"}, "b" * 64),
        _view("security_policy", {"security_policy_id": "UIEF-SEC-0001"}, "c" * 64),
        _view("retry_policy", retry.model_dump(mode="json"), retry.retry_hash),
    ]

    bundle = generate_integration_documentation(records)
    document = bundle.documents[0]

    assert bundle.document_count == 1
    assert document.integration_ref == "UIEF-INT-0001"
    assert {
        "business_purpose",
        "participating_systems",
        "data_exchanged",
        "contracts",
        "mapping",
        "authentication",
        "authorization",
        "error_handling",
        "retry_policy",
        "support_ownership",
        "testing",
        "monitoring",
        "lifecycle",
        "change_history",
    } == set(document.sections)
    assert "Certification test plan is ready." == document.sections["testing"]
    assert integration.integration_hash in document.source_record_hashes
    assert bundle.bundle_hash


def test_r11_runtime_builds_sandbox_plan_with_virtualized_behaviors() -> None:
    integration = integration_object(
        integration_id="UIEF-INT-0001",
        manifest_ref="manifest:orders",
        name="Order events",
        domain=UiefIntegrationDomain.EVENT,
        source_ref="system:crm",
        destination_ref="service:orders",
        purpose="Publish order events.",
        protocol="kafka",
        contract_ref="UIEF-CTR-0001",
        authentication_ref="UIEF-SEC-0001",
        authorization_ref="UIEF-SEC-0001",
        mapping_ref="UIEF-MAP-0001",
        trigger="order.changed",
        frequency="streaming",
        error_strategy_ref="error:standard",
        retry_policy_ref="UIEF-RETRY-0001",
        owner_ref="team:integration",
        monitoring_ref="monitor:orders",
        compliance_classification="internal",
    )
    connector = connector_registration(
        connector_id="UIEF-CONN-0001",
        provider="internal",
        supported_system="crm",
        version="1.0.0",
        protocols=("kafka",),
        authentication_methods=("oauth2",),
        operations=(
            "authenticate",
            "configure",
            "discover",
            "observe",
            "read",
            "recover",
            "transform",
            "validate",
            "write",
        ),
        rate_limits={"requests_per_minute": 120},
        data_classifications=("internal",),
        certification_level=UiefCertificationLevel.CERTIFIED,
        compatibility_refs=("UIEF-INT-0001",),
        owner_ref="team:integration",
        lifecycle_status="certified",
    )
    twin = digital_twin(
        twin_id="UIEF-TWIN-0001",
        integration_ref="UIEF-INT-0001",
        deployed_connector_ref="UIEF-CONN-0001",
        active_version="1.0.0",
        endpoint_ref="endpoint:orders",
        dependency_refs=("contract:orders",),
        health=UiefHealthStatus.HEALTHY,
        performance_metrics={"request_count": 1},
        data_flow_refs=("flow:orders",),
        contract_status="compatible",
        security_status="valid",
    )
    records = [
        _view("integration", integration.model_dump(mode="json"), integration.integration_hash),
        _view("connector", connector.model_dump(mode="json"), connector.connector_hash),
        _view(
            "contract",
            {"contract_id": "UIEF-CTR-0001", "operations": ["publishOrder"]},
            "a" * 64,
        ),
        _view("digital_twin", twin.model_dump(mode="json"), twin.twin_hash),
    ]

    report = build_sandbox_plan(records)
    plan = report.sandbox_plans[0]

    assert report.ready_for_isolated_testing is True
    assert "event_streams" in plan.virtualized_behaviors
    assert "malformed_payloads" in plan.virtualized_behaviors
    assert "simulated_credentials" in plan.sandbox_assets
    assert "test_contracts" in plan.sandbox_assets
    assert "publishOrder" in plan.limited_operations
    assert plan.controlled_rate_limits["requests_per_minute"] == 120


def test_r11_runtime_security_readiness_blocks_secret_and_idempotency_violations() -> None:
    integration = integration_object(
        integration_id="UIEF-INT-0001",
        manifest_ref="manifest:payments",
        name="Payment transaction sync",
        domain=UiefIntegrationDomain.API,
        source_ref="system:billing",
        destination_ref="service:ledger",
        purpose="Synchronize critical payment transactions.",
        protocol="rest",
        contract_ref="UIEF-CTR-0001",
        authentication_ref="UIEF-SEC-0001",
        authorization_ref="UIEF-SEC-0001",
        mapping_ref="UIEF-MAP-0001",
        trigger="payment.captured",
        frequency="event-driven",
        error_strategy_ref="error:standard",
        retry_policy_ref="UIEF-RETRY-0001",
        owner_ref="team:payments",
        monitoring_ref="monitor:payments",
        compliance_classification="financial",
    )
    insecure = (
        security_policy(
            security_policy_id="UIEF-SEC-0001",
            identity_strength="password",
            credential_ref="inline:plain-secret",
            transport_encryption="tls1.2",
            authorization_scope_refs=("scope:payments",),
            data_protection_rules=("mask:card",),
            residency_rules=("region:eu",),
            logging_safety_rules=("redact:payload",),
        ).model_dump(mode="json")
        | {"secret_values_embedded": True}
    )
    retry = retry_policy(
        retry_policy_id="UIEF-RETRY-0001",
        maximum_attempts=3,
        delay_seconds=1,
        retryable_errors=("timeout",),
        timeout_seconds=30,
        escalation_ref="incident:payments",
        dead_letter_destination="dlq:payments",
    ).model_dump(mode="json") | {"idempotency_required": False}
    records = [
        _view("integration", integration.model_dump(mode="json"), integration.integration_hash),
        _view("contract", {"contract_id": "UIEF-CTR-0001"}, "a" * 64),
        _view("mapping", {"mapping_id": "UIEF-MAP-0001"}, "b" * 64),
        _view("security_policy", insecure, "c" * 64),
        _view("retry_policy", retry, "d" * 64),
    ]

    report = validate_security_readiness(records)
    categories = {finding.category for finding in report.findings}

    assert report.activation_allowed is False
    assert {"credential_handling", "idempotency"}.issubset(categories)


def test_r11_runtime_analyzes_change_impact_for_contract_refs() -> None:
    integration = integration_object(
        integration_id="UIEF-INT-0001",
        manifest_ref="manifest:orders",
        name="Order API",
        domain=UiefIntegrationDomain.API,
        source_ref="partner:storefront",
        destination_ref="service:orders",
        purpose="Expose governed order API.",
        protocol="rest",
        contract_ref="UIEF-CTR-0001",
        authentication_ref="UIEF-SEC-0001",
        authorization_ref="UIEF-SEC-0001",
        mapping_ref="UIEF-MAP-0001",
        trigger="request",
        frequency="real-time",
        error_strategy_ref="error:standard",
        retry_policy_ref="UIEF-RETRY-0001",
        owner_ref="team:integration",
        monitoring_ref="monitor:orders",
        compliance_classification="internal",
    )
    twin = digital_twin(
        twin_id="UIEF-TWIN-0001",
        integration_ref="UIEF-INT-0001",
        deployed_connector_ref="UIEF-CONN-0001",
        active_version="1.0.0",
        endpoint_ref="endpoint:orders-api",
        dependency_refs=("service:payments",),
        health=UiefHealthStatus.HEALTHY,
        performance_metrics={"request_count": 1},
        data_flow_refs=("flow:orders",),
        contract_status="compatible",
        security_status="valid",
    )
    records = [
        _view("integration", integration.model_dump(mode="json"), integration.integration_hash),
        _view(
            "contract",
            {"contract_id": "UIEF-CTR-0001", "contract_type": "openapi"},
            "a" * 64,
        ),
        _view(
            "mapping",
            {"mapping_id": "UIEF-MAP-0001", "test_refs": ["test:mapping"]},
            "b" * 64,
        ),
        _view(
            "event",
            {"event_id": "UIEF-EVT-0001", "consumer_refs": ["service:warehouse"]},
            "c" * 64,
        ),
        _view("digital_twin", twin.model_dump(mode="json"), twin.twin_hash),
    ]

    report = analyze_integration_impact(records, changed_ref="UIEF-CTR-0001")
    impact = report.impacts[0]

    assert report.impact_count == 1
    assert impact.integration_ref == "UIEF-INT-0001"
    assert impact.changed_ref == "UIEF-CTR-0001"
    assert "api_client:UIEF-INT-0001" in impact.api_clients
    assert "service:payments" in impact.dependent_services
    assert "UIEF-MAP-0001" in impact.mappings
    assert "test:mapping" in impact.tests
    assert "endpoint:orders-api" in impact.runtime_deployments


def test_r11_runtime_builds_legacy_migration_plan() -> None:
    integration = integration_object(
        integration_id="UIEF-INT-0001",
        manifest_ref="manifest:legacy",
        name="Legacy order migration",
        domain=UiefIntegrationDomain.FILE,
        source_ref="legacy:mainframe-orders",
        destination_ref="service:orders",
        purpose="Migrate legacy order records with parallel run and cutover.",
        protocol="file",
        contract_ref="UIEF-CTR-0001",
        authentication_ref="UIEF-SEC-0001",
        authorization_ref="UIEF-SEC-0001",
        mapping_ref="UIEF-MAP-0001",
        trigger="batch",
        frequency="nightly",
        error_strategy_ref="error:standard",
        retry_policy_ref="UIEF-RETRY-0001",
        owner_ref="team:integration",
        monitoring_ref="monitor:legacy-orders",
        compliance_classification="regulated",
    )
    records = [
        _view("integration", integration.model_dump(mode="json"), integration.integration_hash),
        _view("mapping", {"mapping_id": "UIEF-MAP-0001"}, "b" * 64),
    ]

    report = build_migration_plan(records)
    plan = report.migration_plans[0]

    assert report.migration_count == 1
    assert plan.strategy == "file_exchange"
    assert plan.rollback_required is True
    assert plan.parallel_run_required is True
    assert [stage.stage for stage in plan.stages] == [
        "discover",
        "model",
        "map",
        "validate",
        "synchronize",
        "parallel_run",
        "cut_over",
        "retire",
    ]


def test_r11_runtime_assesses_ecosystem_readiness_boundaries() -> None:
    integration = integration_object(
        integration_id="UIEF-INT-0001",
        manifest_ref="manifest:partner",
        name="Partner order API",
        domain=UiefIntegrationDomain.API,
        source_ref="partner:storefront",
        destination_ref="service:orders",
        purpose="Exchange minimal partner order data.",
        protocol="rest",
        contract_ref="UIEF-CTR-0001",
        authentication_ref="UIEF-SEC-0001",
        authorization_ref="UIEF-SEC-0001",
        mapping_ref="UIEF-MAP-0001",
        trigger="request",
        frequency="real-time",
        error_strategy_ref="error:standard",
        retry_policy_ref="UIEF-RETRY-0001",
        owner_ref="team:partners",
        monitoring_ref="monitor:partner-orders",
        compliance_classification="confidential",
    )
    connector = connector_registration(
        connector_id="UIEF-CONN-0001",
        provider="internal",
        supported_system="partner-api",
        version="1.0.0",
        protocols=("rest",),
        authentication_methods=("oauth2",),
        operations=(
            "authenticate",
            "configure",
            "discover",
            "observe",
            "read",
            "recover",
            "transform",
            "validate",
            "write",
        ),
        rate_limits={"requests_per_minute": 60},
        data_classifications=("confidential",),
        certification_level=UiefCertificationLevel.ENTERPRISE_CERTIFIED,
        compatibility_refs=("UIEF-INT-0001",),
        owner_ref="team:partners",
        lifecycle_status="certified",
    )
    security = security_policy(
        security_policy_id="UIEF-SEC-0001",
        identity_strength="mfa",
        credential_ref="secret-ref:partner-oauth",
        transport_encryption="tls1.3",
        authorization_scope_refs=("scope:partner.orders",),
        data_protection_rules=("mask:email",),
        residency_rules=("region:eu",),
        logging_safety_rules=("redact:payload",),
    )
    twin = digital_twin(
        twin_id="UIEF-TWIN-0001",
        integration_ref="UIEF-INT-0001",
        deployed_connector_ref="UIEF-CONN-0001",
        active_version="1.0.0",
        endpoint_ref="endpoint:partner-orders",
        dependency_refs=("service:orders",),
        health=UiefHealthStatus.HEALTHY,
        performance_metrics={"request_count": 1},
        data_flow_refs=("flow:partner-orders",),
        contract_status="compatible",
        security_status="valid",
    )
    asset = marketplace_asset(
        asset_id="UIEF-ASSET-0001",
        asset_type="connector",
        creator_ref="partner:storefront",
        publisher_ref="partner:storefront",
        version="1.0.0",
        source_ref="git:partner-connector",
        dependency_refs=("runtime:python",),
        license_ref="license:enterprise",
        signature_ref="sig:ed25519",
        certification_level=UiefCertificationLevel.ENTERPRISE_CERTIFIED,
        compatibility_refs=("UIEF-INT-0001",),
    )
    records = [
        _view("integration", integration.model_dump(mode="json"), integration.integration_hash),
        _view("connector", connector.model_dump(mode="json"), connector.connector_hash),
        _view("security_policy", security.model_dump(mode="json"), security.security_hash),
        _view("contract", {"contract_id": "UIEF-CTR-0001"}, "a" * 64),
        _view("mapping", {"mapping_id": "UIEF-MAP-0001"}, "b" * 64),
        _view("digital_twin", twin.model_dump(mode="json"), twin.twin_hash),
        _view("marketplace_asset", asset.model_dump(mode="json"), asset.asset_hash),
    ]

    report = assess_ecosystem_readiness(records)

    assert report.production_ready is True
    assert report.connector_registry_ready is True
    assert report.gateway_ready is True
    assert report.marketplace_ready is True
    assert report.partner_ready is True
    assert report.data_governance_ready is True
    assert report.finding_count == 0


def test_r11_runtime_developer_surface_exposes_kernel_managed_cli_capabilities() -> None:
    report = describe_developer_surface()

    assert report.ready_for_external_developers is True
    assert report.cli_capabilities == (
        "discover",
        "validate",
        "generate",
        "test",
        "publish",
        "activate",
        "observe",
        "deactivate",
    )
    assert all(command.kernel_managed for command in report.commands)
    assert "connector_development_kit" in report.sdk_surfaces
    assert "security_readiness_report" in report.validation_tools
    assert "human_approval_gate" in report.certification_pipeline


def test_r11_deployment_preflight_requires_configured_external_services() -> None:
    missing = Settings(
        _env_file=None,
        r11_external_integration_mode="configured",
    )
    ready = Settings(
        _env_file=None,
        r11_external_integration_mode="configured",
        r11_external_endpoint_allowlist="https://partner.example.com,https://api.vendor.example",
        r11_external_credential_refs="secret-ref:partner-oauth,mounted-secret:vendor-api",
        r11_partner_trust_refs="partner-agreement:storefront",
        r11_gateway_base_url="https://gateway.internal.example",
        r11_secrets_manager_ref="vault:ai-enterprise/r11",
    )
    unsafe = Settings(
        _env_file=None,
        r11_external_integration_mode="configured",
        r11_external_endpoint_allowlist="https://partner.example.com",
        r11_external_credential_refs="token=raw-secret",
        r11_partner_trust_refs="partner-agreement:storefront",
        r11_gateway_base_url="https://gateway.internal.example",
        r11_secrets_manager_ref="vault:ai-enterprise/r11",
    )

    assert r11_deployment_preflight(missing).production_operational is False
    assert r11_deployment_preflight(unsafe).credential_refs_ready is False
    assert r11_deployment_preflight(ready).production_operational is True
