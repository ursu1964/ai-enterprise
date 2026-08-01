from dataclasses import dataclass
from datetime import datetime, timedelta

from ai_enterprise.domain.federation import (
    ConnectorVersion,
    DataExchangeAgreement,
    ExternalContract,
    FederatedIdentity,
    FederationAgreement,
    GatewayDecision,
    NonceConsumer,
    PublishedCapability,
    SignatureVerifier,
    SignedGatewayRequest,
    TrustAssessment,
    TrustLevel,
    stable_hash,
)


@dataclass(frozen=True)
class FederationGatewayService:
    verifier: SignatureVerifier
    nonce_consumer: NonceConsumer
    maximum_clock_skew: timedelta = timedelta(minutes=5)

    def authorize(
        self,
        request: SignedGatewayRequest,
        *,
        connector: ConnectorVersion,
        contract: ExternalContract,
        identity: FederatedIdentity,
        agreement: FederationAgreement,
        trust: TrustAssessment,
        capability: PublishedCapability,
        data_exchange: DataExchangeAgreement,
        now: datetime,
    ) -> GatewayDecision:
        request_values = {
            "id": request.id,
            "connector_version_id": request.connector_version_id,
            "contract_id": request.contract_id,
            "federated_identity_id": request.federated_identity_id,
            "federation_id": request.federation_id,
            "audience_enterprise_id": request.audience_enterprise_id,
            "operation": request.operation,
            "capability_key": request.capability_key,
            "payload_hash": request.payload_hash,
            "classification": request.classification,
            "timestamp": request.timestamp,
            "nonce": request.nonce,
            "key_id": request.key_id,
        }
        request_hash = stable_hash(request_values)

        def deny(code: str) -> GatewayDecision:
            return GatewayDecision(
                False,
                code,
                request_hash,
                contract.contract_hash if contract.verify() else None,
                trust.level,
            )

        if request.connector_version_id != connector.id or connector.status != "approved":
            return deny("FED-CONNECTOR-DENIED")
        if (
            request.contract_id != contract.id
            or not contract.verify()
            or contract.id not in connector.contract_ids
            or connector.contract_hashes[connector.contract_ids.index(contract.id)]
            != contract.contract_hash
            or connector.authentication_scheme != contract.authentication_scheme
            or connector.rate_limit_per_minute > contract.rate_limit_per_minute
        ):
            return deny("FED-CONTRACT-DENIED")
        if (
            request.federated_identity_id != identity.id
            or request.key_id != identity.key_id
            or not identity.active_at(now)
        ):
            return deny("FED-IDENTITY-DENIED")
        if (
            agreement.status != "active"
            or request.federation_id != agreement.id
            or request.audience_enterprise_id != agreement.local_enterprise_id
            or not agreement.valid_from <= now < agreement.valid_until
            or identity.partner_id != agreement.partner_enterprise_id
        ):
            return deny("FED-AGREEMENT-DENIED")
        if (
            request.operation not in contract.operations
            or request.capability_key not in connector.capability_keys
            or request.capability_key not in identity.locally_granted_capabilities
            or request.capability_key not in agreement.permitted_workflow_keys
        ):
            return deny("FED-CAPABILITY-DENIED")
        if (
            capability.id not in agreement.exchanged_capability_ids
            or capability.owner_enterprise_id != agreement.partner_enterprise_id
            or capability.capability_key != request.capability_key
            or capability.contract_id != contract.id
            or capability.contract_hash != contract.contract_hash
            or capability.status != "published"
        ):
            return deny("FED-CAPABILITY-EXCHANGE-DENIED")
        if (
            data_exchange.federation_id != agreement.id
            or data_exchange.owner_enterprise_id != agreement.local_enterprise_id
            or not data_exchange.audit_required
            or not data_exchange.permits(
                identity.id,
                payload_classification=request.classification,
                consumer_clearance=identity.maximum_classification,
                now=now,
            )
        ):
            return deny("FED-DATA-EXCHANGE-DENIED")
        if trust.partner_id != identity.partner_id or trust.level is TrustLevel.UNKNOWN:
            return deny("FED-TRUST-DENIED")
        if abs(now - request.timestamp) > self.maximum_clock_skew:
            return deny("FED-REPLAY-DENIED")
        if not self.verifier.verify(
            key_fingerprint=identity.public_key_fingerprint,
            message_hash=request_hash,
            signature=request.signature,
        ):
            return deny("FED-SIGNATURE-DENIED")
        if not self.nonce_consumer.consume(
            identity_id=identity.id,
            nonce=request.nonce,
            expires_at=request.timestamp + self.maximum_clock_skew,
        ):
            return deny("FED-REPLAY-DENIED")
        return GatewayDecision(
            True, "FED-ALLOWED", request_hash, contract.contract_hash, trust.level
        )
