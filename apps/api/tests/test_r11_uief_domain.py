from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_enterprise.domain.r11_uief import (
    UiefCertificationLevel,
    UiefContractType,
    UiefHealthStatus,
    UiefIntegrationDomain,
    UiefIntegrationLifecycle,
    ai_integration_boundary,
    connector_registration,
    contract_registration,
    data_mapping,
    digital_twin,
    event_definition,
    integration_object,
    marketplace_asset,
    provider_abstraction,
    retry_policy,
    security_policy,
)


def test_r11_integration_object_is_manifest_owned_and_approval_gated() -> None:
    integration = integration_object(
        integration_id="UIEF-INT-0001",
        manifest_ref="manifest:orders",
        name="CRM customer sync",
        domain=UiefIntegrationDomain.DATA,
        source_ref="system:crm",
        destination_ref="domain:customer",
        purpose="Synchronize governed customer data.",
        protocol="rest",
        contract_ref="contract:customer:1.0.0",
        authentication_ref="auth:oauth",
        authorization_ref="scope:customer.sync",
        mapping_ref="mapping:customer",
        trigger="customer.changed",
        frequency="event-driven",
        error_strategy_ref="error:standard",
        retry_policy_ref="retry:customer",
        owner_ref="team:integration",
        monitoring_ref="monitor:customer-sync",
        compliance_classification="confidential",
    )

    assert integration.manifest_owned is True
    assert integration.lifecycle_state is UiefIntegrationLifecycle.PROPOSED
    assert integration.integration_hash

    with pytest.raises(ValidationError, match="activation requires explicit approval"):
        integration_object(
            **integration.model_dump(exclude={"integration_hash"})
            | {
                "lifecycle_state": UiefIntegrationLifecycle.ACTIVATED,
                "approved_for_activation": False,
            }
        )


def test_r11_connector_contract_mapping_event_retry_and_security_invariants() -> None:
    connector = connector_registration(
        connector_id="UIEF-CONN-0001",
        provider="internal",
        supported_system="crm",
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
        rate_limits={"requests_per_minute": 600},
        data_classifications=("confidential",),
        certification_level=UiefCertificationLevel.CERTIFIED,
        compatibility_refs=("crm:v3",),
        owner_ref="team:integration",
        lifecycle_status="certified",
    )
    contract = contract_registration(
        contract_id="UIEF-CTR-0001",
        manifest_ref="manifest:orders",
        contract_type=UiefContractType.OPENAPI,
        contract_version="1.0.0",
        operations=("getCustomer", "upsertCustomer"),
        schema_refs=("schema:customer",),
        error_refs=("error:standard",),
        security_requirement_refs=("security:oauth",),
        slo_refs=("slo:customer-sync",),
        compatibility_rules=("semver:minor-compatible",),
    )
    mapping = data_mapping(
        mapping_id="UIEF-MAP-0001",
        integration_ref="UIEF-INT-0001",
        canonical_model_ref="canonical:customer",
        field_mappings=(
            {
                "external_field": "cust_no",
                "canonical_field": "Customer.Identifier",
                "rule": "rename",
            },
        ),
        transformation_rules=("normalize:identifier",),
        test_refs=("test:mapping",),
        version="1.0.0",
    )
    event = event_definition(
        event_id="UIEF-EVT-0001",
        event_name="Customer.Registered",
        producer_ref="system:crm",
        consumer_refs=("service:customer",),
        schema_ref="schema:customer-event",
        version="1.0.0",
        partition_key="customer_id",
        delivery_semantics="effectively_once",
        retention="30d",
        sensitivity="confidential",
        retry_policy_ref="retry:customer",
        dead_letter_strategy_ref="dlq:customer",
    )
    retry = retry_policy(
        retry_policy_id="UIEF-RETRY-0001",
        maximum_attempts=3,
        delay_seconds=1,
        retryable_errors=("connectivity_failure", "timeout"),
        timeout_seconds=30,
        escalation_ref="incident:integration",
        dead_letter_destination="dlq:customer",
    )
    security = security_policy(
        security_policy_id="UIEF-SEC-0001",
        identity_strength="mfa",
        credential_ref="secret-ref:crm-oauth",
        transport_encryption="tls1.3",
        authorization_scope_refs=("scope:customer.sync",),
        data_protection_rules=("mask:email",),
        residency_rules=("region:eu",),
        logging_safety_rules=("redact:payload",),
    )

    assert connector.connector_hash
    assert contract.generated_from_implementation is False
    assert mapping.field_mappings[0]["canonical_field"] == "Customer.Identifier"
    assert event.delivery_semantics == "effectively_once"
    assert retry.idempotency_required is True
    assert security.secret_values_embedded is False


def test_r11_twin_marketplace_provider_and_ai_boundaries_are_governed() -> None:
    twin = digital_twin(
        twin_id="UIEF-TWIN-0001",
        integration_ref="UIEF-INT-0001",
        deployed_connector_ref="UIEF-CONN-0001",
        active_version="1.0.0",
        endpoint_ref="endpoint:crm",
        dependency_refs=("contract:customer",),
        health=UiefHealthStatus.HEALTHY,
        performance_metrics={"latency_ms": 42},
        data_flow_refs=("flow:customer",),
        contract_status="compatible",
        security_status="valid",
    )
    asset = marketplace_asset(
        asset_id="UIEF-ASSET-0001",
        asset_type="connector",
        creator_ref="vendor:acme",
        publisher_ref="marketplace:internal",
        version="1.0.0",
        source_ref="git:connector",
        dependency_refs=("runtime:python",),
        license_ref="license:enterprise",
        signature_ref="sig:ed25519",
        certification_level=UiefCertificationLevel.ENTERPRISE_CERTIFIED,
        compatibility_refs=("uief:1.0",),
    )
    provider = provider_abstraction(
        provider_id="UIEF-PROV-0001",
        capability_ref="payment",
        logical_provider_type="payment_provider",
        primary_provider_ref="stripe",
        backup_provider_refs=("adyen",),
        regional_provider_refs=("provider:eu",),
        selection_policy_ref="policy:payment",
    )
    ai = ai_integration_boundary(
        ai_boundary_id="UIEF-AI-0001",
        provider_ref="openai",
        model_ref="model:reasoning",
        region="eu",
        approved_data_classes=("public",),
        context_limit_ref="ctx:bounded",
        retention_policy_ref="retention:none",
        output_constraint_refs=("constraint:no-secrets",),
        fallback_model_ref="model:fallback",
        cost_control_ref="budget:ai",
        audit_requirement_refs=("audit:model-call",),
    )

    assert twin.health is UiefHealthStatus.HEALTHY
    assert asset.isolated_execution_required is True
    assert provider.vendor_independent is True
    assert ai.unrestricted_project_knowledge_allowed is False
