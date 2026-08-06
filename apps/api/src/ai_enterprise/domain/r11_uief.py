from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_enterprise.domain.specification.kernel import specification_hash


class UiefValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class UiefIntegrationDomain(StrEnum):
    APPLICATION = "application"
    DATA = "data"
    IDENTITY = "identity"
    EVENT = "event"
    API = "api"
    FILE = "file"
    PROCESS = "process"
    INFRASTRUCTURE = "infrastructure"
    AI = "ai"
    PARTNER = "partner"


class UiefIntegrationLifecycle(StrEnum):
    PROPOSED = "proposed"
    MODELED = "modeled"
    VALIDATED = "validated"
    GENERATED = "generated"
    TESTED = "tested"
    APPROVED = "approved"
    ACTIVATED = "activated"
    OBSERVED = "observed"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class UiefIntegrationMode(StrEnum):
    REQUEST_RESPONSE = "request_response"
    PUBLISH_SUBSCRIBE = "publish_subscribe"
    EVENT_STREAMING = "event_streaming"
    BATCH_TRANSFER = "batch_transfer"
    FILE_EXCHANGE = "file_exchange"
    SYNCHRONIZATION = "synchronization"
    REPLICATION = "replication"
    COMMAND_DISPATCH = "command_dispatch"
    WEBHOOK = "webhook"
    POLLING = "polling"
    ORCHESTRATION = "orchestration"
    CHOREOGRAPHY = "choreography"


class UiefContractType(StrEnum):
    OPENAPI = "openapi"
    ASYNCAPI = "asyncapi"
    GRAPHQL = "graphql"
    PROTOBUF = "protobuf"
    JSON_SCHEMA = "json_schema"
    XML_SCHEMA = "xml_schema"
    AVRO = "avro"
    UPDL = "updl"


class UiefHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class UiefCertificationLevel(StrEnum):
    COMMUNITY = "community"
    VERIFIED = "verified"
    CERTIFIED = "certified"
    ENTERPRISE_CERTIFIED = "enterprise_certified"
    REGULATED_INDUSTRY_CERTIFIED = "regulated_industry_certified"


class UiefIntegrationObject(UiefValue):
    schema_version: Literal["uief-integration-object-0.1"] = "uief-integration-object-0.1"
    integration_id: str = Field(pattern=r"^UIEF-INT-[0-9]{4}$")
    manifest_ref: str = Field(min_length=1, max_length=240)
    name: str = Field(min_length=1, max_length=200)
    domain: UiefIntegrationDomain
    source_ref: str = Field(min_length=1, max_length=240)
    destination_ref: str = Field(min_length=1, max_length=240)
    purpose: str = Field(min_length=1, max_length=500)
    protocol: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{1,79}$")
    contract_ref: str = Field(min_length=1, max_length=240)
    authentication_ref: str = Field(min_length=1, max_length=240)
    authorization_ref: str = Field(min_length=1, max_length=240)
    mapping_ref: str = Field(min_length=1, max_length=240)
    trigger: str = Field(min_length=1, max_length=160)
    frequency: str = Field(min_length=1, max_length=120)
    error_strategy_ref: str = Field(min_length=1, max_length=240)
    retry_policy_ref: str = Field(min_length=1, max_length=240)
    owner_ref: str = Field(min_length=1, max_length=200)
    monitoring_ref: str = Field(min_length=1, max_length=240)
    compliance_classification: str = Field(min_length=1, max_length=120)
    lifecycle_state: UiefIntegrationLifecycle = UiefIntegrationLifecycle.PROPOSED
    manifest_owned: bool = True
    approved_for_activation: bool = False
    integration_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_integration(self) -> UiefIntegrationObject:
        if self.source_ref == self.destination_ref:
            raise ValueError("UIEF integration requires distinct source and destination")
        if not self.manifest_owned:
            raise ValueError("UIEF integrations must be represented in the Manifest")
        if self.lifecycle_state in {
            UiefIntegrationLifecycle.ACTIVATED,
            UiefIntegrationLifecycle.OBSERVED,
        } and not self.approved_for_activation:
            raise ValueError("UIEF integration activation requires explicit approval")
        if self.integration_hash != _integration_object_hash(self):
            raise ValueError("UIEF integration hash does not match canonical content")
        return self


class UiefConnectorRegistration(UiefValue):
    schema_version: Literal["uief-connector-registration-0.1"] = (
        "uief-connector-registration-0.1"
    )
    connector_id: str = Field(pattern=r"^UIEF-CONN-[0-9]{4}$")
    provider: str = Field(min_length=1, max_length=160)
    supported_system: str = Field(min_length=1, max_length=160)
    version: str = Field(min_length=1, max_length=80)
    protocols: tuple[str, ...]
    authentication_methods: tuple[str, ...]
    operations: tuple[str, ...]
    rate_limits: dict[str, float]
    data_classifications: tuple[str, ...]
    certification_level: UiefCertificationLevel
    compatibility_refs: tuple[str, ...]
    owner_ref: str = Field(min_length=1, max_length=200)
    lifecycle_status: str = Field(pattern=r"^(registered|certified|deprecated|disabled)$")
    hidden_business_rules: bool = False
    connector_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_connector(self) -> UiefConnectorRegistration:
        required_operations = {
            "configure",
            "authenticate",
            "discover",
            "read",
            "write",
            "transform",
            "validate",
            "observe",
            "recover",
        }
        if not required_operations.issubset(set(self.operations)):
            raise ValueError("UIEF connector must implement the universal connector contract")
        for values in (
            self.protocols,
            self.authentication_methods,
            self.operations,
            self.data_classifications,
            self.compatibility_refs,
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError("UIEF connector values must be unique and sorted")
        if self.hidden_business_rules:
            raise ValueError("UIEF connectors may not contain hidden business rules")
        if self.connector_hash != _connector_registration_hash(self):
            raise ValueError("UIEF connector hash does not match canonical content")
        return self


class UiefContractRegistration(UiefValue):
    schema_version: Literal["uief-contract-registration-0.1"] = (
        "uief-contract-registration-0.1"
    )
    contract_id: str = Field(pattern=r"^UIEF-CTR-[0-9]{4}$")
    manifest_ref: str = Field(min_length=1, max_length=240)
    contract_type: UiefContractType
    contract_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    operations: tuple[str, ...]
    schema_refs: tuple[str, ...]
    error_refs: tuple[str, ...]
    security_requirement_refs: tuple[str, ...]
    slo_refs: tuple[str, ...]
    compatibility_rules: tuple[str, ...]
    generated_from_implementation: bool = False
    contract_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_contract(self) -> UiefContractRegistration:
        for values in (
            self.operations,
            self.schema_refs,
            self.error_refs,
            self.security_requirement_refs,
            self.slo_refs,
            self.compatibility_rules,
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError("UIEF contract values must be unique and sorted")
        if self.generated_from_implementation:
            raise ValueError("UIEF contracts must be contract-first")
        if self.contract_hash != _contract_registration_hash(self):
            raise ValueError("UIEF contract hash does not match canonical content")
        return self


class UiefDataMapping(UiefValue):
    schema_version: Literal["uief-data-mapping-0.1"] = "uief-data-mapping-0.1"
    mapping_id: str = Field(pattern=r"^UIEF-MAP-[0-9]{4}$")
    integration_ref: str = Field(min_length=1, max_length=240)
    canonical_model_ref: str = Field(min_length=1, max_length=240)
    field_mappings: tuple[dict[str, str], ...]
    transformation_rules: tuple[str, ...]
    test_refs: tuple[str, ...]
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    mapping_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_mapping(self) -> UiefDataMapping:
        if not self.field_mappings:
            raise ValueError("UIEF data mapping requires field mappings")
        for item in self.field_mappings:
            required = {"external_field", "canonical_field", "rule"}
            if not required.issubset(set(item)):
                raise ValueError("UIEF field mapping requires external, canonical, and rule")
        for values in (self.transformation_rules, self.test_refs):
            if tuple(sorted(set(values))) != values:
                raise ValueError("UIEF mapping values must be unique and sorted")
        if self.mapping_hash != _data_mapping_hash(self):
            raise ValueError("UIEF mapping hash does not match canonical content")
        return self


class UiefEventDefinition(UiefValue):
    schema_version: Literal["uief-event-definition-0.1"] = "uief-event-definition-0.1"
    event_id: str = Field(pattern=r"^UIEF-EVT-[0-9]{4}$")
    event_name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.:-]{2,159}$")
    producer_ref: str = Field(min_length=1, max_length=240)
    consumer_refs: tuple[str, ...]
    schema_ref: str = Field(min_length=1, max_length=240)
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    partition_key: str = Field(min_length=1, max_length=120)
    delivery_semantics: str = Field(
        pattern=r"^(at_most_once|at_least_once|effectively_once)$"
    )
    retention: str = Field(min_length=1, max_length=120)
    sensitivity: str = Field(min_length=1, max_length=120)
    retry_policy_ref: str = Field(min_length=1, max_length=240)
    dead_letter_strategy_ref: str = Field(min_length=1, max_length=240)
    event_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_event(self) -> UiefEventDefinition:
        if tuple(sorted(set(self.consumer_refs))) != self.consumer_refs:
            raise ValueError("UIEF event consumers must be unique and sorted")
        if self.producer_ref in self.consumer_refs:
            raise ValueError("UIEF event producer may not consume the same definition")
        if self.event_hash != _event_definition_hash(self):
            raise ValueError("UIEF event hash does not match canonical content")
        return self


class UiefRetryPolicy(UiefValue):
    schema_version: Literal["uief-retry-policy-0.1"] = "uief-retry-policy-0.1"
    retry_policy_id: str = Field(pattern=r"^UIEF-RETRY-[0-9]{4}$")
    maximum_attempts: int = Field(ge=0, le=20)
    delay_seconds: float = Field(ge=0)
    exponential_backoff: bool = True
    jitter: bool = True
    retryable_errors: tuple[str, ...]
    timeout_seconds: float = Field(gt=0)
    escalation_ref: str = Field(min_length=1, max_length=240)
    dead_letter_destination: str = Field(min_length=1, max_length=240)
    idempotency_required: bool = True
    retry_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_retry(self) -> UiefRetryPolicy:
        if tuple(sorted(set(self.retryable_errors))) != self.retryable_errors:
            raise ValueError("UIEF retryable errors must be unique and sorted")
        if not self.idempotency_required and self.maximum_attempts > 0:
            raise ValueError("UIEF retries require idempotency protection")
        if self.retry_hash != _retry_policy_hash(self):
            raise ValueError("UIEF retry hash does not match canonical content")
        return self


class UiefSecurityPolicy(UiefValue):
    schema_version: Literal["uief-security-policy-0.1"] = "uief-security-policy-0.1"
    security_policy_id: str = Field(pattern=r"^UIEF-SEC-[0-9]{4}$")
    identity_strength: str = Field(min_length=1, max_length=120)
    credential_ref: str = Field(min_length=1, max_length=240)
    transport_encryption: str = Field(min_length=1, max_length=120)
    authorization_scope_refs: tuple[str, ...]
    data_protection_rules: tuple[str, ...]
    residency_rules: tuple[str, ...]
    logging_safety_rules: tuple[str, ...]
    secret_values_embedded: bool = False
    security_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_security(self) -> UiefSecurityPolicy:
        for values in (
            self.authorization_scope_refs,
            self.data_protection_rules,
            self.residency_rules,
            self.logging_safety_rules,
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError("UIEF security values must be unique and sorted")
        if self.secret_values_embedded:
            raise ValueError("UIEF credentials must be secret references, not secret values")
        if self.security_hash != _security_policy_hash(self):
            raise ValueError("UIEF security hash does not match canonical content")
        return self


class UiefDigitalTwin(UiefValue):
    schema_version: Literal["uief-digital-twin-0.1"] = "uief-digital-twin-0.1"
    twin_id: str = Field(pattern=r"^UIEF-TWIN-[0-9]{4}$")
    integration_ref: str = Field(min_length=1, max_length=240)
    deployed_connector_ref: str = Field(min_length=1, max_length=240)
    active_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    endpoint_ref: str = Field(min_length=1, max_length=240)
    dependency_refs: tuple[str, ...]
    health: UiefHealthStatus
    performance_metrics: dict[str, float]
    data_flow_refs: tuple[str, ...]
    contract_status: str = Field(min_length=1, max_length=120)
    security_status: str = Field(min_length=1, max_length=120)
    twin_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_twin(self) -> UiefDigitalTwin:
        for values in (self.dependency_refs, self.data_flow_refs):
            if tuple(sorted(set(values))) != values:
                raise ValueError("UIEF digital twin refs must be unique and sorted")
        if self.twin_hash != _digital_twin_hash(self):
            raise ValueError("UIEF digital twin hash does not match canonical content")
        return self


class UiefMarketplaceAsset(UiefValue):
    schema_version: Literal["uief-marketplace-asset-0.1"] = "uief-marketplace-asset-0.1"
    asset_id: str = Field(pattern=r"^UIEF-ASSET-[0-9]{4}$")
    asset_type: str = Field(
        pattern=(
            r"^(connector|integration_template|canonical_model|api_contract|event_schema|"
            r"generator|workflow_pack|compliance_mapping|migration_tool|industry_accelerator)$"
        )
    )
    creator_ref: str = Field(min_length=1, max_length=200)
    publisher_ref: str = Field(min_length=1, max_length=200)
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    source_ref: str = Field(min_length=1, max_length=240)
    dependency_refs: tuple[str, ...]
    license_ref: str = Field(min_length=1, max_length=200)
    signature_ref: str = Field(min_length=1, max_length=300)
    certification_level: UiefCertificationLevel
    compatibility_refs: tuple[str, ...]
    isolated_execution_required: bool = True
    asset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_asset(self) -> UiefMarketplaceAsset:
        for values in (self.dependency_refs, self.compatibility_refs):
            if tuple(sorted(set(values))) != values:
                raise ValueError("UIEF marketplace asset refs must be unique and sorted")
        if not self.isolated_execution_required:
            raise ValueError("UIEF marketplace assets require isolation")
        if self.asset_hash != _marketplace_asset_hash(self):
            raise ValueError("UIEF marketplace asset hash does not match canonical content")
        return self


class UiefProviderAbstraction(UiefValue):
    schema_version: Literal["uief-provider-abstraction-0.1"] = (
        "uief-provider-abstraction-0.1"
    )
    provider_id: str = Field(pattern=r"^UIEF-PROV-[0-9]{4}$")
    capability_ref: str = Field(min_length=1, max_length=240)
    logical_provider_type: str = Field(min_length=1, max_length=120)
    primary_provider_ref: str = Field(min_length=1, max_length=240)
    backup_provider_refs: tuple[str, ...] = ()
    regional_provider_refs: tuple[str, ...] = ()
    selection_policy_ref: str = Field(min_length=1, max_length=240)
    vendor_independent: bool = True
    provider_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_provider(self) -> UiefProviderAbstraction:
        for values in (self.backup_provider_refs, self.regional_provider_refs):
            if tuple(sorted(set(values))) != values:
                raise ValueError("UIEF provider refs must be unique and sorted")
        if self.primary_provider_ref in self.backup_provider_refs:
            raise ValueError("UIEF backup providers must differ from the primary provider")
        if not self.vendor_independent:
            raise ValueError("UIEF provider abstractions must preserve vendor independence")
        if self.provider_hash != _provider_abstraction_hash(self):
            raise ValueError("UIEF provider hash does not match canonical content")
        return self


class UiefAiIntegrationBoundary(UiefValue):
    schema_version: Literal["uief-ai-integration-boundary-0.1"] = (
        "uief-ai-integration-boundary-0.1"
    )
    ai_boundary_id: str = Field(pattern=r"^UIEF-AI-[0-9]{4}$")
    provider_ref: str = Field(min_length=1, max_length=240)
    model_ref: str = Field(min_length=1, max_length=240)
    region: str = Field(min_length=1, max_length=80)
    approved_data_classes: tuple[str, ...]
    context_limit_ref: str = Field(min_length=1, max_length=200)
    retention_policy_ref: str = Field(min_length=1, max_length=200)
    output_constraint_refs: tuple[str, ...]
    fallback_model_ref: str = Field(min_length=1, max_length=240)
    cost_control_ref: str = Field(min_length=1, max_length=200)
    audit_requirement_refs: tuple[str, ...]
    unrestricted_project_knowledge_allowed: bool = False
    ai_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_ai_boundary(self) -> UiefAiIntegrationBoundary:
        for values in (
            self.approved_data_classes,
            self.output_constraint_refs,
            self.audit_requirement_refs,
        ):
            if tuple(sorted(set(values))) != values:
                raise ValueError("UIEF AI integration refs must be unique and sorted")
        if self.unrestricted_project_knowledge_allowed:
            raise ValueError("UIEF AI providers may not receive unrestricted project knowledge")
        if self.ai_hash != _ai_integration_boundary_hash(self):
            raise ValueError("UIEF AI integration hash does not match canonical content")
        return self


def integration_object(**values: object) -> UiefIntegrationObject:
    values.pop("schema_version", None)
    provisional = UiefIntegrationObject.model_construct(
        schema_version="uief-integration-object-0.1",
        integration_hash="0" * 64,
        **values,
    )
    return UiefIntegrationObject(
        **provisional.model_dump(exclude={"integration_hash"}),
        integration_hash=_integration_object_hash(provisional),
    )


def connector_registration(**values: object) -> UiefConnectorRegistration:
    values.pop("schema_version", None)
    provisional = UiefConnectorRegistration.model_construct(
        schema_version="uief-connector-registration-0.1",
        connector_hash="0" * 64,
        **_sorted_tuple_values(values),
    )
    return UiefConnectorRegistration(
        **provisional.model_dump(exclude={"connector_hash"}),
        connector_hash=_connector_registration_hash(provisional),
    )


def contract_registration(**values: object) -> UiefContractRegistration:
    values.pop("schema_version", None)
    provisional = UiefContractRegistration.model_construct(
        schema_version="uief-contract-registration-0.1",
        contract_hash="0" * 64,
        **_sorted_tuple_values(values),
    )
    return UiefContractRegistration(
        **provisional.model_dump(exclude={"contract_hash"}),
        contract_hash=_contract_registration_hash(provisional),
    )


def data_mapping(**values: object) -> UiefDataMapping:
    values.pop("schema_version", None)
    provisional = UiefDataMapping.model_construct(
        schema_version="uief-data-mapping-0.1",
        mapping_hash="0" * 64,
        **_sorted_tuple_values(values),
    )
    return UiefDataMapping(
        **provisional.model_dump(exclude={"mapping_hash"}),
        mapping_hash=_data_mapping_hash(provisional),
    )


def event_definition(**values: object) -> UiefEventDefinition:
    values.pop("schema_version", None)
    provisional = UiefEventDefinition.model_construct(
        schema_version="uief-event-definition-0.1",
        event_hash="0" * 64,
        **_sorted_tuple_values(values),
    )
    return UiefEventDefinition(
        **provisional.model_dump(exclude={"event_hash"}),
        event_hash=_event_definition_hash(provisional),
    )


def retry_policy(**values: object) -> UiefRetryPolicy:
    values.pop("schema_version", None)
    provisional = UiefRetryPolicy.model_construct(
        schema_version="uief-retry-policy-0.1",
        retry_hash="0" * 64,
        **_sorted_tuple_values(values),
    )
    return UiefRetryPolicy(
        **provisional.model_dump(exclude={"retry_hash"}),
        retry_hash=_retry_policy_hash(provisional),
    )


def security_policy(**values: object) -> UiefSecurityPolicy:
    values.pop("schema_version", None)
    provisional = UiefSecurityPolicy.model_construct(
        schema_version="uief-security-policy-0.1",
        security_hash="0" * 64,
        **_sorted_tuple_values(values),
    )
    return UiefSecurityPolicy(
        **provisional.model_dump(exclude={"security_hash"}),
        security_hash=_security_policy_hash(provisional),
    )


def digital_twin(**values: object) -> UiefDigitalTwin:
    values.pop("schema_version", None)
    provisional = UiefDigitalTwin.model_construct(
        schema_version="uief-digital-twin-0.1",
        twin_hash="0" * 64,
        **_sorted_tuple_values(values),
    )
    return UiefDigitalTwin(
        **provisional.model_dump(exclude={"twin_hash"}),
        twin_hash=_digital_twin_hash(provisional),
    )


def marketplace_asset(**values: object) -> UiefMarketplaceAsset:
    values.pop("schema_version", None)
    provisional = UiefMarketplaceAsset.model_construct(
        schema_version="uief-marketplace-asset-0.1",
        asset_hash="0" * 64,
        **_sorted_tuple_values(values),
    )
    return UiefMarketplaceAsset(
        **provisional.model_dump(exclude={"asset_hash"}),
        asset_hash=_marketplace_asset_hash(provisional),
    )


def provider_abstraction(**values: object) -> UiefProviderAbstraction:
    values.pop("schema_version", None)
    provisional = UiefProviderAbstraction.model_construct(
        schema_version="uief-provider-abstraction-0.1",
        provider_hash="0" * 64,
        **_sorted_tuple_values(values),
    )
    return UiefProviderAbstraction(
        **provisional.model_dump(exclude={"provider_hash"}),
        provider_hash=_provider_abstraction_hash(provisional),
    )


def ai_integration_boundary(**values: object) -> UiefAiIntegrationBoundary:
    values.pop("schema_version", None)
    provisional = UiefAiIntegrationBoundary.model_construct(
        schema_version="uief-ai-integration-boundary-0.1",
        ai_hash="0" * 64,
        **_sorted_tuple_values(values),
    )
    return UiefAiIntegrationBoundary(
        **provisional.model_dump(exclude={"ai_hash"}),
        ai_hash=_ai_integration_boundary_hash(provisional),
    )


def _sorted_tuple_values(values: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in values.items():
        if isinstance(value, tuple) and all(isinstance(item, str | StrEnum) for item in value):
            result[key] = tuple(sorted(set(value)))
        else:
            result[key] = value
    return result


def _integration_object_hash(value: UiefIntegrationObject) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"integration_hash"}))


def _connector_registration_hash(value: UiefConnectorRegistration) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"connector_hash"}))


def _contract_registration_hash(value: UiefContractRegistration) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"contract_hash"}))


def _data_mapping_hash(value: UiefDataMapping) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"mapping_hash"}))


def _event_definition_hash(value: UiefEventDefinition) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"event_hash"}))


def _retry_policy_hash(value: UiefRetryPolicy) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"retry_hash"}))


def _security_policy_hash(value: UiefSecurityPolicy) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"security_hash"}))


def _digital_twin_hash(value: UiefDigitalTwin) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"twin_hash"}))


def _marketplace_asset_hash(value: UiefMarketplaceAsset) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"asset_hash"}))


def _provider_abstraction_hash(value: UiefProviderAbstraction) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"provider_hash"}))


def _ai_integration_boundary_hash(value: UiefAiIntegrationBoundary) -> str:
    return specification_hash(value.model_dump(mode="json", exclude={"ai_hash"}))
