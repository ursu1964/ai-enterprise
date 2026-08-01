from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ActivityParticipation:
    actor_id: UUID
    activity_type: str
    scope_type: str
    scope_id: UUID
    occurred_at: datetime
    agent_profile_version_id: UUID | None = None
    artifact_hash: str | None = None


@dataclass(frozen=True)
class SeparationOfDutiesRule:
    key: str
    version: str
    first_activity: str
    second_activity: str
    scope_relation: str = "same-scope"
    enforcement: str = "deny"

    def conflicts(self, *, requested_activity: str, prior: ActivityParticipation) -> bool:
        pair = {self.first_activity, self.second_activity}
        return (
            self.enforcement == "deny"
            and requested_activity in pair
            and prior.activity_type in pair
            and requested_activity != prior.activity_type
        )


DEFAULT_SEPARATION_RULES = (
    SeparationOfDutiesRule(
        "requirements-author-approval", "1", "author-requirements", "approve-requirements"
    ),
    SeparationOfDutiesRule(
        "architecture-author-approval", "1", "author-architecture", "approve-architecture"
    ),
    SeparationOfDutiesRule(
        "decomposer-final-approval", "1", "decompose-work", "approve-decomposition"
    ),
    SeparationOfDutiesRule(
        "implementation-independent-review", "1", "implement-work-package", "review-generated-patch"
    ),
    SeparationOfDutiesRule(
        "reviewer-integration-approval", "1", "review-generated-patch", "approve-integration"
    ),
    SeparationOfDutiesRule(
        "integration-self-approval", "1", "execute-integration", "approve-integration"
    ),
)


def find_conflicts(
    *,
    actor_id: UUID,
    requested_activity: str,
    scope_type: str,
    scope_id: UUID,
    participations: tuple[ActivityParticipation, ...],
    rules: tuple[SeparationOfDutiesRule, ...] = DEFAULT_SEPARATION_RULES,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                rule.key
                for prior in participations
                if prior.actor_id == actor_id
                and prior.scope_type == scope_type
                and prior.scope_id == scope_id
                for rule in rules
                if rule.conflicts(requested_activity=requested_activity, prior=prior)
            }
        )
    )
