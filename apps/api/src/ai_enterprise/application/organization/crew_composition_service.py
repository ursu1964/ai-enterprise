from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from ai_enterprise.domain.hashing import hash_json
from ai_enterprise.domain.organization.agent_profile import AgentProfile
from ai_enterprise.domain.organization.assignment import AgentAssignment
from ai_enterprise.domain.organization.enums import AgentStatus, Availability
from ai_enterprise.domain.organization.policies import CrewCompositionPolicy
from ai_enterprise.domain.organization.profile_version import AgentProfileVersion
from ai_enterprise.domain.organization.role import RoleVersion


@dataclass(frozen=True)
class CrewCandidate:
    agent: AgentProfile
    profile_version: AgentProfileVersion
    assignment: AgentAssignment
    role: RoleVersion
    current_workload: int = 0
    performance_band: int = 0
    separation_conflict: bool = False


@dataclass(frozen=True)
class CrewMember:
    agent_profile_id: UUID
    agent_profile_version_id: UUID
    assignment_id: UUID
    role_version_id: UUID
    capabilities: tuple[str, ...]
    configuration_hash: str


@dataclass(frozen=True)
class CrewManifest:
    crew_run_id: UUID
    workflow_type: str
    policy_version: str
    members: tuple[CrewMember, ...]
    manifest_hash: str


class CrewCompositionError(ValueError):
    pass


class CrewCompositionService:
    def compose(
        self,
        *,
        crew_run_id: UUID,
        workflow_type: str,
        policy: CrewCompositionPolicy,
        candidates: tuple[CrewCandidate, ...],
        now: datetime,
    ) -> CrewManifest:
        selected: list[CrewCandidate] = []
        used_agents: set[UUID] = set()
        for role_key in (*policy.required_roles, *policy.optional_roles):
            eligible = [
                candidate
                for candidate in candidates
                if candidate.role.role_key == role_key
                and candidate.role.is_active
                and candidate.agent.status is AgentStatus.ACTIVE
                and candidate.agent.availability
                not in {Availability.SUSPENDED, Availability.OFFLINE, Availability.DRAINING}
                and candidate.profile_version.is_approved
                and candidate.assignment.is_active_at(now)
                and not candidate.separation_conflict
                and candidate.agent.id not in used_agents
            ]
            eligible.sort(
                key=lambda candidate: (
                    candidate.assignment.priority,
                    candidate.current_workload,
                    -candidate.performance_band,
                    candidate.assignment.activated_at or candidate.assignment.valid_from,
                    candidate.agent.agent_key,
                    str(candidate.assignment.id),
                )
            )
            if not eligible:
                if role_key in policy.required_roles:
                    raise CrewCompositionError(f"no eligible agent for required role {role_key}")
                continue
            if len(selected) >= policy.maximum_members:
                break
            selected.append(eligible[0])
            used_agents.add(eligible[0].agent.id)
        if len(selected) < policy.minimum_members:
            raise CrewCompositionError("crew does not satisfy minimum membership")
        role_keys = {candidate.role.role_key for candidate in selected}
        missing = set(policy.required_roles) - role_keys
        if missing:
            raise CrewCompositionError(f"crew is missing required roles: {sorted(missing)}")
        members = tuple(
            CrewMember(
                candidate.agent.id,
                candidate.profile_version.id,
                candidate.assignment.id,
                candidate.role.id,
                tuple(
                    sorted(
                        set(candidate.role.required_capabilities)
                        & set(candidate.profile_version.capability_grants)
                        & set(candidate.assignment.granted_capabilities)
                        - set(candidate.assignment.denied_capabilities)
                    )
                ),
                candidate.profile_version.configuration_hash,
            )
            for candidate in selected
        )
        document = {
            "crew_run_id": str(crew_run_id),
            "workflow_type": workflow_type,
            "policy_version": policy.version,
            "members": [
                {
                    "agent_profile_id": str(member.agent_profile_id),
                    "agent_profile_version_id": str(member.agent_profile_version_id),
                    "assignment_id": str(member.assignment_id),
                    "role_version_id": str(member.role_version_id),
                    "capabilities": list(member.capabilities),
                    "configuration_hash": member.configuration_hash,
                }
                for member in members
            ],
        }
        return CrewManifest(
            crew_run_id, workflow_type, policy.version, members, hash_json(document)
        )
