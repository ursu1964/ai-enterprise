from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ai_enterprise.api.dependencies import ActorDependency, SessionDependency
from ai_enterprise.api.resilience_extended_schemas import GovernanceRecordRequest
from ai_enterprise.api.routes.resilience import _authorize
from ai_enterprise.application.resilience.extended_service import InstitutionalGovernanceValidator
from ai_enterprise.domain.resilience.enums import Capability
from ai_enterprise.domain.resilience.policies import ResiliencePolicyError
from ai_enterprise.infrastructure.database.models import AuditEventModel
from ai_enterprise.infrastructure.resilience.extended_models import (
    InstitutionalGovernanceRecordModel,
)
from ai_enterprise.infrastructure.resilience.repository import SqlAlchemyResilienceRepository

router = APIRouter(prefix="/resilience/governance", tags=["institutional-resilience"])

_ROLES = {
    "region_site": "resilience_admin",
    "region_ownership_lease": "region_authority",
    "residency_policy": "sovereignty_authority",
    "execution_zone": "sovereignty_authority",
    "model_provider": "model_governance_authority",
    "model_definition": "model_governance_authority",
    "model_evaluation": "model_governance_authority",
    "model_substitution": "model_governance_authority",
    "crypto_profile": "cryptographic_authority",
    "crypto_key_version": "cryptographic_authority",
    "crypto_rotation": "cryptographic_authority",
    "key_revocation": "cryptographic_authority",
    "signature_record": "cryptographic_authority",
    "authority_succession": "identity_authority",
    "emergency_grant": "identity_authority",
    "knowledge_assessment": "continuity_authority",
    "institutional_runbook": "continuity_authority",
    "runbook_rehearsal": "continuity_authority",
    "vendor_exit_plan": "vendor_risk_authority",
    "vendor_exit_rehearsal": "vendor_risk_authority",
    "technology_substitution": "vendor_risk_authority",
    "archive_verification": "archive_authority",
    "backup_archive_replication": "archive_authority",
    "resilience_experiment": "chaos_authority",
    "artifact_migration": "preservation_authority",
    "audit_checkpoint": "archive_authority",
    "crisis_activation": "crisis_commander",
    "crisis_exit_review": "crisis_review_authority",
}


@router.post("/{record_type}", status_code=201)
async def create_governance_record(
    record_type: str,
    request: GovernanceRecordRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, object]:
    role = _ROLES.get(record_type)
    if actor.actor_type != "human" or role is None or actor.role != role:
        raise HTTPException(status_code=403, detail="Required institutional authority is missing")
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
    session.add(
        AuditEventModel(
            id=uuid.uuid4(),
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
    )
    await session.commit()
    return {"id": row.id, "record_type": row.record_type, "status": row.status}


@router.get("/{record_type}")
async def list_governance_records(
    record_type: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> list[dict[str, object]]:
    if actor.actor_type != "human" or actor.role not in {
        "resilience_auditor",
        _ROLES.get(record_type),
    }:
        raise HTTPException(status_code=403, detail="Governance read authority is missing")
    if record_type not in InstitutionalGovernanceValidator.RECORD_TYPES:
        raise HTTPException(status_code=404, detail="Unknown governance record type")
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
