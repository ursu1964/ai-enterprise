from fastapi import HTTPException

from ai_enterprise.api.dependencies import Actor
from ai_enterprise.application.change_management.dto import GovernanceActor

_CAPABILITY_ROLES = {
    "change.create": {"change_proposer"},
    "change.submit": {"change_proposer"},
    "change.assess": {"change_assessor"},
    "change.validate": {"change_validator"},
    "change.plan": {"change_planner", "change_validator", "change_approver"},
    "change.decide": {"change_approver"},
    "change.observe": {"change_observer", "change_approver"},
    "change.outcome": {"change_approver"},
    "change.read": {
        "change_proposer",
        "change_planner",
        "change_assessor",
        "change_validator",
        "change_approver",
        "change_observer",
        "audit_reader",
    },
}


def governed_change_actor(actor: Actor, capability: str) -> GovernanceActor:
    allowed = _CAPABILITY_ROLES[capability]
    if actor.role not in allowed:
        raise HTTPException(status_code=403, detail=f"Missing capability: {capability}")
    if (
        capability in {"change.submit", "change.decide", "change.outcome"}
        and actor.actor_type != "human"
    ):
        raise HTTPException(status_code=403, detail="A human governance actor is required")
    return GovernanceActor(
        subject=actor.subject,
        roles=frozenset({actor.role}),
        metadata={"actor_type": actor.actor_type},
    )
