from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from ai_enterprise.application.resilience.extended_service import InstitutionalGovernanceValidator
from ai_enterprise.domain.resilience.enums import Capability
from ai_enterprise.domain.resilience.extended import (
    ChaosExperiment,
    CrisisActivation,
    CrisisGovernancePolicy,
    CryptographicContinuityPolicy,
    CryptoKeyVersion,
    EmergencyAuthorityGrant,
    EmergencyAuthorityPolicy,
    EvidenceGovernancePolicy,
    ModelCandidate,
    ModelRoutingPolicy,
    RegionFencingPolicy,
    RegionOwnershipLease,
    ResidencyContext,
    ResidencyPolicy,
    SovereigntyPolicyEvaluator,
)
from ai_enterprise.domain.resilience.policies import ResiliencePolicyError
from ai_enterprise.infrastructure.database.models import Base
from ai_enterprise.main import app

NOW = datetime(2026, 7, 31, tzinfo=UTC)


def test_region_write_requires_live_witnessed_monotonic_fence() -> None:
    policy = RegionFencingPolicy()
    resource = uuid4()
    previous = RegionOwnershipLease(resource, "eu-1", 4, NOW, NOW + timedelta(minutes=1), True)
    with pytest.raises(ResiliencePolicyError):
        policy.acquire(
            RegionOwnershipLease(resource, "eu-2", 4, NOW, NOW + timedelta(minutes=1), True),
            previous,
            now=NOW,
        )
    assert not policy.authorize_write(previous, 3, NOW)
    assert policy.authorize_write(previous, 4, NOW)


def test_sovereignty_and_model_routing_fail_closed() -> None:
    provider = uuid4()
    context = ResidencyContext("restricted", "EU", "eu-1", provider, "us-1")
    assert not SovereigntyPolicyEvaluator().authorize(None, context)
    residency = ResidencyPolicy(
        "restricted",
        "EU",
        frozenset({"eu-1"}),
        frozenset({"eu-1"}),
        frozenset({provider}),
        False,
    )
    assert not SovereigntyPolicyEvaluator().authorize(residency, context)
    candidate = ModelCandidate(
        uuid4(), provider, "approved", frozenset({"architecture"}), frozenset(), "eu-1", True
    )
    assert (
        ModelRoutingPolicy().select(
            (candidate,),
            use_case="architecture",
            data_classification="restricted",
            permitted_providers=frozenset({provider}),
            permitted_regions=frozenset({"eu-1"}),
        )
        == candidate
    )
    with pytest.raises(ResiliencePolicyError):
        ModelRoutingPolicy().select(
            (candidate,),
            use_case="code",
            data_classification="restricted",
            permitted_providers=frozenset({provider}),
            permitted_regions=frozenset({"eu-1"}),
        )


def test_crypto_rotation_preserves_only_pre_revocation_history() -> None:
    key = CryptoKeyVersion(uuid4(), 1, "ed25519", "revoked", NOW, NOW + timedelta(hours=1))
    policy = CryptographicContinuityPolicy()
    with pytest.raises(ResiliencePolicyError):
        policy.authorize_signing(key, now=NOW)
    assert policy.historical_verification_allowed(key, signed_at=NOW + timedelta(minutes=30))
    assert not policy.historical_verification_allowed(key, signed_at=NOW + timedelta(hours=2))


def test_emergency_authority_requires_independent_dual_control() -> None:
    grant = EmergencyAuthorityGrant(
        uuid4(),
        "operator",
        frozenset({Capability.EXECUTE_RECOVERY}),
        NOW,
        NOW + timedelta(minutes=15),
        "issuer",
        "issuer",
    )
    with pytest.raises(ResiliencePolicyError):
        EmergencyAuthorityPolicy().validate(grant, now=NOW)


def test_provider_evidence_required_for_exit_chaos_archive_and_preservation() -> None:
    policy = EvidenceGovernancePolicy()
    with pytest.raises(ResiliencePolicyError):
        policy.complete_experiment(
            ChaosExperiment(uuid4(), "approved", "worker survives", {}, ("abort",), "owner")
        )
    with pytest.raises(ResiliencePolicyError):
        policy.migrate_artifact(uuid4(), uuid4(), "")


def test_crisis_exit_requires_independent_integrity_and_authority_review() -> None:
    crisis = CrisisActivation(
        uuid4(),
        "declared",
        "commander",
        "second",
        frozenset({Capability.DISPATCH_EXTERNAL_COMMAND}),
    )
    active = CrisisGovernancePolicy().activate(crisis)
    with pytest.raises(ResiliencePolicyError):
        CrisisGovernancePolicy().close(active)


def test_generic_governance_records_never_accept_secret_or_unproved_success() -> None:
    validator = InstitutionalGovernanceValidator()
    with pytest.raises(ResiliencePolicyError):
        validator.validate(
            record_type="vendor_exit_rehearsal",
            status="tested",
            payload={},
            evidence_hash=None,
            actor="owner",
        )
    with pytest.raises(ResiliencePolicyError):
        validator.validate(
            record_type="crypto_key_version",
            status="active",
            payload={"private_key": "forbidden"},
            evidence_hash=None,
            actor="authority",
        )


def test_extended_tables_and_api_are_registered() -> None:
    assert "region_ownership_leases" in Base.metadata.tables
    assert "institutional_governance_records" in Base.metadata.tables
    assert "/api/v1/resilience/governance/{record_type}" in app.openapi()["paths"]
