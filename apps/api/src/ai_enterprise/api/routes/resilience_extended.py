from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ai_enterprise.api.dependencies import (
    Actor,
    ActorDependency,
    SessionDependency,
    require_capability,
)
from ai_enterprise.api.resilience_extended_schemas import GovernanceRecordRequest
from ai_enterprise.api.routes.resilience import _authorize
from ai_enterprise.application.audit.writer import AuditWriter
from ai_enterprise.application.resilience.extended_service import InstitutionalGovernanceValidator
from ai_enterprise.domain.resilience.enums import Capability
from ai_enterprise.domain.resilience.policies import ResiliencePolicyError
from ai_enterprise.infrastructure.resilience.extended_models import (
    InstitutionalGovernanceRecordModel,
)
from ai_enterprise.infrastructure.resilience.repository import SqlAlchemyResilienceRepository

router = APIRouter(prefix="/resilience/governance", tags=["institutional-resilience"])

def _require_governance_capability(actor: Actor, action: str, record_type: str) -> None:
    if actor.actor_type != "human":
        raise HTTPException(status_code=403, detail="Human governance authority is required")
    if record_type not in InstitutionalGovernanceValidator.RECORD_TYPES:
        raise HTTPException(status_code=404, detail="Unknown governance record type")
    capabilities = (
        f"resilience.governance.{record_type}.{action}",
        f"resilience.governance.{action}",
    )
    for capability in capabilities:
        try:
            require_capability(actor, capability, "global")
            return
        except HTTPException:
            continue
    raise HTTPException(status_code=403, detail="Governance capability is missing")


@router.post("/{record_type}", status_code=201)
async def create_governance_record(
    record_type: str,
    request: GovernanceRecordRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, object]:
    _require_governance_capability(actor, "write", record_type)
    await _authorize(SqlAlchemyResilienceRepository(session), Capability.GRANT_APPROVAL, actor)
    try:
        InstitutionalGovernanceValidator().validate(
            record_type=record_type,
            status=request.status,
            payload=request.payload,
            evidence_hash=request.provider_evidence_hash,
            actor=actor.subject,
        )
    except (ResiliencePolicyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = InstitutionalGovernanceRecordModel(
        id=uuid.uuid4(),
        record_type=record_type,
        recorded_by=actor.subject,
        **request.model_dump(),
    )
    session.add(row)
    await AuditWriter(session).append_event(
        stream_id=f"resilience.governance:{record_type}",
        project_id=None,
        event_type=f"resilience.governance.{record_type}_recorded",
        actor_type="human",
        actor_id=actor.subject,
        payload={
            "record_id": str(row.id),
            "status": row.status,
            "policy_version": row.policy_version,
            "provider_evidence_present": bool(row.provider_evidence_hash),
        },
    )
    await session.commit()
    return {"id": row.id, "record_type": row.record_type, "status": row.status}


@router.get("/{record_type}")
async def list_governance_records(
    record_type: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> list[dict[str, object]]:
    _require_governance_capability(actor, "read", record_type)
    rows = (
        (
            await session.execute(
                select(InstitutionalGovernanceRecordModel)
                .where(InstitutionalGovernanceRecordModel.record_type == record_type)
                .order_by(InstitutionalGovernanceRecordModel.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": row.id,
            "status": row.status,
            "policy_version": row.policy_version,
            "payload": row.payload,
            "provider_evidence_present": bool(row.provider_evidence_hash),
        }
        for row in rows
    ]
