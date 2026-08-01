from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from ai_enterprise.application.federation_service import FederationGatewayService
from ai_enterprise.domain.federation import (
    ConnectorVersion,
    DataExchangeAgreement,
    ExternalContract,
    FederatedIdentity,
    FederationAgreement,
    FederationError,
    PublishedCapability,
    SignedGatewayRequest,
    SupplyChainDependency,
    ThirdPartyRiskRecommendation,
    TrustAssessment,
    TrustLevel,
    stable_hash,
)

NOW = datetime(2026, 8, 1, tzinfo=UTC)


class Verifier:
    def verify(self, *, key_fingerprint: str, message_hash: str, signature: str) -> bool:
        return key_fingerprint == "f" * 64 and signature == f"signed:{message_hash}"


class Nonces:
    def __init__(self) -> None:
        self.values: set[tuple[object, str]] = set()

    def consume(self, *, identity_id, nonce: str, expires_at) -> bool:
        key = (identity_id, nonce)
        if key in self.values:
            return False
        self.values.add(key)
        return True


def _fixtures():
    contract = ExternalContract.create(
        id=uuid4(),
        provider_key="partner.api",
        version="1.0.0",
        authentication_scheme="mTLS",
        operations=("create_project",),
        request_schema_hash="a" * 64,
        response_schema_hash="b" * 64,
        rate_limit_per_minute=60,
        failure_modes=("timeout",),
        approved_by_human_id=uuid4(),
    )
    connector = ConnectorVersion(
        uuid4(),
        "partner",
        "1.0.0",
        ("project.create",),
        "mTLS",
        (contract.id,),
        (contract.contract_hash,),
        60,
        "federation-v1",
        "c" * 64,
        uuid4(),
        "approved",
    )
    partner = uuid4()
    identity = FederatedIdentity(
        uuid4(),
        partner,
        "subject-1",
        "partner.example",
        "workload",
        "f" * 64,
        "partner-key",
        ("project.create",),
        "confidential",
        uuid4(),
        NOW - timedelta(days=1),
        NOW + timedelta(days=1),
    )
    capability = PublishedCapability(
        uuid4(),
        partner,
        "project.create",
        "1.0.0",
        contract.id,
        contract.contract_hash,
        "4" * 64,
        "5" * 64,
        None,
        "commercial",
        "6" * 64,
        ("7" * 64,),
        "published",
    )
    agreement = FederationAgreement(
        uuid4(),
        uuid4(),
        partner,
        "d" * 64,
        ("project.create",),
        (capability.id,),
        NOW - timedelta(days=1),
        NOW + timedelta(days=1),
        uuid4(),
        "partner-signature",
        "active",
    )
    trust = TrustAssessment.assess(
        partner_id=partner,
        authentication_quality=80,
        historical_reliability=80,
        contract_stability=80,
        security_posture=80,
        operational_history=80,
        certification=80,
        policy_compliance=80,
        evidence_hashes=("e" * 64,),
        policy_version="trust-v1",
    )
    exchange = DataExchangeAgreement(
        uuid4(),
        agreement.id,
        "1" * 64,
        agreement.local_enterprise_id,
        "confidential",
        "confidential",
        30,
        "aes-256-gcm",
        "2" * 64,
        "contract-performance",
        (identity.id,),
        True,
        uuid4(),
        NOW - timedelta(days=1),
        NOW + timedelta(days=1),
    )
    request = SignedGatewayRequest(
        uuid4(),
        connector.id,
        contract.id,
        identity.id,
        agreement.id,
        agreement.local_enterprise_id,
        "create_project",
        "project.create",
        "3" * 64,
        "confidential",
        NOW,
        "unique-nonce",
        "partner-key",
        "pending",
    )
    service = FederationGatewayService(Verifier(), Nonces())
    unsigned = service.authorize(
        request,
        connector=connector,
        contract=contract,
        identity=identity,
        agreement=agreement,
        trust=trust,
        capability=capability,
        data_exchange=exchange,
        now=NOW,
    )
    request = replace(request, signature=f"signed:{unsigned.request_hash}")
    return service, request, connector, contract, identity, agreement, trust, exchange, capability


def _authorize(
    *,
    request_mutator=lambda value: value,
    identity_mutator=lambda value: value,
    trust_mutator=lambda value: value,
    exchange_mutator=lambda value: value,
    capability_mutator=lambda value: value,
    connector_mutator=lambda value: value,
    **changes,
):
    service, request, connector, contract, identity, agreement, trust, exchange, capability = (
        _fixtures()
    )
    values = {
        "request": request_mutator(request),
        "connector": connector_mutator(connector),
        "contract": contract,
        "identity": identity_mutator(identity),
        "agreement": agreement,
        "trust": trust_mutator(trust),
        "capability": capability_mutator(capability),
        "data_exchange": exchange_mutator(exchange),
        "now": NOW,
    }
    values.update(changes)
    return service.authorize(**values)


def test_gateway_allows_only_fully_bound_signed_local_authority() -> None:
    decision = _authorize()
    assert decision.allowed and decision.code == "FED-ALLOWED"
    assert decision.contract_hash is not None


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda request: replace(request, connector_version_id=uuid4()), "FED-CONNECTOR-DENIED"),
        (lambda request: replace(request, contract_id=uuid4()), "FED-CONTRACT-DENIED"),
        (lambda request: replace(request, federated_identity_id=uuid4()), "FED-IDENTITY-DENIED"),
        (lambda request: replace(request, capability_key="admin.all"), "FED-CAPABILITY-DENIED"),
    ],
)
def test_gateway_fails_closed_on_binding_or_authority_substitution(mutation, code) -> None:
    assert _authorize(request_mutator=mutation).code == code


def test_replay_expiry_bad_signature_unknown_trust_and_data_scope_are_denied() -> None:
    service, request, connector, contract, identity, agreement, trust, exchange, capability = (
        _fixtures()
    )
    arguments = {
        "connector": connector,
        "contract": contract,
        "identity": identity,
        "agreement": agreement,
        "trust": trust,
        "capability": capability,
        "data_exchange": exchange,
        "now": NOW,
    }
    assert service.authorize(request, **arguments).allowed
    assert service.authorize(request, **arguments).code == "FED-REPLAY-DENIED"
    assert (
        _authorize(
            request_mutator=lambda request: replace(request, timestamp=NOW - timedelta(hours=1))
        ).code
        == "FED-REPLAY-DENIED"
    )
    assert (
        _authorize(request_mutator=lambda request: replace(request, signature="forged")).code
        == "FED-SIGNATURE-DENIED"
    )
    assert (
        _authorize(trust_mutator=lambda trust: replace(trust, level=TrustLevel.UNKNOWN)).code
        == "FED-TRUST-DENIED"
    )
    assert (
        _authorize(
            exchange_mutator=lambda exchange: replace(exchange, classification="restricted")
        ).code
        == "FED-DATA-EXCHANGE-DENIED"
    )
    assert (
        _authorize(identity_mutator=lambda identity: replace(identity, valid_until=NOW)).code
        == "FED-IDENTITY-DENIED"
    )


def test_contract_is_deterministic_immutable_and_drift_detectable() -> None:
    _, _, _, contract, *_ = _fixtures()
    assert contract.verify()
    assert not replace(contract, operations=("delete_everything",)).verify()
    with pytest.raises(FrozenInstanceError):
        contract.version = "2.0.0"  # type: ignore[misc]


def test_trust_never_grants_capability_and_requires_all_dimensions() -> None:
    assert (
        _authorize(
            identity_mutator=lambda identity: replace(identity, locally_granted_capabilities=()),
            trust_mutator=lambda trust: replace(trust, level=TrustLevel.STRATEGIC),
        ).code
        == "FED-CAPABILITY-DENIED"
    )
    with pytest.raises(FederationError, match="0 to 100"):
        TrustAssessment.assess(
            partner_id=uuid4(),
            authentication_quality=101,
            historical_reliability=100,
            contract_stability=100,
            security_posture=100,
            operational_history=100,
            certification=100,
            policy_compliance=100,
            evidence_hashes=("a" * 64,),
            policy_version="v1",
        )


def test_capability_supply_chain_risk_and_data_are_governed_not_self_executing() -> None:
    capability = PublishedCapability(
        uuid4(),
        uuid4(),
        "identity.verify",
        "1.0.0",
        uuid4(),
        "a" * 64,
        "b" * 64,
        "c" * 64,
        None,
        "commercial",
        "d" * 64,
        ("d" * 64,),
        "published",
    )
    assert capability.status == "published"
    dependency = SupplyChainDependency(
        uuid4(),
        "container",
        "registry.example",
        "service",
        "1.0.0",
        "e" * 64,
        "Apache-2.0",
        "verified",
        "f" * 64,
        "low",
        ("1" * 64,),
        uuid4(),
        None,
    )
    assert not dependency.usable
    assert replace(dependency, approved_by_human_id=uuid4()).usable
    recommendation = ThirdPartyRiskRecommendation(
        uuid4(),
        dependency.id,
        "provider_outage",
        "high",
        ("2" * 64,),
        "review alternate provider",
    )
    assert recommendation.self_executing is False


def test_capability_exchange_and_connector_contract_negotiation_are_explicit() -> None:
    assert (
        _authorize(
            capability_mutator=lambda capability: replace(capability, contract_id=uuid4())
        ).code
        == "FED-CAPABILITY-EXCHANGE-DENIED"
    )
    assert (
        _authorize(
            connector_mutator=lambda connector: replace(connector, authentication_scheme="api-key")
        ).code
        == "FED-CONTRACT-DENIED"
    )
    assert (
        _authorize(
            connector_mutator=lambda connector: replace(connector, rate_limit_per_minute=1000)
        ).code
        == "FED-CONTRACT-DENIED"
    )


def test_signed_requests_and_federation_validity_require_aware_time() -> None:
    _, request, _, _, identity, agreement, *_ = _fixtures()
    with pytest.raises(FederationError, match="timezone-aware"):
        replace(request, timestamp=datetime(2026, 8, 1))
    with pytest.raises(FederationError, match="timezone-aware"):
        replace(identity, valid_from=datetime(2026, 8, 1))
    with pytest.raises(FederationError, match="timezone-aware"):
        replace(agreement, valid_until=datetime(2026, 8, 2))


def test_risk_recommendation_can_never_be_constructed_as_self_executing() -> None:
    with pytest.raises(FederationError, match="cannot self-execute"):
        ThirdPartyRiskRecommendation(
            uuid4(),
            uuid4(),
            "license_change",
            "high",
            ("a" * 64,),
            "review dependency",
            True,
        )


def test_signed_canonicalization_binds_audience_federation_key_and_exact_contract_hash() -> None:
    assert stable_hash({"at": NOW}) == stable_hash({"at": NOW.astimezone(UTC)})
    assert (
        _authorize(
            request_mutator=lambda request: replace(request, audience_enterprise_id=uuid4())
        ).code
        == "FED-AGREEMENT-DENIED"
    )
    assert (
        _authorize(request_mutator=lambda request: replace(request, federation_id=uuid4())).code
        == "FED-AGREEMENT-DENIED"
    )
    assert (
        _authorize(request_mutator=lambda request: replace(request, key_id="substituted-key")).code
        == "FED-IDENTITY-DENIED"
    )
    assert (
        _authorize(
            connector_mutator=lambda connector: replace(connector, contract_hashes=("9" * 64,))
        ).code
        == "FED-CONTRACT-DENIED"
    )


def test_classification_clearance_exchange_expiry_owner_and_audit_fail_closed() -> None:
    assert (
        _authorize(
            identity_mutator=lambda identity: replace(identity, maximum_classification="internal")
        ).code
        == "FED-DATA-EXCHANGE-DENIED"
    )
    assert (
        _authorize(exchange_mutator=lambda exchange: replace(exchange, valid_until=NOW)).code
        == "FED-DATA-EXCHANGE-DENIED"
    )
    assert (
        _authorize(
            exchange_mutator=lambda exchange: replace(exchange, owner_enterprise_id=uuid4())
        ).code
        == "FED-DATA-EXCHANGE-DENIED"
    )
    assert (
        _authorize(exchange_mutator=lambda exchange: replace(exchange, audit_required=False)).code
        == "FED-DATA-EXCHANGE-DENIED"
    )
    with pytest.raises(FederationError, match="incomplete"):
        _, _, _, _, _, _, _, exchange, _ = _fixtures()
        replace(exchange, legal_basis="")


def test_supply_chain_registration_cannot_self_approve() -> None:
    actor = uuid4()
    dependency = SupplyChainDependency(
        uuid4(),
        "model",
        "vendor",
        "model",
        "1.0.0",
        "a" * 64,
        "commercial",
        "verified",
        "b" * 64,
        "medium",
        ("c" * 64,),
        actor,
        actor,
    )
    assert not dependency.usable
