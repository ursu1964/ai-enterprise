from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import UniqueConstraint

from ai_enterprise.api.recovery_schemas import (
    RecoveryIncidentRequest,
    RollbackApprovalRequest,
)
from ai_enterprise.application.recovery.service import RecoveryControlPlaneService
from ai_enterprise.domain.recovery.exceptions import RollbackApprovalHumanRequired
from ai_enterprise.infrastructure.database.models import (
    Base,
    RecoveryAttemptModel,
    RollbackApprovalModel,
    RollbackRecordModel,
)


def test_recovery_schema_requires_bounded_incident_and_approved_decision() -> None:
    incident = RecoveryIncidentRequest(
        severity="high",
        summary="Regression observed",
        details="Requests fail after integration.",
        affected_environment="production",
        detected_at=datetime.now(UTC),
    )
    assert incident.severity == "high"
    with pytest.raises(ValidationError):
        RollbackApprovalRequest(decision="denied", reason="Not this endpoint")


@pytest.mark.asyncio
async def test_agent_cannot_create_recovery_incident() -> None:
    session = AsyncMock()
    service = RecoveryControlPlaneService(session)
    with pytest.raises(RollbackApprovalHumanRequired):
        await service.create_incident(
            integration_attempt_id=uuid4(),
            actor_subject="agent:implementation",
            actor_type="agent",
            actor_role="incident_reporter",
            severity="high",
            summary="Regression",
            details="Observed failure",
            affected_environment="production",
            detected_at=datetime.now(UTC),
            external_reference=None,
        )
    session.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_only_rollback_approver_can_approve() -> None:
    session = AsyncMock()
    with pytest.raises(RollbackApprovalHumanRequired):
        await RecoveryControlPlaneService(session).approve(
            assessment_id=uuid4(),
            actor_subject="human:operator",
            actor_type="human",
            actor_role="recovery_operator",
            reason="Attempted privilege crossover",
        )
    session.scalar.assert_not_awaited()


def test_recovery_tables_bind_one_record_and_attempt() -> None:
    rollback_uniques = {
        column.name
        for constraint in RollbackRecordModel.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
        for column in constraint.columns
    }
    attempt_uniques = {
        column.name
        for constraint in RecoveryAttemptModel.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
        for column in constraint.columns
    }
    assert {"integration_attempt_id", "integration_commit_id"} <= rollback_uniques
    assert "rollback_approval_id" in attempt_uniques
    assert "rollback_approvals" in Base.metadata.tables
    assert RollbackApprovalModel.__table__.c.approval_binding_sha256.nullable is False
