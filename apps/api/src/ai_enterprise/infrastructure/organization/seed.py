import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.organization_persistence_service import canonical_hash
from ai_enterprise.infrastructure.organization.models import (
    AgentAssignmentModel,
    AgentProfileModel,
    AgentProfileVersionModel,
    CapabilityModel,
    OrganizationalUnitModel,
    OrganizationModel,
    RoleModel,
    RoleVersionModel,
)

SEED_NAMESPACE = uuid.UUID("8a6e7df4-5d89-4a0c-932a-6696448fb7e2")
ORGANIZATION_KEY = "ai-enterprise-software-company"
UNITS = (
    ("product-analysis", "Product and Analysis"),
    ("architecture", "Architecture"),
    ("engineering", "Engineering"),
    ("security-assurance", "Security and Assurance"),
    ("quality-engineering", "Quality Engineering"),
    ("execution-operations", "Execution Operations"),
    ("integration-control", "Integration Control"),
)
ROLES = (
    "requirements-analyst",
    "requirements-reviewer",
    "system-architect",
    "architecture-reviewer",
    "work-package-planner",
    "implementation-engineer",
    "test-engineer",
    "patch-reviewer",
    "security-reviewer",
    "execution-scheduler",
    "integration-executor",
)
PROFILES = (
    (
        "requirements-analyst-primary",
        "Requirements analyst",
        "product-analysis",
        "requirements-analyst",
        (
            "read-project-manifest",
            "analyze-requirements",
            "identify-ambiguities",
            "create-requirements-candidate",
        ),
        ("project_metadata.read", "artifact.read", "artifact.create_candidate"),
        (),
    ),
    (
        "python-platform-engineer",
        "Python platform engineer",
        "engineering",
        "implementation-engineer",
        (
            "read-approved-work-package",
            "modify-workspace-files",
            "run-approved-commands",
            "generate-patch",
        ),
        (
            "repository_snapshot.read",
            "execution_workspace.write",
            "approved_command.execute",
            "patch.create",
        ),
        ("review-own-patch", "approve-integration"),
    ),
    (
        "independent-patch-reviewer",
        "Independent patch reviewer",
        "quality-engineering",
        "patch-reviewer",
        (
            "read-patch",
            "review-correctness",
            "review-scope",
            "review-test-evidence",
            "create-review-candidate",
        ),
        ("artifact.read", "repository_snapshot.read", "review_record.create"),
        (),
    ),
)


def _id(key: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, key)


async def seed_organization(session: AsyncSession) -> uuid.UUID:
    now = datetime.now(UTC)
    organization_id = _id(f"organization:{ORGANIZATION_KEY}")
    if await session.get(OrganizationModel, organization_id) is None:
        session.add(
            OrganizationModel(
                id=organization_id,
                organization_key=ORGANIZATION_KEY,
                name="AI Enterprise Software Company",
                status="active",
                policy_set_id=_id("policy:organizational-v1"),
                version=1,
            )
        )
    units: dict[str, uuid.UUID] = {}
    for unit_key, name in UNITS:
        unit_id = _id(f"unit:{unit_key}")
        units[unit_key] = unit_id
        if await session.get(OrganizationalUnitModel, unit_id) is None:
            session.add(
                OrganizationalUnitModel(
                    id=unit_id,
                    organization_id=organization_id,
                    parent_unit_id=None,
                    unit_key=unit_key,
                    name=name,
                    purpose=f"Governed {name.lower()} function",
                    status="active",
                )
            )
    role_versions: dict[str, uuid.UUID] = {}
    for role_key in ROLES:
        role_id, version_id = _id(f"role:{role_key}"), _id(f"role-version:{role_key}:1")
        role_versions[role_key] = version_id
        document = {
            "role_key": role_key,
            "capabilities": [],
            "denied_capabilities": [],
            "human_only_approvals": False,
            "policy_version": "organizational-v1",
        }
        if await session.get(RoleModel, role_id) is None:
            session.add(
                RoleModel(
                    id=role_id,
                    organization_id=organization_id,
                    role_key=role_key,
                    name=role_key.replace("-", " ").title(),
                    current_version_id=version_id,
                    status="active",
                )
            )
            session.add(
                RoleVersionModel(
                    id=version_id,
                    role_id=role_id,
                    version_number=1,
                    role_document=document,
                    role_hash=canonical_hash(document),
                    status="active",
                )
            )
    await session.flush()
    scope_id = _id("scope:organization")
    for agent_key, display_name, unit_key, role_key, capabilities, tools, denied in PROFILES:
        for capability in (*capabilities, *denied):
            existing = await session.get(CapabilityModel, capability)
            if existing is None:
                session.add(
                    CapabilityModel(
                        capability_key=capability,
                        category="organizational",
                        description=capability.replace("-", " "),
                        human_only=capability == "approve-integration",
                        high_risk=capability in {"modify-workspace-files", "approve-integration"},
                        capability_document={"key": capability},
                        version="1",
                    )
                )
        profile_id, version_id, assignment_id = (
            _id(f"agent:{agent_key}"),
            _id(f"agent-version:{agent_key}:1"),
            _id(f"assignment:{agent_key}:{role_key}"),
        )
        configuration = {
            "agent_key": agent_key,
            "roles": [role_key],
            "capabilities": list(capabilities),
            "tool_permissions": list(tools),
            "denied_capabilities": list(denied),
            "knowledge_policy": "bounded-project-v1",
            "model_policy": "approved-local-or-enterprise-v1",
            "concurrency_policy": {
                "maximum_active_runs": 1,
                "maximum_high_risk_runs": 1,
                "allow_parallel_projects": False,
            },
        }
        if await session.get(AgentProfileModel, profile_id) is None:
            session.add(
                AgentProfileModel(
                    id=profile_id,
                    organization_id=organization_id,
                    home_unit_id=units[unit_key],
                    agent_key=agent_key,
                    display_name=display_name,
                    status="active",
                    current_version_id=version_id,
                    state_version=1,
                )
            )
            await session.flush()
            session.add(
                AgentProfileVersionModel(
                    id=version_id,
                    agent_profile_id=profile_id,
                    version_number=1,
                    configuration_document=configuration,
                    configuration_hash=canonical_hash(configuration),
                    approval_status="approved",
                )
            )
            await session.flush()
            assignment_document = {
                "role": role_key,
                "scope_type": "organization",
                "scope_id": str(scope_id),
                "capabilities": list(capabilities),
                "denied_capabilities": list(denied),
                "priority": 100,
            }
            session.add(
                AgentAssignmentModel(
                    id=assignment_id,
                    organization_id=organization_id,
                    agent_profile_id=profile_id,
                    agent_profile_version_id=version_id,
                    role_version_id=role_versions[role_key],
                    scope_type="organization",
                    scope_id=scope_id,
                    status="active",
                    granted_capabilities=list(capabilities),
                    denied_capabilities=list(denied),
                    valid_from=now,
                    valid_until=None,
                    assigned_by=_id("actor:bootstrap"),
                    assignment_document=assignment_document,
                    assignment_hash=canonical_hash(assignment_document),
                )
            )
            await session.flush()
    await session.flush()
    return organization_id
