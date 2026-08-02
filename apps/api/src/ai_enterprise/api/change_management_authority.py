from fastapi import HTTPException

from ai_enterprise.api.dependencies import Actor, require_capability
from ai_enterprise.application.change_management.dto import GovernanceActor


def governed_change_actor(actor: Actor, capability: str) -> GovernanceActor:
    try:
        require_capability(actor, capability, "global")
    except HTTPException as exc:
        raise HTTPException(status_code=403, detail=f"Missing capability: {capability}") from exc
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
