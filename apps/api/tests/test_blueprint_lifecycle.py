import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from ai_enterprise.api.blueprint_schemas import BlueprintCreateRequest, BlueprintTransitionRequest
from ai_enterprise.api.dependencies import Actor
from ai_enterprise.api.routes.blueprints import (
    blueprint_history,
    list_blueprints,
    propose_blueprint,
    transition_blueprint,
)
from ai_enterprise.domain.blueprints import (
    BLUEPRINT_LIFECYCLES,
    BlueprintLifecycleError,
    require_blueprint_transition,
    require_reuse_evidence,
)
from ai_enterprise.infrastructure.database.models import (
    ArtifactModel,
    BlueprintAssetModel,
    BlueprintDecisionModel,
    ProjectModel,
)
from ai_enterprise.main import app


class _Scalars:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class _Session:
    def __init__(self) -> None:
        self.rows: dict[tuple[type[Any], uuid.UUID], Any] = {}
        self.query_rows: list[Any] = []
        self.added: list[Any] = []
        self.statements: list[Any] = []
        self.commit_error: Exception | None = None
        self.rollbacks = 0

    async def get(self, model: type[Any], identity: uuid.UUID, **_: Any) -> Any:
        return self.rows.get((model, identity))

    def add(self, row: Any) -> None:
        self.added.append(row)

    async def commit(self) -> None:
        if self.commit_error is not None:
            raise self.commit_error

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def refresh(self, row: Any) -> None:
        now = datetime.now(UTC)
        if getattr(row, "created_at", None) is None:
            row.created_at = now
        if hasattr(row, "updated_at") and getattr(row, "updated_at", None) is None:
            row.updated_at = now

    async def scalars(self, statement: Any) -> _Scalars:
        self.statements.append(statement)
        return _Scalars(self.query_rows)


def _actor(*capabilities: str, scopes: frozenset[str]) -> Actor:
    return Actor(
        "blueprint-owner",
        "human",
        "architect",
        frozenset(capabilities),
        scopes=scopes,
    )


def _project(project_id: uuid.UUID) -> ProjectModel:
    return ProjectModel(
        id=project_id,
        name="Source",
        description="Source project",
        status="active",
        manifest_hash="a" * 64,
        manifest={},
        repository_path="/tmp/source",
    )


def _blueprint(
    organization_id: uuid.UUID,
    *,
    blueprint_id: uuid.UUID | None = None,
    lifecycle: str = "proposed",
    version: int = 1,
    key: str = "delivery-pattern",
) -> BlueprintAssetModel:
    now = datetime.now(UTC)
    return BlueprintAssetModel(
        id=blueprint_id or uuid.uuid4(),
        organization_id=organization_id,
        blueprint_key=key,
        version=version,
        title="Delivery Pattern",
        kind="workflow_pattern",
        lifecycle=lifecycle,
        source_project_id=uuid.uuid4(),
        source_phase="implementation",
        pattern={"steps": ["verify"]},
        evidence={"source": "audit"},
        economic_proof={"result": "measured"},
        recommended_use="Use for controlled delivery",
        reuse_count=0,
        created_by="owner",
        created_at=now,
        updated_at=now,
    )


def test_blueprint_lifecycle_supports_governed_promotion_and_retirement() -> None:
    assert BLUEPRINT_LIFECYCLES == {
        "proposed",
        "reviewed",
        "reusable",
        "deprecated",
        "improved",
    }
    require_blueprint_transition("proposed", "reviewed")
    require_blueprint_transition("reviewed", "reusable")
    require_blueprint_transition("reusable", "improved")
    require_blueprint_transition("improved", "reusable")
    require_blueprint_transition("reusable", "deprecated")


def test_blueprint_lifecycle_rejects_unreviewed_reuse() -> None:
    with pytest.raises(BlueprintLifecycleError, match="proposed to reusable"):
        require_blueprint_transition("proposed", "reusable")


def test_reusable_blueprint_requires_meaningful_review_evidence() -> None:
    with pytest.raises(BlueprintLifecycleError, match="named evidence reviewer"):
        require_reuse_evidence({})
    with pytest.raises(BlueprintLifecycleError, match="validation summary"):
        require_reuse_evidence({"reviewed_by": "alice"})
    with pytest.raises(BlueprintLifecycleError, match="evidence references"):
        require_reuse_evidence(
            {"reviewed_by": "alice", "validation_summary": "Validated in staging"}
        )
    require_reuse_evidence(
        {
            "reviewed_by": "alice",
            "validation_summary": "Validated against the governed canary",
            "evidence_refs": ["audit:event-1"],
        }
    )


def test_blueprint_migration_preserves_deprecated_history() -> None:
    migration = (
        __import__("pathlib").Path(__file__).resolve().parents[3]
        / "migrations/versions/e9a4b7c2d6f1_add_governed_blueprint_lifecycle.py"
    ).read_text(encoding="utf-8")

    assert "blueprint_assets" in migration
    assert "blueprint_decisions" in migration
    assert "deprecated" in migration
    assert 'ondelete="RESTRICT"' in migration
    assert 'sa.Column("organization_id", sa.UUID(), nullable=False)' in migration


def test_blueprint_lifecycle_api_is_exposed() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert "/api/v1/blueprints" in paths
    assert "/api/v1/blueprints/{blueprint_id}/transitions" in paths
    assert "/api/v1/blueprints/{blueprint_id}/history" in paths


@pytest.mark.asyncio
async def test_create_blueprint_enforces_org_and_source_project_authority() -> None:
    organization_id = uuid.uuid4()
    project_id = uuid.uuid4()
    request = BlueprintCreateRequest(
        organization_id=organization_id,
        blueprint_key="delivery-pattern",
        version=1,
        title="Delivery Pattern",
        kind="workflow_pattern",
        source_project_id=project_id,
        source_phase="implementation",
        pattern={"steps": ["verify"]},
        evidence={"source": "audit"},
        economic_proof={"result": "measured"},
        recommended_use="Use for controlled delivery",
    )
    session = _Session()
    session.rows[(ProjectModel, project_id)] = _project(project_id)
    wrong_org = _actor(
        "blueprint.write",
        "project.read",
        scopes=frozenset({f"organization:{uuid.uuid4()}", f"project:{project_id}"}),
    )
    with pytest.raises(HTTPException) as denied:
        await propose_blueprint(request, session, wrong_org)  # type: ignore[arg-type]
    assert denied.value.status_code == 403

    actor = _actor(
        "blueprint.write",
        "project.read",
        scopes=frozenset({f"organization:{organization_id}", f"project:{project_id}"}),
    )
    response = await propose_blueprint(request, session, actor)  # type: ignore[arg-type]
    assert response.organization_id == organization_id
    assert response.source_project_id == project_id
    assert isinstance(session.added[-1], BlueprintAssetModel)


@pytest.mark.asyncio
async def test_supersession_is_org_owned_same_key_and_monotonic() -> None:
    organization_id = uuid.uuid4()
    project_id = uuid.uuid4()
    superseded_id = uuid.uuid4()
    session = _Session()
    session.rows[(ProjectModel, project_id)] = _project(project_id)
    actor = _actor(
        "blueprint.write",
        "project.read",
        scopes=frozenset({f"organization:{organization_id}", f"project:{project_id}"}),
    )

    def request(*, version: int, key: str = "delivery-pattern") -> BlueprintCreateRequest:
        return BlueprintCreateRequest(
            organization_id=organization_id,
            blueprint_key=key,
            version=version,
            title="Delivery Pattern",
            kind="workflow_pattern",
            source_project_id=project_id,
            source_phase="implementation",
            supersedes_id=superseded_id,
            pattern={"steps": ["verify"]},
            evidence={"source": "audit"},
            economic_proof={"result": "measured"},
            recommended_use="Use for controlled delivery",
        )

    session.rows[(BlueprintAssetModel, superseded_id)] = _blueprint(uuid.uuid4())
    with pytest.raises(HTTPException) as hidden_cross_org:
        await propose_blueprint(request(version=2), session, actor)  # type: ignore[arg-type]
    assert hidden_cross_org.value.status_code == 404

    session.rows[(BlueprintAssetModel, superseded_id)] = _blueprint(
        organization_id, version=2, key="other-key"
    )
    with pytest.raises(HTTPException, match="same blueprint key"):
        await propose_blueprint(request(version=3), session, actor)  # type: ignore[arg-type]

    session.rows[(BlueprintAssetModel, superseded_id)] = _blueprint(organization_id, version=2)
    with pytest.raises(HTTPException, match="increase monotonically"):
        await propose_blueprint(request(version=2), session, actor)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_source_artifact_must_belong_to_authorized_source_project() -> None:
    organization_id = uuid.uuid4()
    project_id = uuid.uuid4()
    artifact_id = uuid.uuid4()
    session = _Session()
    session.rows[(ProjectModel, project_id)] = _project(project_id)
    session.rows[(ArtifactModel, artifact_id)] = ArtifactModel(
        id=artifact_id,
        project_id=uuid.uuid4(),
        artifact_type="review",
        media_type="application/json",
        content='{"status":"passed"}',
        content_hash="b" * 64,
    )
    actor = _actor(
        "blueprint.write",
        "project.read",
        scopes=frozenset({f"organization:{organization_id}", f"project:{project_id}"}),
    )
    request = BlueprintCreateRequest(
        organization_id=organization_id,
        blueprint_key="delivery-pattern",
        title="Delivery Pattern",
        kind="workflow_pattern",
        source_project_id=project_id,
        source_phase="review",
        source_artifact_id=artifact_id,
        pattern={"steps": ["verify"]},
        evidence={"source": "audit"},
        economic_proof={"result": "measured"},
        recommended_use="Use for controlled delivery",
    )
    with pytest.raises(HTTPException, match="must belong to the source project"):
        await propose_blueprint(request, session, actor)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_list_is_org_filtered_and_hides_deprecated_by_default() -> None:
    organization_id = uuid.uuid4()
    session = _Session()
    session.query_rows = [_blueprint(organization_id)]
    actor = _actor("blueprint.read", scopes=frozenset({f"organization:{organization_id}"}))
    rows = await list_blueprints(  # type: ignore[arg-type]
        session, actor, organization_id, None, None, False, 100
    )
    assert len(rows) == 1
    sql = str(session.statements[-1])
    assert "blueprint_assets.organization_id" in sql
    assert "blueprint_assets.lifecycle !=" in sql
    await list_blueprints(  # type: ignore[arg-type]
        session, actor, organization_id, None, None, True, 100
    )
    assert "blueprint_assets.lifecycle !=" not in str(session.statements[-1])


@pytest.mark.asyncio
async def test_transition_and_history_enforce_owning_org_and_persist_decision() -> None:
    organization_id = uuid.uuid4()
    blueprint = _blueprint(organization_id, lifecycle="reviewed")
    session = _Session()
    session.rows[(BlueprintAssetModel, blueprint.id)] = blueprint
    wrong_actor = _actor(
        "blueprint.review", scopes=frozenset({f"organization:{uuid.uuid4()}"})
    )
    request = BlueprintTransitionRequest(
        lifecycle="reusable",
        rationale="Canary and review passed",
        evidence={
            "reviewed_by": "review-board",
            "validation_summary": "Validated against controlled canary",
            "evidence_refs": ["audit:event-1"],
        },
    )
    with pytest.raises(HTTPException) as denied:
        await transition_blueprint(blueprint.id, request, session, wrong_actor)  # type: ignore[arg-type]
    assert denied.value.status_code == 403

    reviewer = _actor(
        "blueprint.review", scopes=frozenset({f"organization:{organization_id}"})
    )
    response = await transition_blueprint(blueprint.id, request, session, reviewer)  # type: ignore[arg-type]
    assert response.previous_lifecycle == "reviewed"
    assert response.lifecycle == "reusable"
    assert blueprint.lifecycle == "reusable"
    assert isinstance(session.added[-1], BlueprintDecisionModel)

    session.query_rows = [session.added[-1]]
    reader = _actor("blueprint.read", scopes=frozenset({f"organization:{organization_id}"}))
    history = await blueprint_history(blueprint.id, session, reader)  # type: ignore[arg-type]
    assert [item.lifecycle for item in history] == ["reusable"]


@pytest.mark.asyncio
async def test_duplicate_and_concurrent_conflicts_are_recoverable() -> None:
    organization_id = uuid.uuid4()
    project_id = uuid.uuid4()
    actor = _actor(
        "blueprint.write",
        "project.read",
        scopes=frozenset({f"organization:{organization_id}", f"project:{project_id}"}),
    )
    session = _Session()
    session.rows[(ProjectModel, project_id)] = _project(project_id)
    session.commit_error = IntegrityError("insert", {}, Exception("duplicate"))
    request = BlueprintCreateRequest(
        organization_id=organization_id,
        blueprint_key="delivery-pattern",
        title="Delivery Pattern",
        kind="workflow_pattern",
        source_project_id=project_id,
        source_phase="implementation",
        pattern={"steps": ["verify"]},
        evidence={"source": "audit"},
        economic_proof={"result": "measured"},
        recommended_use="Use for controlled delivery",
    )
    with pytest.raises(HTTPException) as conflict:
        await propose_blueprint(request, session, actor)  # type: ignore[arg-type]
    assert conflict.value.status_code == 409
    assert session.rollbacks == 1

    blueprint = _blueprint(organization_id, lifecycle="reviewed")
    concurrent = _Session()
    concurrent.rows[(BlueprintAssetModel, blueprint.id)] = blueprint
    concurrent.commit_error = IntegrityError("update", {}, Exception("concurrent change"))
    reviewer = _actor(
        "blueprint.review", scopes=frozenset({f"organization:{organization_id}"})
    )
    transition = BlueprintTransitionRequest(
        lifecycle="reusable",
        rationale="Canary and review passed",
        evidence={
            "reviewed_by": "review-board",
            "validation_summary": "Validated against controlled canary",
            "evidence_refs": ["audit:event-1"],
        },
    )
    with pytest.raises(HTTPException, match="changed concurrently") as concurrent_conflict:
        await transition_blueprint(  # type: ignore[arg-type]
            blueprint.id, transition, concurrent, reviewer
        )
    assert concurrent_conflict.value.status_code == 409
    assert concurrent.rollbacks == 1
