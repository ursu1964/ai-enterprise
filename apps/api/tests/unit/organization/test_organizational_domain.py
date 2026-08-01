from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from ai_enterprise.application.organization.crew_composition_service import (
    CrewCandidate,
    CrewCompositionService,
)
from ai_enterprise.domain.organization.agent_profile import AgentProfile
from ai_enterprise.domain.organization.assignment import AgentAssignment
from ai_enterprise.domain.organization.authority import (
    AuthorityContext,
    AuthorityRequest,
    AuthorityService,
)
from ai_enterprise.domain.organization.capability import CapabilityDefinition
from ai_enterprise.domain.organization.enums import (
    AgentStatus,
    AssignmentStatus,
    OrganizationStatus,
    RoleStatus,
)
from ai_enterprise.domain.organization.organization import Organization
from ai_enterprise.domain.organization.policies import CrewCompositionPolicy
from ai_enterprise.domain.organization.profile_version import AgentProfileVersion
from ai_enterprise.domain.organization.role import RoleVersion
from ai_enterprise.domain.organization.separation_of_duties import ActivityParticipation

NOW = datetime(2026, 7, 31, tzinfo=UTC)


def _objects(agent_key: str = "architect-a") -> tuple[
    Organization, AgentProfile, AgentProfileVersion, RoleVersion, AgentAssignment
]:
    organization = Organization(uuid4(), "Enterprise", OrganizationStatus.ACTIVE, uuid4())
    agent = AgentProfile(
        uuid4(), organization.id, agent_key, agent_key, AgentStatus.ACTIVE, uuid4(), uuid4()
    )
    profile = AgentProfileVersion(
        agent.current_version_id,
        agent.id,
        1,
        (),
        ("assess_architecture", "approve_architecture"),
        ("artifact.read",),
        uuid4(),
        uuid4(),
        (),
        uuid4(),
        uuid4(),
        "pending",
        NOW,
        "approved",
    )
    profile = replace(profile, configuration_hash=profile.calculated_hash())
    role = RoleVersion(
        uuid4(),
        uuid4(),
        "system-architect",
        1,
        ("architecture-analysis",),
        ("assess_architecture", "approve_architecture"),
        status=RoleStatus.ACTIVE,
    )
    assignment = AgentAssignment(
        uuid4(),
        organization.id,
        agent.id,
        profile.id,
        role.id,
        "project",
        uuid4(),
        AssignmentStatus.ACTIVE,
        NOW - timedelta(days=1),
        None,
        ("assess_architecture", "approve_architecture"),
        (),
        uuid4(),
        "hash",
        activated_at=NOW - timedelta(days=1),
    )
    return organization, agent, profile, role, assignment


def _context(
    objects: tuple[Organization, AgentProfile, AgentProfileVersion, RoleVersion, AgentAssignment],
    *,
    participations: tuple[ActivityParticipation, ...] = (),
) -> AuthorityContext:
    organization, agent, profile, role, assignment = objects
    policies = frozenset({"assess_architecture", "approve_architecture"})
    return AuthorityContext(
        organization,
        agent,
        profile,
        (assignment,),
        {role.id: role},
        {
            "assess_architecture": CapabilityDefinition("assess_architecture", "analysis", ""),
            "approve_architecture": CapabilityDefinition(
                "approve_architecture", "approval", "", human_only=True
            ),
        },
        policies,
        policies,
        policies,
        ("organization-v1", "project-v1", "workflow-v1"),
        NOW,
        participations,
    )


def test_authority_is_intersection_and_human_approval_fails_closed() -> None:
    objects = _objects()
    context = _context(objects)
    assignment = objects[-1]
    service = AuthorityService()
    allowed = service.evaluate(
        AuthorityRequest(objects[1].id, "assess_architecture", "project", assignment.scope_id),
        context,
    )
    human_only = service.evaluate(
        AuthorityRequest(objects[1].id, "approve_architecture", "project", assignment.scope_id),
        context,
    )
    missing_policy = replace(context, workflow_policy=frozenset())
    denied = service.evaluate(
        AuthorityRequest(objects[1].id, "assess_architecture", "project", assignment.scope_id),
        missing_policy,
    )
    assert (allowed.allowed, allowed.code) == (True, "AUTH-ALLOWED")
    assert (human_only.allowed, human_only.code) == (False, "AUTH-HUMAN-ONLY")
    assert (denied.allowed, denied.code) == (False, "AUTH-CAPABILITY-DENIED")


def test_separation_of_duties_denies_architecture_self_approval() -> None:
    objects = _objects()
    assignment = objects[-1]
    participation = ActivityParticipation(
        objects[1].id,
        "author-architecture",
        "project",
        assignment.scope_id,
        NOW,
    )
    decision = AuthorityService().evaluate(
        AuthorityRequest(
            objects[1].id,
            "assess_architecture",
            "project",
            assignment.scope_id,
            {"activity_type": "approve-architecture"},
        ),
        _context(objects, participations=(participation,)),
    )
    assert (decision.allowed, decision.code) == (False, "AUTH-SEPARATION-OF-DUTIES")


def test_crew_selection_is_deterministic_and_uses_stable_tie_breaker() -> None:
    first = _objects("agent-b")
    second = _objects("agent-a")
    # Put both candidates into the same logical run scope and role.
    second_assignment = replace(
        second[-1], scope_id=first[-1].scope_id, role_version_id=first[-2].id
    )
    second_role = replace(first[-2])
    candidates = (
        CrewCandidate(first[1], first[2], first[-1], first[-2]),
        CrewCandidate(second[1], second[2], second_assignment, second_role),
    )
    policy = CrewCompositionPolicy("v1", ("system-architect",), minimum_members=1)
    run_id = UUID("00000000-0000-0000-0000-000000000001")
    service = CrewCompositionService()
    forward = service.compose(
        crew_run_id=run_id,
        workflow_type="architecture-analysis",
        policy=policy,
        candidates=candidates,
        now=NOW,
    )
    reverse = service.compose(
        crew_run_id=run_id,
        workflow_type="architecture-analysis",
        policy=policy,
        candidates=tuple(reversed(candidates)),
        now=NOW,
    )
    assert forward == reverse
    assert forward.members[0].agent_profile_id == second[1].id
