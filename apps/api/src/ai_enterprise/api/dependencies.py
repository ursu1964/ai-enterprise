import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.config import Settings, get_settings
from ai_enterprise.infrastructure.database.foundation_models import (
    ActorIdentityModel,
    AuthorityGrantModel,
)
from ai_enterprise.infrastructure.database.session import get_session
from ai_enterprise.infrastructure.security.local_activation import verify_identity_assertion

SessionDependency = Annotated[AsyncSession, Depends(get_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


@dataclass(frozen=True, slots=True)
class Actor:
    subject: str
    actor_type: str
    role: str
    capabilities: frozenset[str] = frozenset()
    trusted: bool = False
    scopes: frozenset[str] = frozenset()


async def get_actor(
    session: Annotated[AsyncSession | None, Depends(get_session)] = None,
    actor_id: Annotated[str | None, Header(alias="X-Actor-ID")] = None,
    actor_type: Annotated[str | None, Header(alias="X-Actor-Type")] = None,
    actor_role: Annotated[str | None, Header(alias="X-Actor-Role")] = None,
    proxy_timestamp: Annotated[str | None, Header(alias="X-Proxy-Timestamp")] = None,
    proxy_signature: Annotated[str | None, Header(alias="X-Proxy-Signature")] = None,
) -> Actor:
    if not actor_id or not actor_type or not actor_role:
        raise HTTPException(status_code=401, detail="Authenticated actor headers are required")
    settings = get_settings()
    trusted = False
    if settings.trusted_proxy_hmac_secret:
        try:
            timestamp = int(proxy_timestamp or "")
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid trusted proxy timestamp") from exc
        if abs(int(time.time()) - timestamp) > settings.trusted_proxy_max_clock_skew_seconds:
            raise HTTPException(status_code=401, detail="Expired trusted proxy assertion")
        if not proxy_signature or not verify_identity_assertion(
            secret=settings.trusted_proxy_hmac_secret.encode(),
            actor_id=actor_id,
            actor_type=actor_type,
            actor_role=actor_role,
            timestamp=timestamp,
            signature=proxy_signature,
        ):
            raise HTTPException(status_code=401, detail="Invalid trusted proxy signature")
        trusted = True
    elif settings.app_env.lower() in {"production", "staging"}:
        raise HTTPException(
            status_code=503, detail="Trusted proxy authentication is not configured"
        )

    if session is None:
        if settings.app_env.lower() in {"production", "staging"}:
            raise HTTPException(status_code=503, detail="Authority store is unavailable")
        return Actor(subject=actor_id, actor_type=actor_type, role=actor_role, trusted=trusted)

    identity = await session.scalar(
        select(ActorIdentityModel).where(
            ActorIdentityModel.subject == actor_id, ActorIdentityModel.enabled.is_(True)
        )
    )
    capabilities: frozenset[str] = frozenset()
    scopes: frozenset[str] = frozenset()
    durable_role = actor_role
    if identity is not None:
        now = datetime.now(UTC)
        grants = list(
            (
                await session.scalars(
                    select(AuthorityGrantModel).where(
                        AuthorityGrantModel.actor_id == identity.id,
                        AuthorityGrantModel.revoked_at.is_(None),
                        AuthorityGrantModel.valid_from <= now,
                        or_(
                            AuthorityGrantModel.valid_until.is_(None),
                            AuthorityGrantModel.valid_until > now,
                        ),
                    )
                )
            ).all()
        )
        capabilities = frozenset(item.capability for item in grants)
        scopes = frozenset(item.scope for item in grants)
        matching = next((item for item in grants if item.role == actor_role), None)
        if matching is None and settings.app_env.lower() in {"production", "staging"}:
            raise HTTPException(status_code=403, detail="No active authority grant")
        if matching is not None:
            durable_role = matching.role
    elif settings.app_env.lower() in {"production", "staging"}:
        raise HTTPException(status_code=403, detail="Unknown or disabled actor")
    return Actor(
        subject=actor_id,
        actor_type=actor_type,
        role=durable_role,
        capabilities=capabilities,
        trusted=trusted,
        scopes=scopes,
    )


ActorDependency = Annotated[Actor, Depends(get_actor)]
