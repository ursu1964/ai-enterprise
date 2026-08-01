from dataclasses import dataclass
from datetime import datetime

from ai_enterprise.domain.organization.agent_profile import AgentProfile
from ai_enterprise.domain.organization.assignment import AgentAssignment
from ai_enterprise.domain.organization.capability import AGENT_PROHIBITED_TOOL_PERMISSIONS
from ai_enterprise.domain.organization.enums import AgentStatus, Availability, OrganizationStatus
from ai_enterprise.domain.organization.organization import Organization
from ai_enterprise.domain.organization.profile_version import AgentProfileVersion
from ai_enterprise.domain.organization.role import RoleVersion


@dataclass(frozen=True)
class EligibilityFinding:
    code: str
    message: str


@dataclass(frozen=True)
class AssignmentEligibility:
    eligible: bool
    findings: tuple[EligibilityFinding, ...]


@dataclass(frozen=True)
class EligibilityContext:
    organization: Organization
    agent: AgentProfile
    profile_version: AgentProfileVersion
    role: RoleVersion
    assignment: AgentAssignment
    now: datetime
    required_capabilities: frozenset[str] = frozenset()
    required_tools: frozenset[str] = frozenset()
    knowledge_policy_sufficient: bool = True
    model_policy_compatible: bool = True
    separation_conflict: bool = False
    active_runs: int = 0
    maximum_active_runs: int = 1


class AssignmentEligibilityService:
    def evaluate(self, context: EligibilityContext) -> AssignmentEligibility:
        findings: list[EligibilityFinding] = []
        if (
            context.organization.status is not OrganizationStatus.ACTIVE
            or context.agent.status is not AgentStatus.ACTIVE
            or context.agent.availability in {Availability.SUSPENDED, Availability.OFFLINE}
        ):
            findings.append(EligibilityFinding("ASSIGN-001", "AGENT_INACTIVE"))
        if not context.role.is_active:
            findings.append(EligibilityFinding("ASSIGN-002", "ROLE_RETIRED"))
        if not context.profile_version.is_approved:
            findings.append(EligibilityFinding("ASSIGN-001", "PROFILE_VERSION_UNAPPROVED"))
        effective_grants = set(context.profile_version.capability_grants) & set(
            context.assignment.granted_capabilities
        )
        if not context.required_capabilities <= effective_grants:
            findings.append(EligibilityFinding("ASSIGN-003", "CAPABILITY_MISSING"))
        tools = set(context.profile_version.tool_permissions)
        if not context.required_tools <= tools or tools & AGENT_PROHIBITED_TOOL_PERMISSIONS:
            findings.append(
                EligibilityFinding("ASSIGN-004", "TOOL_PERMISSION_MISSING_OR_PROHIBITED")
            )
        if not context.knowledge_policy_sufficient:
            findings.append(EligibilityFinding("ASSIGN-005", "KNOWLEDGE_POLICY_INSUFFICIENT"))
        if context.separation_conflict:
            findings.append(EligibilityFinding("ASSIGN-006", "SEPARATION_OF_DUTIES_CONFLICT"))
        if context.active_runs >= context.maximum_active_runs:
            findings.append(EligibilityFinding("ASSIGN-007", "CONCURRENCY_LIMIT_REACHED"))
        if not context.model_policy_compatible:
            findings.append(EligibilityFinding("ASSIGN-008", "MODEL_POLICY_INCOMPATIBLE"))
        if not context.assignment.is_active_at(context.now):
            findings.append(EligibilityFinding("ASSIGN-009", "ASSIGNMENT_SCOPE_MISMATCH"))
        return AssignmentEligibility(not findings, tuple(findings))
