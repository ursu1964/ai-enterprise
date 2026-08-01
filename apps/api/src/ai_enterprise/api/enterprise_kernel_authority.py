from fastapi import HTTPException

from ai_enterprise.api.dependencies import Actor
from ai_enterprise.application.enterprise_kernel.dto import KernelActor


def enterprise_kernel_actor(actor: Actor, capability: str) -> KernelActor:
    if actor.actor_type != "human":
        raise HTTPException(status_code=403, detail="Enterprise kernel decisions require a human")
    allowed = capability in actor.capabilities or actor.role in {
        "enterprise_kernel_admin",
        "governance_admin",
        "platform_owner",
    }
    if not allowed:
        raise HTTPException(status_code=403, detail=f"Missing capability: {capability}")
    return KernelActor(subject=actor.subject, roles=frozenset({actor.role}))
