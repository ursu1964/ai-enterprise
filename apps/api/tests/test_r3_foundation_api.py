import json
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from ai_enterprise.api.dependencies import Actor, get_actor
from ai_enterprise.api.project_formation_schemas import ClientBlueprintResponse
from ai_enterprise.application.project_formation_service import (
    ProjectFormationError,
    ProjectFormationService,
)
from ai_enterprise.domain.aeir import compile_aepm
from ai_enterprise.domain.aepm import AepmManifest
from ai_enterprise.domain.hashing import hash_json
from ai_enterprise.infrastructure.database.models import ProjectModel
from ai_enterprise.infrastructure.database.session import get_session
from ai_enterprise.infrastructure.knowledge.models import (
    AeirModelVersionModel,
    AeirProjectSnapshotModel,
    AeirValidationFindingModel,
)
from ai_enterprise.main import app

ROOT = Path(__file__).resolve().parents[3]


def _actor() -> Actor:
    return Actor(subject="client-reviewer", actor_type="human", role="platform-admin")


def test_r3_foundation_openapi_exposes_minimal_project_endpoints() -> None:
    paths = app.openapi()["paths"]

    for path in (
        "/api/v1/projects/import",
        "/api/v1/projects/{project_id}/foundation",
        "/api/v1/projects/{project_id}/objects",
        "/api/v1/projects/{project_id}/objects/{object_id}",
        "/api/v1/projects/{project_id}/relationships",
        "/api/v1/projects/{project_id}/validation-runs",
        "/api/v1/projects/{project_id}/validation-findings",
        "/api/v1/projects/{project_id}/validation-findings/{finding_id}/resolution",
        "/api/v1/projects/{project_id}/snapshots",
        "/api/v1/projects/{project_id}/snapshots/{snapshot_id}",
    ):
        assert path in paths


def test_r3_foundation_import_route_serializes_success(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    project_id = uuid.uuid4()

    async def fake_session():
        yield object()

    async def fake_actor():
        return _actor()

    async def import_manifest(self, request, *, actor_id):  # type: ignore[no-untyped-def]
        assert actor_id == "client-reviewer"
        assert request.content_type == "application/yaml"
        return ClientBlueprintResponse(
            project_id=project_id,
            status="ready_for_approval",
            review_state="awaiting_client_review",
            project_name="Inventory Management Platform",
            source_manifest_sha256="a" * 64,
            validation_report={"valid": True, "findings": []},
            interpretation_batch=None,
            clarification_report={"report_sha256": "b" * 64},
            missing_information=[],
            assumptions=[],
            canonical_model={"model_sha256": "c" * 64},
            canonical_object_count=12,
            relationship_count=11,
            artifacts=[],
            blueprint_download_url=None,
            traceability={"source_object": {"provider": "local"}},
            proof={"project_snapshot_id": "SNP-0001", "project_snapshot_status": "draft"},
            next_action="Review the deterministic project model.",
        )

    monkeypatch.setattr(
        ProjectFormationService, "import_client_blueprint_manifest", import_manifest
    )
    app.dependency_overrides[get_session] = fake_session
    app.dependency_overrides[get_actor] = fake_actor
    try:
        response = TestClient(app).post(
            "/api/v1/projects/import",
            json={"manifest_text": "schema_version: aepm-0.1", "content_type": "application/yaml"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == str(project_id)
    assert payload["canonical_model_sha256"] == "c" * 64
    assert payload["snapshot_id"] == "SNP-0001"


def test_r3_foundation_import_route_returns_structured_422(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def fake_session():
        yield object()

    async def fake_actor():
        return _actor()

    async def reject_manifest(self, request, *, actor_id):  # type: ignore[no-untyped-def]
        raise ProjectFormationError("Manifest schema validation failed")

    monkeypatch.setattr(
        ProjectFormationService, "import_client_blueprint_manifest", reject_manifest
    )
    app.dependency_overrides[get_session] = fake_session
    app.dependency_overrides[get_actor] = fake_actor
    try:
        response = TestClient(app).post(
            "/api/v1/projects/import",
            json={"manifest": {"invalid": True}},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["detail"] == "Manifest schema validation failed"


def test_r3_foundation_snapshot_route_reconstructs_model(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    project_id = uuid.uuid4()
    model_version_id = uuid.uuid4()
    model_document = {
        "schema_version": "aeir-0.1",
        "source_manifest_sha256": "a" * 64,
        "objects": [{"id": "PROJ-001", "type": "project"}],
        "relationships": [],
        "model_sha256": "b" * 64,
    }
    snapshot_document = {
        "schema_version": "aeir-snapshot-0.1",
        "snapshot_id": "SNP-0007",
        "project_id": "PROJ-001",
        "aepm_version": "0.1",
        "aeir_version": "0.1",
        "source_model_sha256": "b" * 64,
        "object_versions": ["PROJ-001:0.1.0"],
        "relationship_versions": [],
        "status": "approved",
        "created_at": "2026-08-05T00:00:00Z",
        "snapshot_sha256": "c" * 64,
    }
    model_version = AeirModelVersionModel(
        id=model_version_id,
        project_id=project_id,
        version_number=1,
        schema_version="aeir-0.1",
        source_manifest_sha256="a" * 64,
        model_sha256="b" * 64,
        model_document=model_document,
        created_by="client-reviewer",
    )
    snapshot = AeirProjectSnapshotModel(
        id=uuid.uuid4(),
        project_id=project_id,
        model_version_id=model_version_id,
        snapshot_id="SNP-0007",
        aepm_version="0.1",
        aeir_version="0.1",
        status="approved",
        object_versions=["PROJ-001:0.1.0"],
        snapshot_document=snapshot_document,
        snapshot_sha256="c" * 64,
        created_by="client-reviewer",
    )

    class SnapshotSession:
        async def scalar(self, statement):  # type: ignore[no-untyped-def]
            return snapshot

        async def get(self, model, identity):  # type: ignore[no-untyped-def]
            assert model is AeirModelVersionModel
            assert identity == model_version_id
            return model_version

    async def fake_session():
        yield SnapshotSession()

    async def fake_actor():
        return _actor()

    app.dependency_overrides[get_session] = fake_session
    app.dependency_overrides[get_actor] = fake_actor
    try:
        response = TestClient(app).get(
            f"/api/v1/projects/{project_id}/snapshots/SNP-0007"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot_id"] == "SNP-0007"
    assert payload["status"] == "approved"
    assert payload["source_model_sha256"] == "b" * 64
    assert payload["reconstructed_model"] == model_document


def test_r3_foundation_snapshot_route_creates_immutable_snapshot(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    manifest = json.loads(
        (ROOT / "examples/sample-project/aepm-0.1.json").read_text(encoding="utf-8")
    )
    model = compile_aepm(AepmManifest.model_validate(manifest))
    project_id = uuid.uuid4()
    model_version = AeirModelVersionModel(
        id=uuid.uuid4(),
        project_id=project_id,
        version_number=1,
        schema_version=model.schema_version,
        source_manifest_sha256=model.source_manifest_sha256,
        model_sha256=model.model_sha256,
        model_document=model.model_dump(mode="json"),
        created_by="client-reviewer",
    )
    project = ProjectModel(
        id=project_id,
        name="Service Request Portal",
        status="ready_for_approval",
        manifest=manifest,
        manifest_hash=hash_json(manifest),
    )

    class SnapshotCreateSession:
        def __init__(self) -> None:
            self.scalar_values = [model_version, "SNP-0001", 3, "d" * 64]
            self.added: list[object] = []
            self.committed = False

        async def get(self, model_class, identity):  # type: ignore[no-untyped-def]
            assert model_class is ProjectModel
            assert identity == project_id
            return project

        async def scalar(self, statement):  # type: ignore[no-untyped-def]
            return self.scalar_values.pop(0)

        def add_all(self, values):  # type: ignore[no-untyped-def]
            self.added.extend(values)

        async def commit(self) -> None:
            self.committed = True

    session = SnapshotCreateSession()

    async def fake_session():
        yield session

    async def fake_actor():
        return _actor()

    app.dependency_overrides[get_session] = fake_session
    app.dependency_overrides[get_actor] = fake_actor
    try:
        response = TestClient(app).post(
            f"/api/v1/projects/{project_id}/snapshots",
            json={"status": "draft"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot_id"] == "SNP-0002"
    assert payload["status"] == "draft"
    assert payload["source_model_sha256"] == model.model_sha256
    assert payload["object_count"] == len(model.objects)
    assert session.committed is True


def test_r3_foundation_validation_run_persists_structured_findings(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    project_id = uuid.uuid4()
    project = ProjectModel(
        id=project_id,
        name="Incomplete Inventory Platform",
        status="draft",
        manifest={
            "schema_version": "aepm-0.1",
            "project_intent": {"name": "Incomplete", "summary": "Missing problem."},
            "business_outcomes": [],
            "stakeholders": [],
            "capabilities": [],
            "core_processes": [],
            "business_rules": [],
            "data_entities": [],
            "integrations": [],
            "quality_requirements": [],
            "constraints": [],
            "preferred_technology_targets": {
                "frontend": [],
                "backend": [],
                "database": [],
                "queue": [],
                "object_storage": [],
                "deployment": [],
            },
        },
        manifest_hash="e" * 64,
    )

    class ValidationSession:
        def __init__(self) -> None:
            self.scalar_values = [None, None, 0, None]
            self.added: list[object] = []
            self.committed = False

        async def get(self, model_class, identity):  # type: ignore[no-untyped-def]
            assert model_class is ProjectModel
            assert identity == project_id
            return project

        async def scalar(self, statement):  # type: ignore[no-untyped-def]
            return self.scalar_values.pop(0)

        def add_all(self, values):  # type: ignore[no-untyped-def]
            self.added.extend(values)

        def add(self, value):  # type: ignore[no-untyped-def]
            self.added.append(value)

        async def commit(self) -> None:
            self.committed = True

    session = ValidationSession()

    async def fake_session():
        yield session

    async def fake_actor():
        return _actor()

    app.dependency_overrides[get_session] = fake_session
    app.dependency_overrides[get_actor] = fake_actor
    try:
        response = TestClient(app).post(f"/api/v1/projects/{project_id}/validation-runs")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["findings"]
    assert any(isinstance(item, AeirValidationFindingModel) for item in session.added)
    assert session.committed is True
