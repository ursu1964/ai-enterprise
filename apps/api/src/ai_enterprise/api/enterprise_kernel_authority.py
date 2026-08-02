from fastapi import HTTPException

from ai_enterprise.api.dependencies import Actor, require_capability
from ai_enterprise.application.enterprise_kernel.dto import KernelActor


def enterprise_kernel_actor(actor: Actor, capability: str) -> KernelActor:
    if actor.actor_type != "human":
        raise HTTPException(status_code=403, detail="Enterprise kernel decisions require a human")
    try:
        require_capability(actor, capability, "global")
    except HTTPException as exc:
        raise HTTPException(status_code=403, detail=f"Missing capability: {capability}") from exc
    return KernelActor(subject=actor.subject, roles=frozenset({actor.role}))
