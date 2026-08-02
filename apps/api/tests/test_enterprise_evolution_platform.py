from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException

from ai_enterprise.api.dependencies import Actor
from ai_enterprise.api.routes.enterprise_evolution import _authority, _human, router
from ai_enterprise.application.enterprise_evolution_service import (
    ARTIFACT_TYPES,
    EnterpriseEvolutionError,
    EnterpriseEvolutionService,
    EnterpriseEvolutionWorker,
)
from ai_enterprise.infrastructure.enterprise_evolution.models import (
    EnterpriseEvolutionArtifactModel,
    EnterpriseEvolutionDecisionModel,
    EnterpriseImprovementModel,
    EnterpriseImprovementTransitionModel,
)
from ai_enterprise.infrastructure.performance.models import PerformanceEvidenceModel


class Rows:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    def all(self) -> list[Any]:
        return self.rows


class Session:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.gets: dict[tuple[type, uuid.UUID | None], Any] = {}
        self.scalar_values: list[Any] = []
        self.scalars_values: list[list[Any]] = []

    def add(self, row: Any) -> None:
        self.added.append(row)

    async def get(self, model: type, identity: uuid.UUID | None) -> Any:
        return self.gets.get((model, identity))

    async def scalar(self, statement: object) -> Any:
        return self.scalar_values.pop(0) if self.scalar_values else None

    async def scalars(self, statement: object) -> Rows:
        return Rows(self.scalars_values.pop(0) if self.scalars_values else [])

    async def commit(self) -> None:
        return None


def test_enterprise_evolution_authority_requires_scoped_capability() -> None:
    organization_id = uuid.uuid4()
    with pytest.raises(HTTPException, match="evolution authority"):
        _authority(Actor("admin", "human", "platform-admin"), organization_id, "read")
    scoped = Actor(
        "governor",
        "human",
        "governor",
        frozenset({"enterprise_evolution.read"}),
        scopes=frozenset({f"organization:{organization_id}"}),
    )
    _authority(scoped, organization_id, "read")
    global_scoped = Actor(
        "governor",
        "human",
        "governor",
        frozenset({"enterprise_evolution.read"}),
        scopes=frozenset({"global"}),
    )
    _authority(global_scoped, organization_id, "read")
    with pytest.raises(HTTPException, match="evolution authority"):
        _authority(scoped, uuid.uuid4(), "read")

    async def commit(self) -> None:
        return None


def performance_evidence(organization_id: uuid.UUID) -> PerformanceEvidenceModel:
    return PerformanceEvidenceModel(
        id=uuid.uuid4(),
        organization_id=organization_id,
        project_id=None,
        workflow_type="integration",
        workflow_id=uuid.uuid4(),
        evidence_type="integration-outcome",
        evidence_document={"success": True},
        evidence_hash="a" * 64,
        source_audit_event_id=uuid.uuid4(),
        observed_at=datetime.now(UTC),
    )


def improvement(
    organization_id: uuid.UUID, creator: str = "learning-engine"
) -> EnterpriseImprovementModel:
    return EnterpriseImprovementModel(
        id=uuid.uuid4(),
        organization_id=organization_id,
        improvement_key=f"security.auth.{uuid.uuid4().hex}",
        category="security",
        origin="benchmark",
        title="Improve auth specifications",
        expected_benefit="Reduce review iterations",
        risk_document={"level": "medium"},
        dependencies=[],
        evidence_ids=[],
        evidence_set_hash="b" * 64,
        proposal_document={},
        proposal_hash="c" * 64,
        proposed_by=creator,
        proposed_at=datetime.now(UTC),
    )


def test_m1_m16_registry_api_and_append_only_schema_are_complete() -> None:
    assert ARTIFACT_TYPES == {
        "learning_hypothesis",
        "pattern",
        "anti_pattern",
        "recommendation",
        "simulation",
        "experiment",
        "generator_evolution",
        "policy_evolution",
        "ai_workforce_evolution",
        "capability_evolution",
        "maturity_assessment",
        "benchmark",
        "roadmap",
        "refactoring_plan",
        "self_reflection",
    }
    paths = {f"/api/v1{route.path}" for route in router.routes}
    for path in (
        "learning",
        "patterns",
        "anti-patterns",
        "recommendations",
        "simulations",
        "experiments",
        "generator-evolution",
        "policy-evolution",
        "workforce-evolution",
        "capability-evolution",
        "maturity",
        "benchmarks",
        "roadmaps",
        "refactoring",
        "self-reflections",
    ):
        assert f"/api/v1/enterprise-evolution/{path}" in paths
    migration = (
        Path(__file__).parents[3]
        / "migrations/versions/c42b87eaf956_add_governed_enterprise_evolution.py"
    ).read_text()
    assert 'down_revision: str | None = "c31a76d9e845"' in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "DROP TRIGGER" in migration and "DROP FUNCTION" in migration
    assert EnterpriseImprovementModel.__table__.c.proposal_hash.unique
    assert EnterpriseEvolutionArtifactModel.__table__.c.artifact_hash.unique
    pattern_route = next(route for route in router.routes if route.path.endswith("/patterns"))
    assert "_artifact_type" not in inspect.signature(pattern_route.endpoint).parameters
    hardening = (
        Path(__file__).parents[3]
        / "migrations/versions/c43c98fb0a67_harden_enterprise_evolution_constraints.py"
    ).read_text()
    assert 'down_revision: str | None = "c42b87eaf956"' in hardening
    assert hardening.count("create_check_constraint") == 5
    assert hardening.count("drop_constraint") == 5


@pytest.mark.asyncio
async def test_improvement_and_learning_artifact_preserve_verified_evidence_lineage() -> None:
    organization_id = uuid.uuid4()
    evidence = performance_evidence(organization_id)
    session = Session()
    session.gets[(PerformanceEvidenceModel, evidence.id)] = evidence
    service = EnterpriseEvolutionService(session)  # type: ignore[arg-type]
    reference = [{"type": "performance", "id": str(evidence.id), "hash": evidence.evidence_hash}]
    row = await service.propose(
        organization_id=organization_id,
        improvement_key="security.auth.specification",
        category="security",
        origin="performance-trend",
        title="Improve auth specification",
        expected_benefit="Reduce review iterations",
        risk_document={"level": "medium"},
        dependencies=[],
        evidence=reference,
        proposed_by="learning-engine",
    )
    assert len(row.proposal_hash) == 64
    initial = next(
        item for item in session.added if isinstance(item, EnterpriseImprovementTransitionModel)
    )
    assert initial.to_state == "proposed"
    session.gets[(EnterpriseImprovementModel, row.id)] = row
    artifact = await EnterpriseEvolutionWorker(  # type: ignore[arg-type]
        session, "learning-worker"
    ).record_analysis(
        organization_id=organization_id,
        improvement_id=row.id,
        artifact_type="learning_hypothesis",
        artifact_key="learning.auth-review",
        version="1.0.0",
        document={"hypothesis": "specification ambiguity"},
        evidence=reference,
        created_by="spoofed-creator",
    )
    assert artifact.evidence_set_hash == row.evidence_set_hash
    assert artifact.created_by == "learning-worker"


@pytest.mark.asyncio
async def test_cross_organization_evidence_and_self_approval_fail_closed() -> None:
    first, second = uuid.uuid4(), uuid.uuid4()
    evidence = performance_evidence(first)
    session = Session()
    session.gets[(PerformanceEvidenceModel, evidence.id)] = evidence
    service = EnterpriseEvolutionService(session)  # type: ignore[arg-type]
    with pytest.raises(EnterpriseEvolutionError, match="HASH-OR-SCOPE-MISMATCH"):
        await service.propose(
            organization_id=second,
            improvement_key="security.auth.cross-scope",
            category="security",
            origin="test",
            title="invalid",
            expected_benefit="none",
            risk_document={},
            dependencies=[],
            evidence=[
                {"type": "performance", "id": str(evidence.id), "hash": evidence.evidence_hash}
            ],
            proposed_by="agent",
        )
    target = improvement(first, creator="same-human")
    session.gets[(EnterpriseImprovementModel, target.id)] = target
    with pytest.raises(EnterpriseEvolutionError, match="INDEPENDENT-DECISION"):
        await service.decide(
            organization_id=first,
            target_type="improvement",
            target_id=target.id,
            target_hash=target.proposal_hash,
            decision="approve",
            decided_by="same-human",
            board_role="evolution-board",
            rationale="self approval",
        )
    with pytest.raises(HTTPException, match="human governance"):
        _human(Actor("agent", "agent", "evolution-board"))


@pytest.mark.asyncio
async def test_dependency_lineage_and_artifact_category_confusion_fail_closed() -> None:
    organization_id = uuid.uuid4()
    session = Session()
    service = EnterpriseEvolutionService(session)  # type: ignore[arg-type]
    session.scalars_values = [[]]
    with pytest.raises(EnterpriseEvolutionError, match="DEPENDENCY-SCOPE-OR-LINEAGE"):
        await service.propose(
            organization_id=organization_id,
            improvement_key="security.auth.dependent",
            category="security",
            origin="roadmap",
            title="Dependent improvement",
            expected_benefit="safer auth",
            risk_document={},
            dependencies=["foreign.item"],
            evidence=[{"type": "performance", "id": str(uuid.uuid4()), "hash": "a" * 64}],
            proposed_by="planner",
        )
    target = improvement(organization_id)
    target.category = "architecture"
    session.gets[(EnterpriseImprovementModel, target.id)] = target
    with pytest.raises(EnterpriseEvolutionError, match="ARTIFACT-CATEGORY-MISMATCH"):
        await service.record_artifact(
            organization_id=organization_id,
            improvement_id=target.id,
            artifact_type="benchmark",
            artifact_key="benchmark.architecture",
            version="1.0.0",
            document={},
            evidence=[],
            created_by="worker",
        )


@pytest.mark.asyncio
async def test_lifecycle_is_sequential_and_approval_is_hash_bound() -> None:
    organization_id = uuid.uuid4()
    target = improvement(organization_id)
    session = Session()
    service = EnterpriseEvolutionService(session)  # type: ignore[arg-type]
    current = EnterpriseImprovementTransitionModel(
        id=uuid.uuid4(),
        improvement_id=target.id,
        sequence=3,
        from_state="analyzed",
        to_state="simulated",
        evidence_artifact_ids=[],
        evidence_set_hash="d" * 64,
        decision_id=None,
        transitioned_by="worker",
        transitioned_at=datetime.now(UTC),
    )
    session.scalar_values = [current]
    with pytest.raises(EnterpriseEvolutionError, match="NON-SEQUENTIAL"):
        await service.transition(
            target,
            to_state="approved",
            evidence_artifact_ids=[],
            transitioned_by="human",
            decision_id=None,
        )
    reviewed = EnterpriseImprovementTransitionModel(
        id=uuid.uuid4(),
        improvement_id=target.id,
        sequence=4,
        from_state="simulated",
        to_state="reviewed",
        evidence_artifact_ids=[],
        evidence_set_hash="e" * 64,
        decision_id=None,
        transitioned_by="reviewer",
        transitioned_at=datetime.now(UTC),
    )
    wrong = EnterpriseEvolutionDecisionModel(
        id=uuid.uuid4(),
        organization_id=organization_id,
        target_type="improvement",
        target_id=target.id,
        target_hash="0" * 64,
        decision="approve",
        decided_by="board",
        board_role="evolution-board",
        rationale="wrong hash",
        expires_at=None,
        decided_at=datetime.now(UTC),
    )
    review_evidence = EnterpriseEvolutionArtifactModel(
        id=uuid.uuid4(),
        organization_id=organization_id,
        improvement_id=target.id,
        artifact_type="recommendation",
        artifact_key="recommend.auth",
        version="1.0.0",
        artifact_document={},
        artifact_hash="9" * 64,
        evidence_ids=[],
        evidence_set_hash="8" * 64,
        parent_artifact_id=None,
        created_by="reviewer",
        created_at=datetime.now(UTC),
    )
    session.scalar_values = [reviewed]
    session.scalars_values = [[review_evidence]]
    session.gets[(EnterpriseEvolutionDecisionModel, wrong.id)] = wrong
    with pytest.raises(EnterpriseEvolutionError, match="HUMAN-APPROVAL-REQUIRED"):
        await service.transition(
            target,
            to_state="approved",
            evidence_artifact_ids=[review_evidence.id],
            transitioned_by="human",
            decision_id=wrong.id,
        )


@pytest.mark.asyncio
async def test_required_simulation_refactor_benchmark_and_reflection_cannot_be_bypassed() -> None:
    organization_id = uuid.uuid4()
    target = improvement(organization_id)
    session = Session()
    service = EnterpriseEvolutionService(session)  # type: ignore[arg-type]
    analyzed = EnterpriseImprovementTransitionModel(
        id=uuid.uuid4(),
        improvement_id=target.id,
        sequence=2,
        from_state="proposed",
        to_state="analyzed",
        evidence_artifact_ids=[],
        evidence_set_hash="f" * 64,
        decision_id=None,
        transitioned_by="worker",
        transitioned_at=datetime.now(UTC),
    )
    recommendation = EnterpriseEvolutionArtifactModel(
        id=uuid.uuid4(),
        organization_id=organization_id,
        improvement_id=target.id,
        artifact_type="recommendation",
        artifact_key="recommend.auth",
        version="1.0.0",
        artifact_document={},
        artifact_hash="1" * 64,
        evidence_ids=[],
        evidence_set_hash="2" * 64,
        parent_artifact_id=None,
        created_by="worker",
        created_at=datetime.now(UTC),
    )
    session.scalar_values = [analyzed]
    session.scalars_values = [[recommendation]]
    with pytest.raises(EnterpriseEvolutionError, match="SIMULATION-REQUIRED"):
        await service.transition(
            target,
            to_state="simulated",
            evidence_artifact_ids=[recommendation.id],
            transitioned_by="worker",
        )
