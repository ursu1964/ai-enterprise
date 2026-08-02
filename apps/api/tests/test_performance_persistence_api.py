from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException

from ai_enterprise.api.dependencies import Actor
from ai_enterprise.api.performance_schemas import EvidenceCollectRequest, MetricDeriveRequest
from ai_enterprise.api.routes.performance import _require_human, _require_org, router
from ai_enterprise.application.performance_integration_service import (
    COMPLETION_EVENTS,
    PerformanceGovernanceError,
    PerformanceIntegrationService,
)
from ai_enterprise.infrastructure.database.models import AuditEventModel
from ai_enterprise.infrastructure.performance.models import (
    AssignmentQualityModel,
    CapabilityCertificationModel,
    CapabilityRecommendationModel,
    CertificationDecisionModel,
    LearningProposalModel,
    PerformanceEvidenceModel,
    PerformanceMetricModel,
    PerformanceTrendModel,
)


class Scalars:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    def all(self) -> list[Any]:
        return self.rows


class Session:
    def __init__(self, audit: AuditEventModel) -> None:
        self.audit = audit
        self.added: list[Any] = []
        self.scalar_results: list[Any] = []
        self.scalars_results: list[list[Any]] = []
        self.commits = 0

    async def get(self, model: type, identity: uuid.UUID) -> Any:
        if model is AuditEventModel and identity == self.audit.id:
            return self.audit
        return None

    async def scalar(self, statement: object) -> Any:
        return self.scalar_results.pop(0) if self.scalar_results else None

    async def scalars(self, statement: object) -> Scalars:
        return Scalars(self.scalars_results.pop(0))

    def add(self, row: Any) -> None:
        self.added.append(row)

    async def commit(self) -> None:
        self.commits += 1


def audit(event_type: str = "ExecutionCompleted") -> AuditEventModel:
    return AuditEventModel(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        event_type=event_type,
        actor_type="service",
        actor_id="execution-worker",
        payload={"status": "completed"},
        created_at=datetime.now(UTC),
    )


def test_schema_is_append_only_lineage_complete_and_api_surface_is_audited() -> None:
    assert set(COMPLETION_EVENTS) == {
        "requirements",
        "architecture",
        "planning",
        "implementation",
        "review",
        "integration",
        "recovery",
    }
    assert PerformanceEvidenceModel.__table__.c.evidence_hash.unique
    assert PerformanceEvidenceModel.__table__.c.source_audit_event_id.foreign_keys
    assert CapabilityRecommendationModel.__table__.c.recommendation_hash.unique
    assert CapabilityCertificationModel.__table__.c.decision_id.foreign_keys
    for model in (
        PerformanceMetricModel,
        AssignmentQualityModel,
        PerformanceTrendModel,
        CertificationDecisionModel,
        LearningProposalModel,
    ):
        assert len(model.__table__.columns) >= 8
    paths = {f"/api/v1{route.path}" for route in router.routes}
    assert {
        "/api/v1/performance/evidence",
        "/api/v1/performance/metrics",
        "/api/v1/performance/agents",
        "/api/v1/performance/crews",
        "/api/v1/performance/assignments",
        "/api/v1/performance/trends",
        "/api/v1/performance/capabilities",
        "/api/v1/performance/certifications",
        "/api/v1/performance/reports",
        "/api/v1/performance/learning-proposals",
    } <= paths
    migration = (
        Path(__file__).parents[3]
        / "migrations/versions/c24e89f7a613_add_performance_evidence_governance.py"
    ).read_text()
    assert 'down_revision: str | None = "b37e9a81cd44"' in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    hardening = (
        Path(__file__).parents[3]
        / "migrations/versions/c25f91a8b724_harden_performance_governance_records.py"
    ).read_text()
    assert 'down_revision: str | None = "c24e89f7a613"' in hardening
    assert "capability recommendation evidence is immutable" in hardening
    assert "learning proposal evidence is immutable" in hardening
    assert hardening.count("DROP TRIGGER") == 2
    assert hardening.count("DROP FUNCTION") == 2


@pytest.mark.asyncio
async def test_completed_workflow_evidence_is_immutable_and_prompt_version_bound() -> None:
    source = audit()
    session = Session(source)
    service = PerformanceIntegrationService(session)  # type: ignore[arg-type]
    organization_id, workflow_id = uuid.uuid4(), uuid.uuid4()

    evidence = await service.collect_evidence(
        organization_id=organization_id,
        project_id=source.project_id,
        workflow_type="implementation",
        workflow_id=workflow_id,
        evidence_type="execution-outcome",
        evidence_document={
            "duration_seconds": 83,
            "tests_passed": 53,
            "tests_failed": 0,
            "accepted": True,
            "retry_count": 0,
            "rollback": False,
        },
        source_audit_event_id=source.id,
        observed_at=datetime.now(UTC),
        prompt_version="implementation-v7",
    )

    assert evidence.evidence_document["facts"]["tests_passed"] == 53
    assert evidence.prompt_version == "implementation-v7"
    assert len(evidence.evidence_hash) == 64
    assert any(
        isinstance(row, AuditEventModel) and row.event_type == "PerformanceEvidenceCollected"
        for row in session.added
    )


@pytest.mark.asyncio
async def test_evidence_rejects_incomplete_workflow_and_model_opinion() -> None:
    source = audit("ExecutionStarted")
    session = Session(source)
    service = PerformanceIntegrationService(session)  # type: ignore[arg-type]
    values = dict(
        organization_id=uuid.uuid4(),
        project_id=source.project_id,
        workflow_type="implementation",
        workflow_id=uuid.uuid4(),
        evidence_type="execution-outcome",
        evidence_document={"model_confidence": 0.99},
        source_audit_event_id=source.id,
        observed_at=datetime.now(UTC),
    )
    with pytest.raises(PerformanceGovernanceError, match="WORKFLOW-NOT-COMPLETED"):
        await service.collect_evidence(**values)
    source.event_type = "ExecutionCompleted"
    with pytest.raises(PerformanceGovernanceError, match="NON-OBSERVABLE-EVIDENCE"):
        await service.collect_evidence(**values)


@pytest.mark.asyncio
async def test_evidence_rejects_cross_project_binding_and_oversized_payload() -> None:
    source = audit()
    session = Session(source)
    service = PerformanceIntegrationService(session)  # type: ignore[arg-type]
    values = dict(
        organization_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        workflow_type="implementation",
        workflow_id=uuid.uuid4(),
        evidence_type="execution-outcome",
        evidence_document={"accepted": True},
        source_audit_event_id=source.id,
        observed_at=datetime.now(UTC),
    )
    with pytest.raises(PerformanceGovernanceError, match="AUDIT-PROJECT-MISMATCH"):
        await service.collect_evidence(**values)
    values["project_id"] = source.project_id
    values["evidence_document"] = {"log": "x" * 270_000}
    with pytest.raises(PerformanceGovernanceError, match="EVIDENCE-DOCUMENT-TOO-LARGE"):
        await service.collect_evidence(**values)


@pytest.mark.asyncio
async def test_metric_recommendation_and_human_certificate_preserve_evidence_lineage() -> None:
    session = Session(audit())
    service = PerformanceIntegrationService(session)  # type: ignore[arg-type]
    organization_id, agent_id = uuid.uuid4(), uuid.uuid4()
    evidence = PerformanceEvidenceModel(
        id=uuid.uuid4(),
        organization_id=organization_id,
        project_id=None,
        workflow_type="review",
        workflow_id=uuid.uuid4(),
        evidence_type="review-outcome",
        evidence_document={"accepted": True},
        evidence_hash="a" * 64,
        source_audit_event_id=uuid.uuid4(),
        observed_at=datetime.now(UTC),
    )
    session.scalars_results = [[evidence]]
    metric = await service.derive_metric(
        organization_id=organization_id,
        scope_type="agent",
        scope_id=agent_id,
        metric_key="acceptance_rate",
        numerator=1,
        denominator=1,
        evidence_ids=[evidence.id],
        window_days=90,
        policy_version="performance-v1",
        actor_id="metrics-engine",
        now=datetime.now(UTC),
    )
    assert metric.evidence_ids == [str(evidence.id)]
    assert metric.metric_value == 1

    session.scalars_results = [[evidence]]
    recommendation = await service.create_recommendation(
        organization_id=organization_id,
        agent_profile_id=agent_id,
        capability_key="review-patch",
        recommended_level="certified",
        evidence_ids=[evidence.id],
        policy_version="certification-v1",
        assessment={"metric_id": str(metric.id), "eligible": True},
        actor_id="certification-engine",
        now=datetime.now(UTC),
    )
    assert recommendation.status == "pending_human_review"
    assert not any(isinstance(row, CapabilityCertificationModel) for row in session.added)

    session.scalar_results = [None]
    decision, certificate = await service.decide_certification(
        recommendation,
        recommendation_hash=recommendation.recommendation_hash,
        decision="approve",
        decided_by="human-board-member",
        board_role="certification-board",
        rationale="Evidence meets policy thresholds",
        validity_days=365,
        now=datetime.now(UTC),
    )
    assert decision.recommendation_hash == recommendation.recommendation_hash
    assert certificate is not None
    assert certificate.evidence_set_hash == recommendation.evidence_set_hash
    assert certificate.expires_at > certificate.granted_at


def test_agents_cannot_certify_or_approve_learning() -> None:
    agent = Actor("agent-1", "agent", "certification-board")
    with pytest.raises(HTTPException, match="human governance"):
        _require_human(agent, {"certification-board"})
    service = Actor("service-1", "service", "certification-board")
    with pytest.raises(HTTPException, match="human governance"):
        _require_human(service, {"certification-board"})


def test_cross_organization_access_requires_scoped_capability() -> None:
    organization_id = uuid.uuid4()
    auditor = Actor("auditor", "human", "performance-auditor")
    with pytest.raises(HTTPException, match="Organization-scoped"):
        _require_org(auditor, organization_id, "read")
    admin_without_scope = Actor("admin", "human", "platform-admin")
    with pytest.raises(HTTPException, match="Organization-scoped"):
        _require_org(admin_without_scope, organization_id, "read")
    scoped = Actor(
        "auditor",
        "human",
        "performance-auditor",
        frozenset({"performance.read"}),
        scopes=frozenset({f"organization:{organization_id}"}),
    )
    _require_org(scoped, organization_id, "read")
    global_scoped = Actor(
        "auditor",
        "human",
        "performance-auditor",
        frozenset({"performance.read"}),
        scopes=frozenset({"global"}),
    )
    _require_org(global_scoped, organization_id, "read")
    with pytest.raises(HTTPException, match="Organization-scoped"):
        _require_org(scoped, uuid.uuid4(), "read")


def test_request_bounds_reject_resource_exhaustion_inputs() -> None:
    common = {
        "organization_id": uuid.uuid4(),
        "project_id": None,
        "workflow_type": "x" * 61,
        "workflow_id": uuid.uuid4(),
        "evidence_type": "outcome",
        "evidence_document": {},
        "source_audit_event_id": uuid.uuid4(),
        "observed_at": datetime.now(UTC),
    }
    with pytest.raises(ValueError):
        EvidenceCollectRequest(**common)
    with pytest.raises(ValueError):
        MetricDeriveRequest(
            organization_id=uuid.uuid4(),
            scope_type="agent",
            scope_id=uuid.uuid4(),
            metric_key="acceptance",
            numerator=1,
            denominator=1,
            evidence_ids=[uuid.uuid4()] * 1001,
            window_days=90,
            policy_version="v1",
        )


@pytest.mark.asyncio
async def test_metric_replay_is_idempotent_and_does_not_duplicate_audit() -> None:
    session = Session(audit())
    service = PerformanceIntegrationService(session)  # type: ignore[arg-type]
    organization_id, evidence_id = uuid.uuid4(), uuid.uuid4()
    evidence = PerformanceEvidenceModel(
        id=evidence_id,
        organization_id=organization_id,
        project_id=None,
        workflow_type="review",
        workflow_id=uuid.uuid4(),
        evidence_type="outcome",
        evidence_document={"accepted": True},
        evidence_hash="c" * 64,
        source_audit_event_id=uuid.uuid4(),
        observed_at=datetime.now(UTC),
    )
    session.scalars_results = [[evidence]]
    values = dict(
        organization_id=organization_id,
        scope_type="agent",
        scope_id=uuid.uuid4(),
        metric_key="acceptance_rate",
        numerator=1,
        denominator=1,
        evidence_ids=[evidence_id],
        window_days=90,
        policy_version="v1",
        actor_id="engine",
        now=datetime.now(UTC),
    )
    first = await service.derive_metric(**values)
    added_after_first = len(session.added)
    session.scalars_results = [[evidence]]
    session.scalar_results = [first]
    replay = await service.derive_metric(**values)
    assert replay is first
    assert len(session.added) == added_after_first


@pytest.mark.asyncio
async def test_learning_approval_never_changes_prompt_or_authority() -> None:
    session = Session(audit())
    service = PerformanceIntegrationService(session)  # type: ignore[arg-type]
    organization_id = uuid.uuid4()
    evidence = PerformanceEvidenceModel(
        id=uuid.uuid4(),
        organization_id=organization_id,
        project_id=None,
        workflow_type="review",
        workflow_id=uuid.uuid4(),
        evidence_type="review-miss",
        evidence_document={"missed_dependency_violation": True},
        evidence_hash="b" * 64,
        source_audit_event_id=uuid.uuid4(),
        observed_at=datetime.now(UTC),
    )
    session.scalars_results = [[evidence]]
    proposal = await service.create_learning_proposal(
        organization_id=organization_id,
        project_id=None,
        proposal_type="prompt-change-candidate",
        observation="Dependency violations repeatedly escaped review",
        recommendation="Add deterministic dependency graph verification",
        target_reference="review-prompt-v7",
        evidence_ids=[evidence.id],
        proposed_by="trend-engine",
        now=datetime.now(UTC),
    )
    reviewed = await service.review_learning_proposal(
        proposal,
        decision="approve",
        reviewer="human-governor",
        rationale="Open a separate prompt change workflow",
        now=datetime.now(UTC),
    )
    assert reviewed.status == "approved_for_separate_change_workflow"
    event = next(
        row
        for row in session.added
        if isinstance(row, AuditEventModel) and row.event_type == "OrganizationalLearningReviewed"
    )
    assert event.payload["prompt_changed"] is False
    assert event.payload["authority_changed"] is False
