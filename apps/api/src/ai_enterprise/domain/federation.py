import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

_HASH = re.compile(r"^[0-9a-f]{64}$")
_VERSION = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_KEY = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$")
_CLASSIFICATION = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}


class FederationError(ValueError):
    pass


def stable_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(_canonical(value), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _canonical(value: object) -> object:
    if value is None or isinstance(value, bool | int | str):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        require_aware(value, "signed datetime")
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise FederationError("non-finite canonical number")
        return format(value.normalize(), "f")
    if isinstance(value, list | tuple):
        return [_canonical(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise FederationError("canonical object keys must be strings")
        return {key: _canonical(item) for key, item in value.items()}
    raise FederationError(f"unsupported canonical value: {type(value).__name__}")


def require_hash(value: str, label: str = "hash") -> None:
    if _HASH.fullmatch(value) is None:
        raise FederationError(f"{label} must be a lowercase SHA-256 digest")


def require_aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise FederationError(f"{label} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ExternalContract:
    id: UUID
    provider_key: str
    version: str
    authentication_scheme: str
    operations: tuple[str, ...]
    request_schema_hash: str
    response_schema_hash: str
    rate_limit_per_minute: int
    failure_modes: tuple[str, ...]
    approved_by_human_id: UUID
    contract_hash: str

    @classmethod
    def create(cls, **values: object) -> "ExternalContract":
        if not _VERSION.fullmatch(str(values.get("version", ""))):
            raise FederationError("external contracts require semantic versions")
        operations = values.get("operations")
        if not isinstance(operations, tuple) or operations != tuple(sorted(set(operations))):
            raise FederationError("contract operations must be unique and sorted")
        for name in ("request_schema_hash", "response_schema_hash"):
            require_hash(str(values.get(name, "")), name)
        rate_limit = values.get("rate_limit_per_minute")
        if not isinstance(rate_limit, int) or rate_limit < 1:
            raise FederationError("contract rate limit must be positive")
        return cls(contract_hash=stable_hash(values), **values)  # type: ignore[arg-type]

    def verify(self) -> bool:
        values = {name: getattr(self, name) for name in self.__slots__ if name != "contract_hash"}
        return self.contract_hash == stable_hash(values)


@dataclass(frozen=True, slots=True)
class ConnectorVersion:
    id: UUID
    connector_key: str
    version: str
    capability_keys: tuple[str, ...]
    authentication_scheme: str
    contract_ids: tuple[UUID, ...]
    contract_hashes: tuple[str, ...]
    rate_limit_per_minute: int
    policy_version: str
    artifact_hash: str
    approved_by_human_id: UUID
    status: str

    def __post_init__(self) -> None:
        require_hash(self.artifact_hash, "connector artifact hash")
        if len(self.contract_ids) != len(self.contract_hashes):
            raise FederationError("every connector contract ID must bind an exact hash")
        for digest in self.contract_hashes:
            require_hash(digest, "connector contract hash")
        if self.status not in {"approved", "suspended", "retired"}:
            raise FederationError("connector status is not governed")
        if not _VERSION.fullmatch(self.version) or self.capability_keys != tuple(
            sorted(set(self.capability_keys))
        ):
            raise FederationError("invalid connector version or capabilities")


@dataclass(frozen=True, slots=True)
class FederatedIdentity:
    id: UUID
    partner_id: UUID
    external_subject: str
    issuer: str
    identity_type: str
    public_key_fingerprint: str
    key_id: str
    locally_granted_capabilities: tuple[str, ...]
    maximum_classification: str
    local_approval_id: UUID
    valid_from: datetime
    valid_until: datetime
    status: str = "active"

    def __post_init__(self) -> None:
        require_hash(self.public_key_fingerprint, "identity key fingerprint")
        if not self.key_id or self.maximum_classification not in _CLASSIFICATION:
            raise FederationError("federated key and classification clearance are required")
        require_aware(self.valid_from, "identity valid_from")
        require_aware(self.valid_until, "identity valid_until")
        if self.valid_until <= self.valid_from or self.status not in {
            "active",
            "suspended",
            "revoked",
        }:
            raise FederationError("invalid federated identity lifecycle")
        if self.locally_granted_capabilities != tuple(
            sorted(set(self.locally_granted_capabilities))
        ):
            raise FederationError("local capabilities must be explicit, unique, and sorted")

    def active_at(self, now: datetime) -> bool:
        return self.status == "active" and self.valid_from <= now < self.valid_until


class TrustLevel(StrEnum):
    UNKNOWN = "unknown"
    AUTHENTICATED = "authenticated"
    VERIFIED = "verified"
    CERTIFIED = "certified"
    STRATEGIC = "strategic_partner"


@dataclass(frozen=True, slots=True)
class TrustAssessment:
    partner_id: UUID
    authentication_quality: int
    historical_reliability: int
    contract_stability: int
    security_posture: int
    operational_history: int
    certification: int
    policy_compliance: int
    evidence_hashes: tuple[str, ...]
    policy_version: str
    level: TrustLevel

    @classmethod
    def assess(cls, **values: object) -> "TrustAssessment":
        dimensions = (
            "authentication_quality",
            "historical_reliability",
            "contract_stability",
            "security_posture",
            "operational_history",
            "certification",
            "policy_compliance",
        )
        raw_scores = [values.get(name) for name in dimensions]
        if any(not isinstance(score, int) or not 0 <= score <= 100 for score in raw_scores):
            raise FederationError("trust dimensions must be observable values from 0 to 100")
        scores = [score for score in raw_scores if isinstance(score, int)]
        evidence = values.get("evidence_hashes")
        if not isinstance(evidence, tuple) or len(evidence) != len(set(evidence)):
            raise FederationError("trust requires unique evidence")
        for digest in evidence:
            require_hash(digest, "trust evidence")
        minimum = min(scores)
        level = (
            TrustLevel.STRATEGIC
            if minimum >= 90
            else TrustLevel.CERTIFIED
            if minimum >= 75
            else TrustLevel.VERIFIED
            if minimum >= 50
            else TrustLevel.AUTHENTICATED
            if minimum >= 25
            else TrustLevel.UNKNOWN
        )
        return cls(level=level, **values)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class FederationAgreement:
    id: UUID
    local_enterprise_id: UUID
    partner_enterprise_id: UUID
    shared_policy_hash: str
    permitted_workflow_keys: tuple[str, ...]
    exchanged_capability_ids: tuple[UUID, ...]
    valid_from: datetime
    valid_until: datetime
    approved_by_local_human_id: UUID
    approved_by_partner_reference: str
    status: str

    def __post_init__(self) -> None:
        require_hash(self.shared_policy_hash, "shared policy hash")
        require_aware(self.valid_from, "federation valid_from")
        require_aware(self.valid_until, "federation valid_until")
        if (
            self.local_enterprise_id == self.partner_enterprise_id
            or self.valid_until <= self.valid_from
        ):
            raise FederationError("federation requires distinct enterprises and bounded validity")
        if self.status not in {"active", "suspended", "terminated"}:
            raise FederationError("invalid federation lifecycle")
        if self.permitted_workflow_keys != tuple(sorted(set(self.permitted_workflow_keys))):
            raise FederationError("federated workflow scopes must be explicit and sorted")


@dataclass(frozen=True, slots=True)
class PublishedCapability:
    id: UUID
    owner_enterprise_id: UUID
    capability_key: str
    version: str
    contract_id: UUID
    contract_hash: str
    sla_hash: str
    policy_hash: str
    pricing_hash: str | None
    license_key: str
    support_terms_hash: str
    evidence_hashes: tuple[str, ...]
    status: str

    def __post_init__(self) -> None:
        if not _KEY.fullmatch(self.capability_key) or not _VERSION.fullmatch(self.version):
            raise FederationError("invalid capability identity")
        for value in (self.sla_hash, self.policy_hash, self.support_terms_hash):
            require_hash(value)
        require_hash(self.contract_hash, "capability contract hash")
        if self.pricing_hash is not None:
            require_hash(self.pricing_hash)
        if self.status not in {"published", "suspended", "withdrawn"}:
            raise FederationError("invalid capability lifecycle")


@dataclass(frozen=True, slots=True)
class SupplyChainDependency:
    id: UUID
    dependency_type: str
    origin: str
    name: str
    version: str
    artifact_digest: str
    license_key: str
    security_status: str
    compatibility_hash: str
    risk_level: str
    evidence_hashes: tuple[str, ...]
    registered_by_actor_id: UUID
    approved_by_human_id: UUID | None

    def __post_init__(self) -> None:
        require_hash(self.artifact_digest, "artifact digest")
        require_hash(self.compatibility_hash, "compatibility hash")
        if self.security_status not in {"verified", "vulnerable", "unknown", "quarantined"}:
            raise FederationError("unknown supply-chain security status")
        for digest in self.evidence_hashes:
            require_hash(digest, "supply-chain evidence")
        if not self.evidence_hashes or len(self.evidence_hashes) != len(set(self.evidence_hashes)):
            raise FederationError("unique supply-chain evidence is required")

    @property
    def usable(self) -> bool:
        return (
            self.approved_by_human_id is not None
            and self.approved_by_human_id != self.registered_by_actor_id
            and self.security_status == "verified"
        )


@dataclass(frozen=True, slots=True)
class ThirdPartyRiskRecommendation:
    id: UUID
    subject_id: UUID
    risk_type: str
    severity: str
    evidence_hashes: tuple[str, ...]
    recommended_action: str
    self_executing: bool = False

    def __post_init__(self) -> None:
        if self.self_executing:
            raise FederationError("third-party risk recommendations cannot self-execute")
        for digest in self.evidence_hashes:
            require_hash(digest, "risk evidence")
        if not self.evidence_hashes:
            raise FederationError("risk recommendations require evidence")


@dataclass(frozen=True, slots=True)
class DataExchangeAgreement:
    id: UUID
    federation_id: UUID
    schema_hash: str
    owner_enterprise_id: UUID
    classification: str
    maximum_consumer_classification: str
    retention_days: int
    encryption_profile: str
    privacy_policy_hash: str
    legal_basis: str
    permitted_consumer_ids: tuple[UUID, ...]
    audit_required: bool
    approved_by_local_human_id: UUID
    valid_from: datetime
    valid_until: datetime

    def __post_init__(self) -> None:
        require_hash(self.schema_hash, "exchange schema hash")
        require_hash(self.privacy_policy_hash, "privacy policy hash")
        require_aware(self.valid_from, "data exchange valid_from")
        require_aware(self.valid_until, "data exchange valid_until")
        if (
            self.classification not in _CLASSIFICATION
            or self.maximum_consumer_classification not in _CLASSIFICATION
        ):
            raise FederationError("unknown data classification")
        if (
            self.retention_days < 1
            or not self.encryption_profile
            or not self.legal_basis
            or self.valid_until <= self.valid_from
        ):
            raise FederationError("data exchange governance is incomplete")
        if self.permitted_consumer_ids != tuple(sorted(set(self.permitted_consumer_ids), key=str)):
            raise FederationError("permitted consumers must be explicit, unique, and sorted")

    def permits(
        self,
        consumer_id: UUID,
        *,
        payload_classification: str,
        consumer_clearance: str,
        now: datetime,
    ) -> bool:
        return (
            self.valid_from <= now < self.valid_until
            and consumer_id in self.permitted_consumer_ids
            and payload_classification == self.classification
            and consumer_clearance in _CLASSIFICATION
            and _CLASSIFICATION[consumer_clearance] >= _CLASSIFICATION[self.classification]
            and _CLASSIFICATION[self.classification]
            <= _CLASSIFICATION[self.maximum_consumer_classification]
        )


@dataclass(frozen=True, slots=True)
class SignedGatewayRequest:
    id: UUID
    connector_version_id: UUID
    contract_id: UUID
    federated_identity_id: UUID
    federation_id: UUID
    audience_enterprise_id: UUID
    operation: str
    capability_key: str
    payload_hash: str
    classification: str
    timestamp: datetime
    nonce: str
    key_id: str
    signature: str

    def __post_init__(self) -> None:
        require_hash(self.payload_hash, "gateway payload hash")
        require_aware(self.timestamp, "gateway timestamp")
        if not self.nonce or not self.key_id or not self.signature:
            raise FederationError("signed request metadata is incomplete")


class SignatureVerifier(Protocol):
    def verify(self, *, key_fingerprint: str, message_hash: str, signature: str) -> bool: ...


class NonceConsumer(Protocol):
    """Atomically records a nonce and returns false if it was already consumed."""

    def consume(self, *, identity_id: UUID, nonce: str, expires_at: datetime) -> bool: ...


@dataclass(frozen=True, slots=True)
class GatewayDecision:
    allowed: bool
    code: str
    request_hash: str
    contract_hash: str | None
    trust_level: TrustLevel
