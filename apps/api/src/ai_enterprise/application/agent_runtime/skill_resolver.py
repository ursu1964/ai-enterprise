from dataclasses import dataclass
from uuid import UUID

from ai_enterprise.domain.agent_runtime.enums import BindingStatus
from ai_enterprise.domain.agent_runtime.skill import CapabilitySkillBinding, SkillVersion


@dataclass(frozen=True)
class SkillResolutionRequest:
    agent_profile_version_id: UUID
    assignment_id: UUID
    requested_capability: str
    workflow_type: str
    scope_id: UUID


@dataclass(frozen=True)
class SkillResolutionDecision:
    selected_skill_version_ids: tuple[UUID, ...]
    rejected_candidates: tuple[dict[str, str], ...]
    policy_version: str


class SkillResolver:
    """Pure deterministic resolver; capability authorization is an explicit input."""

    def resolve(
        self,
        *,
        request: SkillResolutionRequest,
        bindings: tuple[CapabilitySkillBinding, ...],
        skills: tuple[SkillVersion, ...],
        profile_skill_bundle: frozenset[UUID],
        effective_capabilities: frozenset[str],
        tool_permissions: frozenset[str],
        maximum_risk_level: str,
    ) -> SkillResolutionDecision:
        policy_versions = sorted(
            {
                binding.policy_version
                for binding in bindings
                if binding.capability_key == request.requested_capability
            }
        )
        policy_version = "+".join(policy_versions) if policy_versions else "deny-default"
        if request.requested_capability not in effective_capabilities:
            return SkillResolutionDecision(
                (), ({"skill": "*", "code": "SKILL-CAPABILITY-NOT-GRANTED"},), policy_version
            )
        by_id = {skill.id: skill for skill in skills}
        rejected: list[dict[str, str]] = []
        eligible: list[tuple[bool, SkillVersion]] = []
        risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        max_risk = risk_order.get(maximum_risk_level, -1)
        relevant = sorted(
            (
                binding
                for binding in bindings
                if binding.capability_key == request.requested_capability
                and binding.binding_status is BindingStatus.ACTIVE
            ),
            key=lambda item: str(item.skill_version_id),
        )
        for binding in relevant:
            skill = by_id.get(binding.skill_version_id)
            code: str | None = None
            if skill is None:
                code = "SKILL-VERSION-NOT-FOUND"
            elif skill.id not in profile_skill_bundle:
                code = "SKILL-NOT-IN-PROFILE-BUNDLE"
            elif not skill.is_executable:
                code = "SKILL-VERSION-NOT-EXECUTABLE"
            elif not set(skill.required_capabilities).issubset(effective_capabilities):
                code = "SKILL-REQUIRED-CAPABILITY-MISSING"
            elif not set(skill.required_tool_permissions).issubset(tool_permissions):
                code = "SKILL-TOOL-PERMISSION-MISSING"
            elif risk_order.get(skill.risk_level, 99) > max_risk:
                code = "SKILL-RISK-INCOMPATIBLE"
            if code is not None:
                rejected.append({"skill": str(binding.skill_version_id), "code": code})
            elif skill is not None:
                eligible.append((binding.explicit_assignment, skill))
        eligible.sort(
            key=lambda item: (
                -int(item[0]),
                item[1].policy_priority,
                risk_order.get(item[1].risk_level, 99),
                item[1].skill_key,
                -item[1].version_number,
                str(item[1].id),
            )
        )
        return SkillResolutionDecision(
            tuple(skill.id for _, skill in eligible), tuple(rejected), policy_version
        )
