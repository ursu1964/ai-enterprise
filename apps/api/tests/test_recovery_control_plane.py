from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import UniqueConstraint

from ai_enterprise.api.dependencies import Actor
from ai_enterprise.api.recovery_schemas import (
    RecoveryIncidentRequest,
    RollbackApprovalRequest,
)
from ai_enterprise.api.routes.recovery import (
    _require_recovery_action,
    get_assessment,
    get_attempt,
    get_incident,
)
from ai_enterprise.application.recovery.service import RecoveryControlPlaneService
from ai_enterprise.domain.recovery.exceptions import RollbackApprovalHumanRequired
from ai_enterprise.infrastructure.database.models import (
    Base,
    RecoveryAssessmentModel,
    RecoveryAttemptModel,
    RecoveryIncidentModel,
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


class RecoveryReadSession:
    def __init__(self, rows: dict[tuple[type, object], object]) -> None:
        self.rows = rows

    async def get(self, model: type, identity: object) -> object | None:
        return self.rows.get((model, identity))


def _recovery_reader(project_id) -> Actor:
    return Actor(
        "reader",
        "human",
        "recovery_operator",
        frozenset({"recovery.read"}),
        scopes=frozenset({f"project:{project_id}"}),
    )


def _wrong_recovery_reader() -> Actor:
    return _recovery_reader(uuid4())


def _service_recovery_reader(project_id) -> Actor:
    return Actor(
        "reader-service",
        "service",
        "recovery_operator",
        frozenset({"recovery.read"}),
        scopes=frozenset({f"project:{project_id}"}),
    )


def test_recovery_action_requires_human_global_capability() -> None:
    with pytest.raises(HTTPException, match="Recovery authority"):
        _require_recovery_action(Actor("operator", "human", "incident_reporter"), "incident.create")
    with pytest.raises(HTTPException, match="Recovery authority"):
        _require_recovery_action(
            Actor(
                "operator",
                "human",
                "incident_reporter",
                frozenset({"recovery.incident.create"}),
                scopes=frozenset({"project:wrong"}),
            ),
            "incident.create",
        )
    with pytest.raises(HTTPException, match="Human recovery authority"):
        _require_recovery_action(
            Actor(
                "service",
                "service",
                "incident_reporter",
                frozenset({"recovery.incident.create"}),
                scopes=frozenset({"global"}),
            ),
            "incident.create",
        )
    _require_recovery_action(
        Actor(
            "operator",
            "human",
            "incident_reporter",
            frozenset({"recovery.incident.create"}),
            scopes=frozenset({"global"}),
        ),
        "incident.create",
    )


def _incident(project_id) -> RecoveryIncidentModel:
    return RecoveryIncidentModel(
        id=uuid4(),
        integration_attempt_id=uuid4(),
        rollback_record_id=uuid4(),
        project_id=project_id,
        reported_by="human:operator",
        severity="high",
        summary="Regression observed",
        details="Requests fail after integration.",
        affected_environment="production",
        detected_at=datetime.now(UTC),
        external_reference=None,
        created_at=datetime.now(UTC),
    )


def _assessment(incident: RecoveryIncidentModel) -> RecoveryAssessmentModel:
    return RecoveryAssessmentModel(
        id=uuid4(),
        incident_id=incident.id,
        rollback_record_id=incident.rollback_record_id,
        status="completed",
        recommended_strategy="revert_commit",
        risk_level="medium",
        expected_remote_head_sha="a" * 40,
        integration_commit_is_ancestor=True,
        direct_revert_possible=True,
        database_coordination_required=False,
        external_coordination_required=False,
        required_test_commands=[],
        findings=[],
        assessment_policy_version="recovery-assessment-v1",
        assessment_binding_sha256="b" * 64,
        assessed_by="human:operator",
        assessed_at=datetime.now(UTC),
    )


def _attempt(project_id, assessment: RecoveryAssessmentModel) -> RecoveryAttemptModel:
    return RecoveryAttemptModel(
        id=uuid4(),
        rollback_approval_id=uuid4(),
        recovery_assessment_id=assessment.id,
        rollback_record_id=assessment.rollback_record_id,
        project_id=project_id,
        target_branch="main",
        expected_remote_head_sha="a" * 40,
        integration_commit_sha="c" * 40,
        recovery_strategy="revert_commit",
        status="queued",
        correlation_id=uuid4(),
        failure_class=None,
        failure_code=None,
        failure_message=None,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_recovery_read_routes_reject_wrong_project_scope() -> None:
    project_id = uuid4()
    incident = _incident(project_id)
    assessment = _assessment(incident)
    attempt = _attempt(project_id, assessment)
    session = RecoveryReadSession(
        {
            (RecoveryIncidentModel, incident.id): incident,
            (RecoveryAssessmentModel, assessment.id): assessment,
            (RecoveryAttemptModel, attempt.id): attempt,
        }
    )
    denied = _wrong_recovery_reader()

    for route, identity in (
        (get_incident, incident.id),
        (get_assessment, assessment.id),
        (get_attempt, attempt.id),
    ):
        with pytest.raises(HTTPException) as exc:
            await route(identity, session, denied)  # type: ignore[arg-type, misc]
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_recovery_read_routes_reject_non_human_actor() -> None:
    project_id = uuid4()
    incident = _incident(project_id)
    assessment = _assessment(incident)
    attempt = _attempt(project_id, assessment)
    session = RecoveryReadSession(
        {
            (RecoveryIncidentModel, incident.id): incident,
            (RecoveryAssessmentModel, assessment.id): assessment,
            (RecoveryAttemptModel, attempt.id): attempt,
        }
    )
    denied = _service_recovery_reader(project_id)

    for route, identity in (
        (get_incident, incident.id),
        (get_assessment, assessment.id),
        (get_attempt, attempt.id),
    ):
        with pytest.raises(HTTPException) as exc:
            await route(identity, session, denied)  # type: ignore[arg-type, misc]
        assert exc.value.status_code == 403
        assert exc.value.detail == "Human recovery authority is required"


@pytest.mark.asyncio
async def test_recovery_read_routes_accept_project_scope() -> None:
    project_id = uuid4()
    incident = _incident(project_id)
    assessment = _assessment(incident)
    attempt = _attempt(project_id, assessment)
    session = RecoveryReadSession(
        {
            (RecoveryIncidentModel, incident.id): incident,
            (RecoveryAssessmentModel, assessment.id): assessment,
            (RecoveryAttemptModel, attempt.id): attempt,
        }
    )
    actor = _recovery_reader(project_id)

    assert (await get_incident(incident.id, session, actor)).id == incident.id  # type: ignore[arg-type]
    assert (await get_assessment(assessment.id, session, actor)).id == assessment.id  # type: ignore[arg-type]
    assert (await get_attempt(attempt.id, session, actor)).id == attempt.id  # type: ignore[arg-type]
