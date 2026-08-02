from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException

from ai_enterprise.api.dependencies import Actor
from ai_enterprise.api.routes.specifications import _authority, router
from ai_enterprise.application.specification_platform_service import (
    SpecificationGenerationWorker,
    SpecificationPlatformError,
    SpecificationPlatformService,
)
from ai_enterprise.infrastructure.specification.models import (
    DriftDecisionModel,
    DriftFindingModel,
    EngineeringEvidenceEdgeModel,
    EngineeringEvidenceNodeModel,
    EngineeringSpecificationModel,
    GeneratedEngineeringArtifactModel,
    SpecificationValidationRunModel,
)


class Rows:
    def __init__(self, values: list[Any]) -> None:
        self.values = values

    def all(self) -> list[Any]:
        return self.values


class Session:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.scalar_values: list[Any] = []
        self.scalars_values: list[list[Any]] = []
        self.get_values: dict[tuple[type, uuid.UUID], Any] = {}
        self.commits = 0

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.commits += 1

    async def flush(self) -> None:
        return None

    async def scalar(self, statement: object) -> Any:
        return self.scalar_values.pop(0) if self.scalar_values else None

    async def scalars(self, statement: object) -> Rows:
        return Rows(self.scalars_values.pop(0) if self.scalars_values else [])

    async def get(self, model: type, identity: uuid.UUID) -> Any:
        return self.get_values.get((model, identity))


def specification(
    organization_id: uuid.UUID | None = None, project_id: uuid.UUID | None = None
) -> EngineeringSpecificationModel:
    return EngineeringSpecificationModel(
        id=uuid.uuid4(),
        organization_id=organization_id or uuid.uuid4(),
        project_id=project_id or uuid.uuid4(),
        specification_key="service.orders",
        specification_type="service",
        version="1.0.0",
        specification_document={"name": "Orders"},
        specification_hash="a" * 64,
        requirements_hash="b" * 64,
        architecture_hash="c" * 64,
        work_package_hash="d" * 64,
        parent_specification_id=None,
        created_by="engineer",
        created_at=datetime.now(UTC),
    )


def test_specification_authority_requires_scoped_capability() -> None:
    organization_id = uuid.uuid4()
    with pytest.raises(HTTPException, match="specification authority"):
        _authority(Actor("admin", "human", "platform-admin"), organization_id, "read")
    scoped = Actor(
        "engineer",
        "human",
        "engineer",
        frozenset({"specification.read"}),
        scopes=frozenset({f"organization:{organization_id}"}),
    )
    _authority(scoped, organization_id, "read")
    global_scoped = Actor(
        "engineer",
        "human",
        "engineer",
        frozenset({"specification.read"}),
        scopes=frozenset({"global"}),
    )
    _authority(global_scoped, organization_id, "read")
    with pytest.raises(HTTPException, match="specification authority"):
        _authority(scoped, uuid.uuid4(), "read")


def test_schema_api_migration_and_append_only_evidence_graph_are_complete() -> None:
    assert EngineeringSpecificationModel.__table__.c.specification_hash.unique
    assert GeneratedEngineeringArtifactModel.__table__.c.provenance_hash.unique
    assert SpecificationValidationRunModel.__table__.c.evidence_hash.unique
    assert EngineeringEvidenceNodeModel.__table__.c.node_hash.unique
    assert EngineeringEvidenceEdgeModel.__table__.c.edge_hash.unique
    assert DriftFindingModel.__table__.c.finding_hash.unique
    paths = {f"/api/v1{route.path}" for route in router.routes}
    assert {
        "/api/v1/specifications",
        "/api/v1/specifications/{specification_id}/decision",
        "/api/v1/specifications/{specification_id}/validations",
        "/api/v1/specifications/{specification_id}/generation-runs",
        "/api/v1/specifications/evidence/nodes",
        "/api/v1/specifications/evidence/edges",
        "/api/v1/specifications/evidence/graph",
        "/api/v1/specifications/{specification_id}/drift-runs",
        "/api/v1/specifications/drift-findings/{finding_id}/decision",
    } <= paths
    migration = (
        Path(__file__).parents[3]
        / "migrations/versions/c31a76d9e845_add_specification_engineering_platform.py"
    ).read_text()
    assert 'down_revision: str | None = "c25f91a8b724"' in migration
    assert migration.count("BEFORE UPDATE OR DELETE") == 1  # reusable trigger builder
    assert "engineering_drift_findings" in migration
    assert "invalid generation run transition" in migration
    assert "generation runs cannot be deleted" in migration
    assert "DROP FUNCTION guard_specification_generation_run()" in migration
    assert '"engineering_drift_runs"' in migration


@pytest.mark.asyncio
async def test_specification_hash_binds_all_parent_provenance_and_approval_hash() -> None:
    session = Session()
    service = SpecificationPlatformService(session)  # type: ignore[arg-type]
    row = await service.create_specification(
        organization_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        specification_key="service.orders",
        specification_type="service",
        version="1.0.0",
        document={"name": "Orders", "operations": []},
        requirements_hash="b" * 64,
        architecture_hash="c" * 64,
        work_package_hash="d" * 64,
        created_by="human-engineer",
    )
    assert len(row.specification_hash) == 64
    assert row.requirements_hash == "b" * 64
    with pytest.raises(SpecificationPlatformError, match="HASH-MISMATCH"):
        await service.approve(
            row,
            specification_hash="0" * 64,
            decision="approve",
            decided_by="approver",
            rationale="valid",
        )
    with pytest.raises(SpecificationPlatformError, match="INDEPENDENT-APPROVER"):
        await service.approve(
            row,
            specification_hash=row.specification_hash,
            decision="approve",
            decided_by=row.created_by,
            rationale="self approval",
        )
    approval = await service.approve(
        row,
        specification_hash=row.specification_hash,
        decision="approve",
        decided_by="approver",
        rationale="validated intent",
    )
    assert approval.specification_hash == row.specification_hash


@pytest.mark.asyncio
async def test_generation_requires_approval_validation_and_worker_preserves_provenance() -> None:
    session = Session()
    service = SpecificationPlatformService(session)  # type: ignore[arg-type]
    spec = specification()
    session.scalar_values = [None]
    with pytest.raises(SpecificationPlatformError, match="APPROVAL-AND-VALIDATION"):
        await service.request_generation(
            spec, generator_key="openapi", generator_version="1.0.0", parameters={}, actor="agent"
        )
    session.scalar_values = [uuid.uuid4(), uuid.uuid4(), None]
    run = await service.request_generation(
        spec, generator_key="openapi", generator_version="1.0.0", parameters={}, actor="agent"
    )
    session.scalar_values = [run]
    session.get_values[(EngineeringSpecificationModel, spec.id)] = spec

    class Generator:
        def generate(
            self, specification: dict[str, Any], parameters: dict[str, Any]
        ) -> tuple[dict[str, str], ...]:
            return (
                {
                    "artifact_type": "openapi",
                    "repository_path": "generated/openapi.json",
                    "content_hash": "e" * 64,
                },
            )

    completed = await SpecificationGenerationWorker(session).handle(run.id, Generator())  # type: ignore[arg-type]
    artifact = next(
        item for item in session.added if isinstance(item, GeneratedEngineeringArtifactModel)
    )
    assert completed.status == "completed"
    assert completed.output_manifest_hash
    assert artifact.specification_hash == spec.specification_hash
    assert artifact.generator_version == "1.0.0"


@pytest.mark.asyncio
async def test_evidence_graph_rejects_cross_project_edges() -> None:
    session = Session()
    service = SpecificationPlatformService(session)  # type: ignore[arg-type]
    organization_id = uuid.uuid4()
    source = EngineeringEvidenceNodeModel(
        id=uuid.uuid4(),
        organization_id=organization_id,
        project_id=uuid.uuid4(),
        node_type="requirement",
        reference_id=uuid.uuid4(),
        reference_hash="a" * 64,
        classification="internal",
        node_document={},
        node_hash="b" * 64,
        recorded_at=datetime.now(UTC),
    )
    target = EngineeringEvidenceNodeModel(
        id=uuid.uuid4(),
        organization_id=organization_id,
        project_id=uuid.uuid4(),
        node_type="deployment",
        reference_id=uuid.uuid4(),
        reference_hash="c" * 64,
        classification="internal",
        node_document={},
        node_hash="d" * 64,
        recorded_at=datetime.now(UTC),
    )
    with pytest.raises(SpecificationPlatformError, match="CROSS-SCOPE-EDGE"):
        await service.add_evidence_edge(
            source, target, relationship="traces-to", document={}, actor="graph-builder"
        )


@pytest.mark.asyncio
async def test_evidence_graph_rejects_self_edges_and_cycles() -> None:
    session = Session()
    service = SpecificationPlatformService(session)  # type: ignore[arg-type]
    organization_id, project_id = uuid.uuid4(), uuid.uuid4()
    source = EngineeringEvidenceNodeModel(
        id=uuid.uuid4(),
        organization_id=organization_id,
        project_id=project_id,
        node_type="requirement",
        reference_id=uuid.uuid4(),
        reference_hash="a" * 64,
        classification="internal",
        node_document={},
        node_hash="b" * 64,
        recorded_at=datetime.now(UTC),
    )
    target = EngineeringEvidenceNodeModel(
        id=uuid.uuid4(),
        organization_id=organization_id,
        project_id=project_id,
        node_type="deployment",
        reference_id=uuid.uuid4(),
        reference_hash="c" * 64,
        classification="internal",
        node_document={},
        node_hash="d" * 64,
        recorded_at=datetime.now(UTC),
    )
    with pytest.raises(SpecificationPlatformError, match="SELF-EDGE"):
        await service.add_evidence_edge(
            source, source, relationship="traces-to", document={}, actor="builder"
        )
    reverse = EngineeringEvidenceEdgeModel(
        id=uuid.uuid4(),
        source_node_id=target.id,
        target_node_id=source.id,
        relationship="traces-to",
        edge_document={},
        edge_hash="e" * 64,
        recorded_at=datetime.now(UTC),
    )
    session.scalars_values = [[source.id, target.id], [reverse]]
    with pytest.raises(SpecificationPlatformError, match="EVIDENCE-CYCLE"):
        await service.add_evidence_edge(
            source, target, relationship="traces-to", document={}, actor="builder"
        )


@pytest.mark.asyncio
async def test_drift_blocks_promotion_and_exception_is_hash_bound_and_expires() -> None:
    session = Session()
    service = SpecificationPlatformService(session)  # type: ignore[arg-type]
    spec = specification()
    session.scalar_values = [uuid.uuid4(), None]
    run, findings = await service.detect_drift(
        spec,
        repository_commit_hash="1" * 40,
        runtime_deployment_hash="2" * 64,
        detector_version="drift-v1",
        observations=[
            {
                "category": "api",
                "severity": "critical",
                "expected_hash": "3" * 64,
                "actual_hash": "4" * 64,
                "promotion_blocking": True,
                "evidence": {"path": "/orders"},
            }
        ],
        actor="drift-worker",
    )
    assert run.status == "completed"
    assert findings[0].promotion_blocking is True
    session.get_values[(type(run), run.id)] = run
    with pytest.raises(SpecificationPlatformError, match="EXCEPTION-EXPIRY"):
        await service.decide_drift(
            findings[0],
            finding_hash=findings[0].finding_hash,
            decision="approved_exception",
            decided_by="human",
            rationale="temporary",
            expires_at=None,
        )
    with pytest.raises(SpecificationPlatformError, match="EXPIRE-IN-FUTURE"):
        await service.decide_drift(
            findings[0],
            finding_hash=findings[0].finding_hash,
            decision="approved_exception",
            decided_by="human",
            rationale="expired",
            expires_at=datetime(2020, 1, 1, tzinfo=UTC),
        )
    decision = await service.decide_drift(
        findings[0],
        finding_hash=findings[0].finding_hash,
        decision="approved_exception",
        decided_by="human",
        rationale="temporary",
        expires_at=datetime(2027, 1, 1, tzinfo=UTC),
    )
    assert decision.finding_hash == findings[0].finding_hash
    assert decision.expires_at is not None


@pytest.mark.asyncio
async def test_expired_drift_exception_cannot_bypass_promotion_block() -> None:
    session = Session()
    service = SpecificationPlatformService(session)  # type: ignore[arg-type]
    run_id = uuid.uuid4()
    finding = DriftFindingModel(
        id=uuid.uuid4(),
        drift_run_id=run_id,
        category="api",
        severity="high",
        expected_hash="a" * 64,
        actual_hash="b" * 64,
        evidence_document={},
        finding_hash="c" * 64,
        promotion_blocking=True,
        detected_at=datetime.now(UTC),
    )
    expired = DriftDecisionModel(
        id=uuid.uuid4(),
        finding_id=finding.id,
        finding_hash=finding.finding_hash,
        decision="approved_exception",
        decided_by="human",
        rationale="temporary",
        expires_at=datetime(2025, 1, 1, tzinfo=UTC),
        decided_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    session.scalars_values = [[run_id], [finding], [expired]]
    eligible, blockers = await service.promotion_eligibility(
        organization_id=uuid.uuid4(), project_id=uuid.uuid4(), now=datetime(2026, 1, 1, tzinfo=UTC)
    )
    assert eligible is False
    assert blockers == (finding.id,)
