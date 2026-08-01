from fastapi import APIRouter
from pydantic import BaseModel

from ai_enterprise.api.dependencies import ActorDependency

router = APIRouter(prefix="/foundation", tags=["production-foundation"])


class AuthorityContextResponse(BaseModel):
    subject: str
    actor_type: str
    role: str
    capabilities: list[str]
    trusted_proxy_assertion: bool


@router.get("/authority-context", response_model=AuthorityContextResponse)
async def authority_context(actor: ActorDependency) -> AuthorityContextResponse:
    return AuthorityContextResponse(
        subject=actor.subject,
        actor_type=actor.actor_type,
        role=actor.role,
        capabilities=sorted(actor.capabilities),
        trusted_proxy_assertion=actor.trusted,
    )
