import uuid

from ai_enterprise.api.organization_schemas import CommandMetadata
from ai_enterprise.api.routes.organizations import router as organization_router
from ai_enterprise.application.organization_persistence_service import canonical_hash
from ai_enterprise.infrastructure.organization.models import (
    AgentAssignmentModel,
    AgentProfileVersionModel,
    CrewManifestModel,
    OrganizationalDecisionModel,
    OrganizationModel,
    RoleVersionModel,
)
from ai_enterprise.infrastructure.organization.seed import PROFILES, ROLES, UNITS


def test_version_and_assignment_records_bind_immutable_hashes() -> None:
    assert RoleVersionModel.__table__.c.role_hash.nullable is False
    assert AgentProfileVersionModel.__table__.c.configuration_hash.nullable is False
    assert AgentAssignmentModel.__table__.c.assignment_hash.nullable is False
    assert CrewManifestModel.__table__.c.manifest_hash.unique is True


def test_organizational_audit_has_complete_correlation_lineage() -> None:
    columns = OrganizationalDecisionModel.__table__.c
    for name in (
        "organization_id",
        "actor_principal",
        "agent_profile_id",
        "profile_version_id",
        "role_version_id",
        "assignment_id",
        "capability",
        "scope_type",
        "scope_id",
        "decision",
        "policy_versions",
        "configuration_hashes",
        "correlation_id",
        "causation_id",
    ):
        assert name in columns


def test_configuration_hash_is_canonical() -> None:
    assert canonical_hash({"b": 2, "a": [1]}) == canonical_hash({"a": [1], "b": 2})
    assert len(canonical_hash({"a": 1})) == 64


def test_commands_require_idempotency_and_carry_concurrency_metadata() -> None:
    value = CommandMetadata(idempotency_key="create-1", expected_version=3)
    assert value.expected_version == 3
    assert isinstance(value.correlation_id, uuid.UUID)


def test_initial_seed_contains_all_units_roles_and_example_profiles() -> None:
    assert len(UNITS) == 7
    assert len(ROLES) == 11
    assert {item[0] for item in PROFILES} == {
        "requirements-analyst-primary",
        "python-platform-engineer",
        "independent-patch-reviewer",
    }
    assert "approve-integration" in PROFILES[1][-1]


def test_organization_contract_routes_are_registered() -> None:
    paths = {f"/api/v1{route.path}" for route in organization_router.routes}
    required = {
        "/api/v1/organizations",
        "/api/v1/organizations/{organization_id}",
        "/api/v1/organizations/{organization_id}/units",
        "/api/v1/organizations/{organization_id}/roles",
        "/api/v1/organizations/{organization_id}/agents",
        "/api/v1/roles/{role_id}/versions",
        "/api/v1/role-versions/{version_id}/activate",
        "/api/v1/agents/{agent_id}/versions",
        "/api/v1/agent-versions/{version_id}/approve",
        "/api/v1/agents/{agent_id}/assignments",
        "/api/v1/authority/evaluate",
        "/api/v1/crews/compose",
    }
    assert required <= paths


def test_organization_identity_and_policy_are_required() -> None:
    columns = OrganizationModel.__table__.c
    assert columns.organization_key.unique is True
    assert columns.policy_set_id.nullable is False
