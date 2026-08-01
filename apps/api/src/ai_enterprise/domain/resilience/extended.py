from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from .enums import Capability
from .policies import ResiliencePolicyError


@dataclass(frozen=True, slots=True)
class RegionOwnershipLease:
    resource_id: UUID
    region: str
    fencing_token: int
    acquired_at: datetime
    expires_at: datetime
    witness_verified: bool


@dataclass(frozen=True, slots=True)
class ResidencyContext:
    data_classification: str
    jurisdiction: str
    processing_region: str
    provider_id: UUID | None
    telemetry_region: str | None = None


@dataclass(frozen=True, slots=True)
class ResidencyPolicy:
    classification: str
    jurisdiction: str
    storage_regions: frozenset[str]
    processing_regions: frozenset[str]
    provider_ids: frozenset[UUID]
    cross_border_allowed: bool


@dataclass(frozen=True, slots=True)
class ModelCandidate:
    model_id: UUID
    provider_id: UUID
    status: str
    approved_use_cases: frozenset[str]
    prohibited_data_classes: frozenset[str]
    hosting_region: str
    evaluation_passed: bool


@dataclass(frozen=True, slots=True)
class CryptoKeyVersion:
    key_id: UUID
    version: int
    algorithm: str
    status: str
    valid_from: datetime
    revoked_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class EmergencyAuthorityGrant:
    id: UUID
    principal_id: str
    capabilities: frozenset[Capability]
    valid_from: datetime
    valid_until: datetime
    issued_by: str
    second_approver: str
    revoked_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class RehearsalEvidence:
    status: str
    executed_at: datetime
    evidence_hash: str
    observed_duration_seconds: int


@dataclass(frozen=True, slots=True)
class ChaosExperiment:
    id: UUID
    status: str
    hypothesis: str
    safety_limits: dict[str, int]
    abort_conditions: tuple[str, ...]
    approved_by: str | None = None
    provider_evidence_hash: str | None = None


@dataclass(frozen=True, slots=True)
class CrisisActivation:
    id: UUID
    status: str
    declared_by: str
    second_approver: str
    prohibited_capabilities: frozenset[Capability]
    integrity_reviewed_by: str | None = None
    authority_reviewed_by: str | None = None


class RegionFencingPolicy:
    def acquire(
        self,
        proposed: RegionOwnershipLease,
        previous: RegionOwnershipLease | None,
        *,
        now: datetime,
    ) -> RegionOwnershipLease:
        if not proposed.witness_verified:
            raise ResiliencePolicyError("External witness verification is required")
        if proposed.expires_at <= now or proposed.acquired_at > now:
            raise ResiliencePolicyError("Ownership lease time bounds are invalid")
        if previous and proposed.fencing_token <= previous.fencing_token:
            raise ResiliencePolicyError("Fencing token must increase monotonically")
        return proposed

    def authorize_write(
        self, lease: RegionOwnershipLease | None, token: int, now: datetime
    ) -> bool:
        return bool(
            lease
            and lease.witness_verified
            and lease.expires_at > now
            and lease.fencing_token == token
        )


class SovereigntyPolicyEvaluator:
    def authorize(self, policy: ResidencyPolicy | None, context: ResidencyContext) -> bool:
        if policy is None:
            return False
        if (policy.classification, policy.jurisdiction) != (
            context.data_classification,
            context.jurisdiction,
        ):
            return False
        if context.processing_region not in policy.processing_regions:
            return False
        if context.provider_id is not None and context.provider_id not in policy.provider_ids:
            return False
        if context.telemetry_region and (
            not policy.cross_border_allowed
            and context.telemetry_region not in policy.storage_regions
        ):
            return False
        return True


class ModelRoutingPolicy:
    def select(
        self,
        candidates: tuple[ModelCandidate, ...],
        *,
        use_case: str,
        data_classification: str,
        permitted_providers: frozenset[UUID],
        permitted_regions: frozenset[str],
    ) -> ModelCandidate:
        eligible = tuple(
            value
            for value in candidates
            if value.status == "approved"
            and value.evaluation_passed
            and use_case in value.approved_use_cases
            and data_classification not in value.prohibited_data_classes
            and value.provider_id in permitted_providers
            and value.hosting_region in permitted_regions
        )
        if not eligible:
            raise ResiliencePolicyError("No compliant approved model is available")
        return sorted(eligible, key=lambda value: str(value.model_id))[0]


class CryptographicContinuityPolicy:
    def authorize_signing(self, key: CryptoKeyVersion | None, *, now: datetime) -> None:
        if key is None or key.status != "active" or key.valid_from > now or key.revoked_at:
            raise ResiliencePolicyError("No active signing key version is available")

    def historical_verification_allowed(
        self, key: CryptoKeyVersion, *, signed_at: datetime
    ) -> bool:
        return key.valid_from <= signed_at and (
            key.revoked_at is None or signed_at < key.revoked_at
        )


class EmergencyAuthorityPolicy:
    def validate(self, grant: EmergencyAuthorityGrant, *, now: datetime) -> None:
        if grant.issued_by == grant.second_approver or grant.principal_id in {
            grant.issued_by,
            grant.second_approver,
        }:
            raise ResiliencePolicyError("Break-glass issuance requires independent dual control")
        if grant.valid_until <= now or grant.valid_until <= grant.valid_from:
            raise ResiliencePolicyError("Emergency authority is expired or invalid")
        if grant.revoked_at:
            raise ResiliencePolicyError("Emergency authority is revoked")


class EvidenceGovernancePolicy:
    def tested_status(self, evidence: RehearsalEvidence | None) -> str:
        if evidence is None or evidence.status != "passed" or not evidence.evidence_hash:
            raise ResiliencePolicyError("Successful provider evidence is required")
        return "tested"

    def migrate_artifact(self, source_id: UUID, target_id: UUID, transformation_hash: str) -> None:
        if source_id == target_id or not transformation_hash:
            raise ResiliencePolicyError("Artifact migration must preserve the original")

    def complete_experiment(self, experiment: ChaosExperiment) -> ChaosExperiment:
        if experiment.status != "approved" or not experiment.provider_evidence_hash:
            raise ResiliencePolicyError("Approved experiment and provider evidence are required")
        return replace(experiment, status="completed")


class CrisisGovernancePolicy:
    def activate(self, crisis: CrisisActivation) -> CrisisActivation:
        if crisis.declared_by == crisis.second_approver:
            raise ResiliencePolicyError("Crisis declaration requires dual control")
        if not crisis.prohibited_capabilities:
            raise ResiliencePolicyError("Crisis mode must restrict capabilities")
        return replace(crisis, status="active")

    def close(self, crisis: CrisisActivation) -> CrisisActivation:
        if not crisis.integrity_reviewed_by or not crisis.authority_reviewed_by:
            raise ResiliencePolicyError("Integrity and authority exit reviews are required")
        if crisis.integrity_reviewed_by == crisis.declared_by:
            raise ResiliencePolicyError("Integrity review must be independent")
        return replace(crisis, status="closed")
