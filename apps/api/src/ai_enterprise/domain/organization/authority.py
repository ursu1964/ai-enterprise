from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from .agent_profile import AgentProfile
from .assignment import AgentAssignment
from .capability import CapabilityDefinition
from .enums import AgentStatus, OrganizationStatus
from .organization import Organization
from .profile_version import AgentProfileVersion
from .role import RoleVersion
from .separation_of_duties import ActivityParticipation, find_conflicts


@dataclass(frozen=True)
class AuthorityRequest:
    actor_id: UUID
    capability: str
    scope_type: str
    scope_id: UUID
    action_context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthorityDecision:
    allowed: bool
    code: str
    reasons: tuple[dict[str, Any], ...]
    policy_versions: tuple[str, ...]


@dataclass(frozen=True)
class EffectiveCapabilities:
    allowed: frozenset[str]
    reasons: tuple[dict[str, Any], ...]
    policy_versions: tuple[str, ...]


@dataclass(frozen=True)
class AuthorityContext:
    organization: Organization
    actor: AgentProfile
    profile_version: AgentProfileVersion
    assignments: tuple[AgentAssignment, ...]
    roles: dict[UUID, RoleVersion]
    capabilities: dict[str, CapabilityDefinition]
    organization_policy: frozenset[str]
    project_policy: frozenset[str]
    workflow_policy: frozenset[str]
    policy_versions: tuple[str, ...]
    now: Any
    participations: tuple[ActivityParticipation, ...] = ()


class CapabilityResolver:
    def resolve(self, *, context: AuthorityContext) -> EffectiveCapabilities:
        active = tuple(
            assignment
            for assignment in context.assignments
            if assignment.is_active_at(context.now)
            and assignment.agent_profile_version_id == context.profile_version.id
        )
        role_allowed: set[str] = set()
        assignment_grants: set[str] = set()
        explicit_denials: set[str] = set()
        for assignment in active:
            role = context.roles.get(assignment.role_version_id)
            if role is None or not role.is_active:
                continue
            role_allowed.update(role.required_capabilities)
            role_allowed.difference_update(role.forbidden_capabilities)
            assignment_grants.update(assignment.granted_capabilities)
            explicit_denials.update(assignment.denied_capabilities)
        allowed = (
            role_allowed
            & set(context.profile_version.capability_grants)
            & assignment_grants
            & set(context.organization_policy)
            & set(context.project_policy)
            & set(context.workflow_policy)
        ) - explicit_denials
        return EffectiveCapabilities(
            allowed=frozenset(allowed),
            reasons=({"effective_capabilities": sorted(allowed)},),
            policy_versions=context.policy_versions,
        )


class AuthorityService:
    def __init__(self, resolver: CapabilityResolver | None = None) -> None:
        self.resolver = resolver or CapabilityResolver()

    def evaluate(self, request: AuthorityRequest, context: AuthorityContext) -> AuthorityDecision:
        if context.actor.id != request.actor_id:
            return self._deny(
                "AUTH-ACTOR-MISMATCH", "authority context does not match actor", context
            )
        if context.organization.status is not OrganizationStatus.ACTIVE:
            return self._deny("AUTH-ORGANIZATION-INACTIVE", "organization is not active", context)
        if context.actor.status is not AgentStatus.ACTIVE:
            return self._deny("AUTH-ACTOR-INACTIVE", "agent profile is not active", context)
        if not context.profile_version.is_approved:
            return self._deny(
                "AUTH-PROFILE-VERSION-UNAPPROVED",
                "profile version is not approved",
                context,
            )
        assignments = tuple(
            assignment
            for assignment in context.assignments
            if assignment.covers(scope_type=request.scope_type, scope_id=request.scope_id)
            and assignment.is_active_at(context.now)
        )
        if not assignments:
            return self._deny(
                "AUTH-NO-ACTIVE-ASSIGNMENT",
                "No active assignment covers the requested scope.",
                context,
            )
        narrowed = AuthorityContext(**{**context.__dict__, "assignments": assignments})
        definition = context.capabilities.get(request.capability)
        if definition is None:
            return self._deny("AUTH-CAPABILITY-UNKNOWN", "capability is not registered", context)
        if definition.human_only:
            return self._deny(
                "AUTH-HUMAN-ONLY", "capability is reserved for a human principal", context
            )
        activity = request.action_context.get("activity_type")
        if isinstance(activity, str):
            conflicts = find_conflicts(
                actor_id=request.actor_id,
                requested_activity=activity,
                scope_type=request.scope_type,
                scope_id=request.scope_id,
                participations=context.participations,
            )
            if conflicts:
                return AuthorityDecision(
                    False,
                    "AUTH-SEPARATION-OF-DUTIES",
                    ({"rules": list(conflicts)},),
                    context.policy_versions,
                )
        effective = self.resolver.resolve(context=narrowed)
        if request.capability not in effective.allowed:
            return AuthorityDecision(
                False, "AUTH-CAPABILITY-DENIED", effective.reasons, effective.policy_versions
            )
        return AuthorityDecision(True, "AUTH-ALLOWED", effective.reasons, effective.policy_versions)

    @staticmethod
    def _deny(code: str, message: str, context: AuthorityContext) -> AuthorityDecision:
        return AuthorityDecision(False, code, ({"message": message},), context.policy_versions)
