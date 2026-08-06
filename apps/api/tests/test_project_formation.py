import copy
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from fastapi.testclient import TestClient

from ai_enterprise.api.dependencies import Actor, get_actor
from ai_enterprise.api.project_formation_schemas import (
    ClientBlueprintClarificationAnswerRequest,
    ClientBlueprintImportRequest,
    ClientBlueprintResponse,
    ClientBlueprintReviewRequest,
    FormationRequest,
)
from ai_enterprise.application import mock_factory_autonomy
from ai_enterprise.application.mock_factory_autonomy import (
    MockEnterpriseAutonomyService,
    MockFactorySpec,
)
from ai_enterprise.application.project_formation_service import (
    ProjectFormationError,
    ProjectFormationService,
)
from ai_enterprise.application.project_foundry_workspace import (
    ProjectFoundryWorkspaceError,
    ProjectFoundryWorkspaceService,
)
from ai_enterprise.config import Settings
from ai_enterprise.domain.aepm_interpretation import AiOperationRecord, _operation_hash
from ai_enterprise.domain.aepm_validation import AepmValidationEngine
from ai_enterprise.domain.clarification import generate_clarification_report
from ai_enterprise.domain.enums import ArtifactType, ProjectStatus
from ai_enterprise.domain.hashing import canonical_json, hash_json
from ai_enterprise.infrastructure.database.models import (
    ApprovalModel,
    ArtifactModel,
    AuditEventModel,
    ProjectModel,
)
from ai_enterprise.infrastructure.database.session import get_session
from ai_enterprise.infrastructure.knowledge.models import (
    AeirAiOperationModel,
    AeirArtifactTraceLinkModel,
    AeirArtifactVersionModel,
    AeirChangeEventModel,
    AeirClarificationAnswerModel,
    AeirClarificationQuestionModel,
    AeirDecisionModel,
    AeirEvidenceModel,
    AeirModelVersionModel,
    AeirObjectSourceLinkModel,
    AeirObjectVersionModel,
    AeirProjectSnapshotModel,
    AeirRelationshipSourceLinkModel,
    AeirRelationshipVersionModel,
    AeirSourceObjectModel,
)
from ai_enterprise.main import app

ROOT = Path(__file__).resolve().parents[3]


class FormationSession:
    def __init__(self, project: ProjectModel | None) -> None:
        self.project = project
        self.added: list[object] = []
        self.scalar_values: list[object | None] = [None, None]
        self.committed = False

    async def get(self, model: type, identity: uuid.UUID) -> object | None:
        return self.project

    async def scalar(self, statement: object) -> object | None:
        return self.scalar_values.pop(0) if self.scalar_values else None

    def add(self, value: object) -> None:
        self.added.append(value)

    def add_all(self, values: list[object]) -> None:
        self.added.extend(values)

    async def commit(self) -> None:
        self.committed = True


class PreviewSession:
    def __init__(self, scalar_rows: list[object | None]) -> None:
        self.scalar_rows = scalar_rows
        self.committed = False

    async def scalar(self, statement: object) -> object | None:
        return self.scalar_rows.pop(0) if self.scalar_rows else None

    async def commit(self) -> None:
        self.committed = True


def project(project_id: uuid.UUID) -> ProjectModel:
    now = datetime.now(UTC)
    return ProjectModel(
        id=project_id,
        name="Formation Project",
        description="A project used for deterministic formation pack tests.",
        repository_path="/home/user/projects/formation-project",
        repository_url=None,
        default_branch="main",
        status=ProjectStatus.CREATED,
        manifest_hash="0" * 64,
        manifest={"project_type": "dashboards_reporting"},
        created_at=now,
        updated_at=now,
    )


def sample_aepm() -> dict[str, object]:
    return json.loads(
        (ROOT / "examples/sample-project/aepm-0.1.json").read_text(encoding="utf-8")
    )


def sample_interpretation_output() -> dict[str, object]:
    return {
        "schema_version": "aepm-interpretation-output-0.1",
        "items": [
            {
                "id": "AI-001",
                "task": "classification",
                "content": "The portal must handle peak open-enrollment traffic.",
                "rationale": "Client prose states an expected peak but not approved capacity.",
                "status": "unverified",
                "confidence": 0.72,
                "source_references": ["client-prose/traffic"],
                "target_object_ids": ["QUAL-001"],
                "classification": "assumption",
            },
            {
                "id": "AI-002",
                "task": "clarification_question",
                "content": "Which identity provider owns production sign-in?",
                "rationale": "The manifest names authentication but not the provider owner.",
                "status": "inferred",
                "confidence": 0.81,
                "source_references": ["client-prose/security"],
                "target_object_ids": ["INT-001"],
            },
        ],
    }


def sample_ai_operation() -> dict[str, object]:
    provisional = AiOperationRecord.model_construct(
        model_provider="openai",
        model_name="gpt-5.1",
        operation_type="extraction",
        prompt_version="aepm-extractor-0.1.3",
        generated_at="2026-08-05T00:00:00Z",
        input_source_refs=("client-manifest:sample",),
        review_required=True,
        operation_sha256="0" * 64,
    )
    return {
        **provisional.model_dump(mode="json"),
        "operation_sha256": _operation_hash(provisional),
    }


def test_project_formation_exposes_mock_factory_autonomy_route() -> None:
    paths = app.openapi()["paths"]

    assert "/api/v1/project-formation/mock-factory/start" in paths
    operation = paths["/api/v1/project-formation/mock-factory/start"]["post"]
    assert operation["responses"]["202"]["description"] == "Successful Response"
    assert "/api/v1/project-formation/mock-factory/preview" in paths
    preview = paths["/api/v1/project-formation/mock-factory/preview"]["get"]
    assert preview["responses"]["200"]["description"] == "Successful Response"
    assert "/api/v1/project-formation/projects/{project_id}/foundry-workspace" in paths
    foundry = paths["/api/v1/project-formation/projects/{project_id}/foundry-workspace"]["post"]
    assert foundry["responses"]["201"]["description"] == "Successful Response"
    assert "/api/v1/project-formation/client-blueprints/import" in paths
    assert "/api/v1/project-formation/client-blueprints/{project_id}/review" in paths
    assert (
        "/api/v1/project-formation/client-blueprints/{project_id}/clarifications/answers"
        in paths
    )
    assert "/api/v1/project-formation/client-blueprints/{project_id}/download" in paths
    schemas = app.openapi()["components"]["schemas"]
    launch_summary = schemas["MockFactoryLaunchSummaryResponse"]["properties"]
    project_result = schemas["MockFactoryProjectResponse"]["properties"]
    assert "review_needed_count" in launch_summary
    assert "recommended_first_project_id" in launch_summary
    assert "recommended_first_project_url" in launch_summary
    assert "result_category" in project_result


def test_clarification_answer_route_maps_contract_failures_to_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_session():
        yield object()

    async def fake_actor():
        return Actor(subject="client-reviewer", actor_type="human", role="platform-admin")

    async def fail_answer(self, project_id, request, *, actor_id):  # type: ignore[no-untyped-def]
        assert actor_id == "client-reviewer"
        assert request.answers == [{"not": "valid"}]
        raise ProjectFormationError("Clarification answers failed validation")

    monkeypatch.setattr(
        ProjectFormationService,
        "answer_client_blueprint_clarifications",
        fail_answer,
    )
    app.dependency_overrides[get_session] = fake_session
    app.dependency_overrides[get_actor] = fake_actor
    try:
        response = TestClient(app).post(
            f"/api/v1/project-formation/client-blueprints/{uuid.uuid4()}"
            "/clarifications/answers",
            json={"clarification_report": {}, "answers": [{"not": "valid"}]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["detail"] == "Clarification answers failed validation"


def test_clarification_answer_route_serializes_success_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = uuid.uuid4()

    async def fake_session():
        yield object()

    async def fake_actor():
        return Actor(subject="client-reviewer", actor_type="human", role="platform-admin")

    async def answer(  # type: ignore[no-untyped-def]
        self, actual_project_id, request, *, actor_id
    ):
        assert actual_project_id == project_id
        assert actor_id == "client-reviewer"
        assert request.respondent_id == "client-reviewer"
        return ClientBlueprintResponse(
            project_id=actual_project_id,
            status="review",
            review_state="clarifications_answered",
            project_name="Inventory Platform",
            source_manifest_sha256="a" * 64,
            validation_report={"valid": True},
            interpretation_batch=None,
            clarification_report={"report_sha256": "b" * 64},
            missing_information=[],
            assumptions=[],
            canonical_model={"schema_version": "aeir-0.1", "objects": []},
            canonical_object_count=0,
            relationship_count=0,
            artifacts=[],
            blueprint_download_url=None,
            traceability={"section_trace_count": 0},
            proof={"ready": True},
            next_action="Review generated artifacts.",
        )

    monkeypatch.setattr(
        ProjectFormationService,
        "answer_client_blueprint_clarifications",
        answer,
    )
    app.dependency_overrides[get_session] = fake_session
    app.dependency_overrides[get_actor] = fake_actor
    try:
        response = TestClient(app).post(
            f"/api/v1/project-formation/client-blueprints/{project_id}"
            "/clarifications/answers",
            json={
                "clarification_report": {"report_sha256": "b" * 64},
                "answers": [{"question_id": "Q-001", "response": "Confirmed."}],
                "respondent_id": "client-reviewer",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == str(project_id)
    assert payload["review_state"] == "clarifications_answered"
    assert payload["proof"]["ready"] is True


@pytest.mark.asyncio
async def test_client_blueprint_import_persists_traceable_first_release_flow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = FormationSession(None)
    monkeypatch.setattr(
        "ai_enterprise.application.project_formation_service.get_settings",
        lambda: SimpleNamespace(artifact_root=tmp_path),
    )
    manifest = sample_aepm()

    response = await ProjectFormationService(session).import_client_blueprint_manifest(
        ClientBlueprintImportRequest(manifest=manifest),
        actor_id="client-reviewer",
    )

    assert response.review_state == "awaiting_client_review"
    assert response.interpretation_batch is None
    assert response.clarification_report["schema_version"] == "clarification-report-0.1"
    assert response.missing_information == []
    assert response.canonical_object_count > 10
    assert response.relationship_count > 0
    assert response.blueprint_download_url is not None
    source = response.traceability["source_object"]
    assert response.proof["schema_version"] == "r1-manifest-to-blueprint-proof-0.1"
    assert response.proof["ready"] is True
    assert response.proof["source_object"] == source
    assert response.proof["source_manifest_sha256"] == response.source_manifest_sha256
    assert response.proof["validation_report_sha256"] == response.validation_report[
        "report_sha256"
    ]
    assert response.proof["clarification_report_sha256"] == response.clarification_report[
        "report_sha256"
    ]
    assert response.proof["aeir_model_version_id"] is not None
    assert response.proof["aeir_change_event_hash"] is not None
    assert response.proof["artifact_count"] == 5
    assert response.proof["stored_artifact_count"] == 7
    assert response.proof["canonical_object_count"] == response.canonical_object_count
    assert source["provider"] == "local"
    assert source["bucket"] == "aepm-sources"
    assert source["content_sha256"] == hash_json(manifest)
    stored_source = tmp_path / source["bucket"] / source["object_key"]
    assert stored_source.read_bytes() == canonical_json(manifest).encode("utf-8")
    assert response.traceability["section_trace_count"] > 0
    assert response.traceability["entry_trace_count"] > 0
    assert {item.artifact_type for item in response.artifacts} == {
        "project_manifest",
        "canonical_project_model",
        "project_snapshot",
        "project_blueprint",
        "traceability_manifest",
        "artifact_contracts",
        "artifact_validation_report",
    }
    assert response.proof["project_snapshot_id"] == "SNP-0001"
    assert response.proof["project_snapshot_status"] == "draft"
    assert response.proof["artifact_contract_count"] == 5
    assert response.proof["artifact_validation_valid"] is True
    assert any(isinstance(item, ProjectModel) for item in session.added)
    assert any(
        isinstance(item, ArtifactModel) and item.artifact_type == "project_blueprint"
        for item in session.added
    )
    assert any(
        isinstance(item, AeirSourceObjectModel)
        and item.object_key == source["object_key"]
        and item.content_sha256 == source["content_sha256"]
        and item.source_metadata["stage"] == "client_blueprint_import"
        for item in session.added
    )
    assert any(
        isinstance(item, AeirModelVersionModel)
        and item.model_sha256 == response.canonical_model["model_sha256"]
        for item in session.added
    )
    assert any(
        isinstance(item, AeirChangeEventModel)
        and item.payload["source_object_count"] == 1
        for item in session.added
    )
    assert any(
        isinstance(item, AeirProjectSnapshotModel)
        and item.snapshot_sha256 == response.proof["project_snapshot_sha256"]
        and item.status == "draft"
        for item in session.added
    )
    assert sum(isinstance(item, AeirObjectVersionModel) for item in session.added) == (
        response.canonical_object_count
    )
    assert sum(isinstance(item, AeirRelationshipVersionModel) for item in session.added) == (
        response.relationship_count
    )
    assert any(isinstance(item, AeirEvidenceModel) for item in session.added)
    assert any(isinstance(item, AeirObjectSourceLinkModel) for item in session.added)
    assert any(isinstance(item, AeirRelationshipSourceLinkModel) for item in session.added)
    assert sum(isinstance(item, AeirArtifactVersionModel) for item in session.added) == 5
    assert any(isinstance(item, AeirArtifactTraceLinkModel) for item in session.added)
    assert any(
        isinstance(item, AuditEventModel)
        and item.event_type == "client_blueprint.manifest_imported"
        and item.payload["source_object"] == source
        and item.payload["aeir_change_event_hash"]
        for item in session.added
    )
    assert session.committed is True


@pytest.mark.asyncio
async def test_client_blueprint_clarification_answers_are_hash_bound_and_persisted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id = uuid.uuid4()
    existing = project(project_id)
    existing.manifest = sample_aepm()
    existing.manifest_hash = hash_json(existing.manifest)
    session = FormationSession(existing)
    monkeypatch.setattr(
        "ai_enterprise.application.project_formation_service.get_settings",
        lambda: SimpleNamespace(artifact_root=tmp_path),
    )
    service = ProjectFormationService(session)
    interpretation = service._interpretation_batch(
        document=existing.manifest,
        interpretation_output=sample_interpretation_output(),
        ai_operation=sample_ai_operation(),
    )
    report = generate_clarification_report(
        AepmValidationEngine().validate(existing.manifest),
        interpretation,
    )
    question = next(item for item in report.questions() if "INT-001" in item.target_object_ids)

    response = await service.answer_client_blueprint_clarifications(
        project_id,
        ClientBlueprintClarificationAnswerRequest(
            clarification_report=report.model_dump(mode="json"),
            answers=[
                {
                    "question_id": question.id,
                    "response": "The managed OIDC provider owns production sign-in.",
                    "resolution": "answered",
                    "rationale": "Confirmed by the platform owner.",
                    "corrections": [
                        {
                            "target_object_id": "INT-001",
                            "field": "description",
                            "proposed_value": (
                                "Managed OIDC provider owns production customer and "
                                "operator sign-in."
                            ),
                        }
                    ],
                }
            ],
        ),
        actor_id="client-reviewer",
    )

    integration = next(
        item for item in response.canonical_model["objects"] if item["id"] == "INT-001"
    )
    assert response.review_state == "clarifications_answered"
    assert response.proof["ready"] is True
    assert response.proof["stored_artifact_count"] == 7
    assert integration["description"] == (
        "Managed OIDC provider owns production customer and operator sign-in."
    )
    assert integration["approval_status"] == "approved"
    assert any(
        isinstance(item, AeirClarificationAnswerModel)
        and item.respondent_id == "client-reviewer"
        and item.answer_document["answer"]["question_id"] == question.id
        for item in session.added
    )
    assert any(
        isinstance(item, AeirChangeEventModel)
        and item.payload["clarification_answer_count"] == 1
        for item in session.added
    )
    assert any(isinstance(item, AeirEvidenceModel) for item in session.added)
    assert any(isinstance(item, AeirObjectSourceLinkModel) for item in session.added)
    assert any(isinstance(item, AeirRelationshipSourceLinkModel) for item in session.added)
    assert sum(isinstance(item, AeirArtifactVersionModel) for item in session.added) == 5
    audit = next(
        item
        for item in session.added
        if isinstance(item, AuditEventModel)
        and item.event_type == "client_blueprint.clarifications_answered"
    )
    assert audit.payload["answer_count"] == 1
    assert audit.payload["answer_batch_sha256"]
    assert session.committed is True


@pytest.mark.asyncio
async def test_client_blueprint_clarification_answers_use_next_snapshot_and_artifact_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id = uuid.uuid4()
    existing = project(project_id)
    existing.manifest = sample_aepm()
    existing.manifest_hash = hash_json(existing.manifest)
    session = FormationSession(existing)
    session.scalar_values = ["SNP-0003", 3, 9, 4, "a" * 64]
    monkeypatch.setattr(
        "ai_enterprise.application.project_formation_service.get_settings",
        lambda: SimpleNamespace(artifact_root=tmp_path),
    )
    service = ProjectFormationService(session)
    interpretation = service._interpretation_batch(
        document=existing.manifest,
        interpretation_output=sample_interpretation_output(),
        ai_operation=sample_ai_operation(),
    )
    report = generate_clarification_report(
        AepmValidationEngine().validate(existing.manifest),
        interpretation,
    )
    question = next(item for item in report.questions() if "INT-001" in item.target_object_ids)

    response = await service.answer_client_blueprint_clarifications(
        project_id,
        ClientBlueprintClarificationAnswerRequest(
            clarification_report=report.model_dump(mode="json"),
            answers=[
                {
                    "question_id": question.id,
                    "response": "The platform team owns production sign-in.",
                    "resolution": "answered",
                    "rationale": "Confirmed by client.",
                    "corrections": [],
                }
            ],
        ),
        actor_id="client-reviewer",
    )

    snapshot = next(item for item in session.added if isinstance(item, AeirProjectSnapshotModel))
    artifact_versions = [
        item for item in session.added if isinstance(item, AeirArtifactVersionModel)
    ]
    event = next(item for item in session.added if isinstance(item, AeirChangeEventModel))

    assert response.proof["project_snapshot_id"] == "SNP-0004"
    assert snapshot.snapshot_id == "SNP-0004"
    assert {item.version_number for item in artifact_versions} == {10}
    assert event.sequence == 5
    assert event.previous_hash == "a" * 64


@pytest.mark.asyncio
async def test_client_blueprint_clarification_answers_reject_stale_report() -> None:
    project_id = uuid.uuid4()
    existing = project(project_id)
    existing.manifest = sample_aepm()
    stale_document = sample_aepm()
    stale_document["business_outcomes"][0]["description"] = "TBD metric owner"  # type: ignore[index]
    stale_report = generate_clarification_report(AepmValidationEngine().validate(stale_document))
    question = stale_report.unverified_assumptions[0]
    session = FormationSession(existing)

    with pytest.raises(ProjectFormationError, match="Clarification answers failed validation"):
        await ProjectFormationService(session).answer_client_blueprint_clarifications(
            project_id,
            ClientBlueprintClarificationAnswerRequest(
                clarification_report=stale_report.model_dump(mode="json"),
                answers=[
                    {
                        "question_id": question.id,
                        "response": "This answer belongs to an old report.",
                        "resolution": "answered",
                        "rationale": "Stale report regression.",
                        "corrections": [],
                    }
                ],
            ),
            actor_id="client-reviewer",
        )

    assert session.added == []
    assert session.committed is False


@pytest.mark.asyncio
async def test_client_blueprint_import_binds_structured_ai_interpretation() -> None:
    session = FormationSession(None)
    operation = sample_ai_operation()

    response = await ProjectFormationService(session).import_client_blueprint_manifest(
        ClientBlueprintImportRequest(
            manifest=sample_aepm(),
            interpretation_output=sample_interpretation_output(),
            ai_operation=operation,
        ),
        actor_id="client-reviewer",
    )

    assert response.interpretation_batch is not None
    assert response.interpretation_batch["schema_version"] == "aepm-interpretation-0.1"
    assert response.interpretation_batch["ai_operation"]["model_provider"] == "openai"
    assert (
        response.proof["ai_operation_sha256"]
        == response.interpretation_batch["ai_operation"]["operation_sha256"]
    )
    assert response.proof["ai_operation_review_required"] is True
    assert (
        response.clarification_report["interpretation_batch_sha256"]
        == response.interpretation_batch["batch_sha256"]
    )
    assert any("Which identity provider" in item for item in response.assumptions)
    assert any("peak open-enrollment traffic" in item for item in response.assumptions)
    audit = next(
        item
        for item in session.added
        if isinstance(item, AuditEventModel)
        and item.event_type == "client_blueprint.manifest_imported"
    )
    assert audit.payload["interpretation_batch_sha256"] == response.interpretation_batch[
        "batch_sha256"
    ]
    assert audit.payload["ai_operation_sha256"] == operation["operation_sha256"]
    assert (
        audit.payload["clarification_report_sha256"]
        == response.clarification_report["report_sha256"]
    )
    assert any(
        isinstance(item, AeirAiOperationModel)
        and item.operation_sha256 == operation["operation_sha256"]
        and item.review_required is True
        for item in session.added
    )
    assert any(
        isinstance(item, AeirClarificationQuestionModel)
        and "Which identity provider" in item.question_document["prompt"]
        for item in session.added
    )


@pytest.mark.asyncio
async def test_client_blueprint_import_rejects_ai_operation_without_interpretation() -> None:
    session = FormationSession(None)

    with pytest.raises(Exception, match="requires interpretation_output"):
        await ProjectFormationService(session).import_client_blueprint_manifest(
            ClientBlueprintImportRequest(
                manifest=sample_aepm(),
                ai_operation=sample_ai_operation(),
            ),
            actor_id="client-reviewer",
        )

    assert session.added == []
    assert session.committed is False


@pytest.mark.asyncio
async def test_client_blueprint_import_rejects_invalid_ai_interpretation() -> None:
    session = FormationSession(None)
    invalid = sample_interpretation_output()
    invalid["items"][0]["status"] = "approved"  # type: ignore[index]

    with pytest.raises(Exception, match="structured validation"):
        await ProjectFormationService(session).import_client_blueprint_manifest(
            ClientBlueprintImportRequest(
                manifest=sample_aepm(),
                interpretation_output=invalid,
            ),
            actor_id="client-reviewer",
        )

    assert session.added == []
    assert session.committed is False


@pytest.mark.asyncio
async def test_client_blueprint_import_accepts_yaml_manifest_text() -> None:
    session = FormationSession(None)

    response = await ProjectFormationService(session).import_client_blueprint_manifest(
        ClientBlueprintImportRequest(
            manifest_text=yaml.safe_dump(sample_aepm()),
            content_type="application/yaml",
        ),
        actor_id="client-reviewer",
    )

    assert response.project_name == sample_aepm()["project_intent"]["name"]  # type: ignore[index]
    assert response.validation_report["valid"] is True


@pytest.mark.asyncio
async def test_client_blueprint_review_can_persist_corrected_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id = uuid.uuid4()
    existing = project(project_id)
    existing.manifest = sample_aepm()
    existing.manifest_hash = "0" * 64
    corrected = copy.deepcopy(existing.manifest)
    corrected["project_intent"]["summary"] = "Corrected client-approved operating summary."  # type: ignore[index]
    session = FormationSession(existing)
    monkeypatch.setattr(
        "ai_enterprise.application.project_formation_service.get_settings",
        lambda: SimpleNamespace(artifact_root=tmp_path),
    )

    response = await ProjectFormationService(session).review_client_blueprint(
        project_id,
        ClientBlueprintReviewRequest(
            decision="approved",
            reviewer_comment="Approved after client correction.",
            corrected_manifest=corrected,
        ),
        actor_id="client-reviewer",
    )

    assert response.review_state == "client_approved"
    assert response.proof["ready"] is True
    assert response.proof["aeir_model_version_id"] is not None
    assert response.proof["aeir_change_event_hash"] is not None
    assert response.canonical_model["objects"][0]["description"] == (
        "Corrected client-approved operating summary."
    )
    source = response.traceability["source_object"]
    assert source["content_sha256"] == hash_json(corrected)
    assert (tmp_path / source["bucket"] / source["object_key"]).read_bytes() == (
        canonical_json(corrected).encode("utf-8")
    )
    assert any(
        isinstance(item, AeirSourceObjectModel)
        and item.source_metadata["stage"] == "client_blueprint_review"
        for item in session.added
    )
    assert any(
        isinstance(item, AeirProjectSnapshotModel)
        and item.snapshot_sha256 == response.proof["project_snapshot_sha256"]
        and item.status == "approved"
        for item in session.added
    )
    assert all(
        item.compilation_status == "approved_snapshot"
        for item in session.added
        if isinstance(item, AeirArtifactVersionModel)
    )
    assert any(
        isinstance(item, AeirDecisionModel)
        and item.decision == "approved"
        and item.decision_document["corrected_manifest"] is True
        for item in session.added
    )
    assert existing.manifest == corrected
    assert any(
        isinstance(item, AuditEventModel)
        and item.event_type == "client_blueprint.review_recorded"
        for item in session.added
    )
    assert session.committed is True


@pytest.mark.asyncio
async def test_client_blueprint_review_accepts_yaml_corrected_manifest_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id = uuid.uuid4()
    existing = project(project_id)
    existing.manifest = sample_aepm()
    existing.manifest_hash = hash_json(existing.manifest)
    corrected = copy.deepcopy(existing.manifest)
    corrected["project_intent"]["summary"] = "Corrected from client YAML."  # type: ignore[index]
    session = FormationSession(existing)
    monkeypatch.setattr(
        "ai_enterprise.application.project_formation_service.get_settings",
        lambda: SimpleNamespace(artifact_root=tmp_path),
    )

    response = await ProjectFormationService(session).review_client_blueprint(
        project_id,
        ClientBlueprintReviewRequest(
            decision="changes_requested",
            reviewer_comment="Client submitted YAML corrections.",
            corrected_manifest_text=yaml.safe_dump(corrected),
            content_type="application/yaml",
        ),
        actor_id="client-reviewer",
    )

    assert response.review_state == "client_changes_requested"
    assert response.canonical_model["objects"][0]["description"] == (
        "Corrected from client YAML."
    )
    assert existing.manifest == corrected
    audit = next(
        item
        for item in session.added
        if isinstance(item, AuditEventModel)
        and item.event_type == "client_blueprint.review_recorded"
    )
    assert audit.payload["corrected_manifest"] is True
    assert audit.payload["corrected_manifest_content_type"] == "application/yaml"
    assert session.committed is True


@pytest.mark.asyncio
async def test_client_blueprint_review_without_correction_does_not_duplicate_aeir_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id = uuid.uuid4()
    existing = project(project_id)
    existing.manifest = sample_aepm()
    existing.manifest_hash = hash_json(existing.manifest)
    session = FormationSession(existing)
    model_version = AeirModelVersionModel(
        id=uuid.uuid4(),
        project_id=project_id,
        version_number=1,
        schema_version="aeir-0.1",
        source_manifest_sha256=existing.manifest_hash,
        model_sha256="1" * 64,
        model_document={},
        created_by="client-reviewer",
    )
    session.scalar_values = ["SNP-0001", model_version, 5, 2, "b" * 64]
    monkeypatch.setattr(
        "ai_enterprise.application.project_formation_service.get_settings",
        lambda: SimpleNamespace(artifact_root=tmp_path),
    )

    response = await ProjectFormationService(session).review_client_blueprint(
        project_id,
        ClientBlueprintReviewRequest(
            decision="approved",
            reviewer_comment="Approved without changing the manifest.",
        ),
        actor_id="client-reviewer",
    )

    assert response.review_state == "client_approved"
    assert response.proof["ready"] is True
    assert response.proof["aeir_model_version_id"] is None
    assert response.proof["aeir_change_event_hash"] is None
    assert not any(isinstance(item, AeirModelVersionModel) for item in session.added)
    assert any(
        isinstance(item, AeirProjectSnapshotModel)
        and item.snapshot_id == "SNP-0002"
        and item.status == "approved"
        for item in session.added
    )
    assert all(
        item.compilation_status == "approved_snapshot"
        for item in session.added
        if isinstance(item, AeirArtifactVersionModel)
    )
    assert any(
        isinstance(item, AeirDecisionModel)
        and item.decision == "approved"
        and item.decision_document["corrected_manifest"] is False
        for item in session.added
    )
    snapshot_event = next(item for item in session.added if isinstance(item, AeirChangeEventModel))
    assert snapshot_event.event_type == "aeir.project-snapshot-created"
    assert snapshot_event.sequence == 3
    assert snapshot_event.previous_hash == "b" * 64
    assert sum(isinstance(item, AeirArtifactVersionModel) for item in session.added) == 5
    audit = next(
        item
        for item in session.added
        if isinstance(item, AuditEventModel)
        and item.event_type == "client_blueprint.review_recorded"
    )
    assert audit.payload["aeir_model_version_id"] is None
    assert audit.payload["aeir_change_event_hash"] == snapshot_event.event_hash
    assert audit.payload["aeir_snapshot_event_hash"] == snapshot_event.event_hash
    assert session.committed is True


@pytest.mark.asyncio
async def test_client_blueprint_changes_requested_is_not_recorded_as_rejection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id = uuid.uuid4()
    existing = project(project_id)
    existing.manifest = sample_aepm()
    existing.manifest_hash = hash_json(existing.manifest)
    session = FormationSession(existing)
    monkeypatch.setattr(
        "ai_enterprise.application.project_formation_service.get_settings",
        lambda: SimpleNamespace(artifact_root=tmp_path),
    )

    response = await ProjectFormationService(session).review_client_blueprint(
        project_id,
        ClientBlueprintReviewRequest(
            decision="changes_requested",
            reviewer_comment="Client edited the manifest before final approval.",
            corrected_manifest=existing.manifest,
        ),
        actor_id="client-reviewer",
    )

    assert response.review_state == "client_changes_requested"
    approval = next(item for item in session.added if isinstance(item, ApprovalModel))
    assert approval.decision == "changes_requested"
    audit = next(
        item
        for item in session.added
        if isinstance(item, AuditEventModel)
        and item.event_type == "client_blueprint.review_recorded"
    )
    assert audit.payload["decision"] == "changes_requested"
    assert session.committed is True


@pytest.mark.asyncio
async def test_mock_factory_preview_reports_ready_reuse_without_writes() -> None:
    existing = project(uuid.uuid4())
    existing.name = "AI Enterprise Product Factory Demo"
    existing.repository_path = "/home/user/projects/mock-enterprise/ai-enterprise-product-factory"
    session = PreviewSession([existing, None, None, None])

    response = await MockEnterpriseAutonomyService(  # type: ignore[arg-type]
        session, object()
    ).preview_mock_factory()

    assert response.status == "ready"
    assert response.ready_count == 4
    assert response.launch_plan.mode == "preview"
    assert response.launch_plan.created_count == 3
    assert response.launch_plan.reused_count == 1
    assert response.launch_plan.blocked_count == 0
    assert response.launch_plan.failed_count == 0
    assert response.launch_plan.review_needed_count == 0
    assert response.launch_plan.recommended_first_project_id == existing.id
    assert response.launch_plan.recommended_first_project_name == (
        "AI Enterprise Product Factory Demo"
    )
    assert response.launch_plan.recommended_first_project_url == (
        f"/dashboard?project={existing.id}"
    )
    assert "Start the mock factory" in response.launch_plan.operator_action
    assert response.would_create_count == 3
    assert response.would_reuse_count == 1
    assert response.would_block_count == 0
    assert response.reused_count == 1
    assert response.blocked_count == 0
    assert len(response.would_create) == 3
    assert response.would_reuse == [response.projects[0]]
    assert response.would_block == []
    assert response.projects[0].action == "reuse"
    assert response.projects[0].dashboard_url == f"/dashboard?project={existing.id}"
    assert response.recommended_first_project == response.projects[0]
    assert session.committed is False


@pytest.mark.asyncio
async def test_mock_factory_preview_groups_blocked_launch_items_without_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocked_spec = MockFactorySpec(
        name="No Repository Path",
        description="Create a project with invalid launch information for preview checks.",
        repository_path="relative/path",
        project_type="dashboards_reporting",
        expected_outcome="A preview item that should be blocked before launch starts.",
        target_users=["operator"],
        constraints=["preview only"],
        known_systems=["factory"],
        deadline="today",
        budget_signal="demo",
    )
    monkeypatch.setattr(mock_factory_autonomy, "MOCK_FACTORY_SPECS", (blocked_spec,))
    session = PreviewSession([None])

    response = await MockEnterpriseAutonomyService(  # type: ignore[arg-type]
        session, object()
    ).preview_mock_factory()

    assert response.status == "blocked"
    assert response.ready_count == 0
    assert response.launch_plan.mode == "preview"
    assert response.launch_plan.created_count == 0
    assert response.launch_plan.reused_count == 0
    assert response.launch_plan.blocked_count == 1
    assert response.launch_plan.review_needed_count == 1
    assert response.launch_plan.recommended_first_project_id is None
    assert response.launch_plan.recommended_first_project_name is None
    assert response.launch_plan.recommended_first_project_url is None
    assert "Fix blocked launch information" in response.launch_plan.operator_action
    assert response.would_create_count == 0
    assert response.would_reuse_count == 0
    assert response.would_block_count == 1
    assert response.blocked_count == 1
    assert response.recommended_first_project is None
    assert response.projects[0].ready is False
    assert response.would_block[0].status == "blocked"
    assert response.would_block[0].issues == ["repository path must be absolute"]
    assert session.committed is False


@pytest.mark.asyncio
async def test_mock_factory_start_reports_structured_recommendation_and_categories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_project = project(uuid.uuid4())
    created_project.name = "Created Demo"
    created_project.repository_path = "/home/user/projects/mock-enterprise/created-demo"
    reused_project = project(uuid.uuid4())
    reused_project.name = "Reused Demo"
    reused_project.repository_path = "/home/user/projects/mock-enterprise/reused-demo"
    specs = (
        MockFactorySpec(
            name=created_project.name,
            description="Create a new mock factory project for launch-result checks.",
            repository_path=created_project.repository_path,
            project_type="dashboards_reporting",
            expected_outcome="A created project with a started workflow and inspection path.",
            target_users=["operator"],
            constraints=["test"],
            known_systems=["factory"],
            deadline="today",
            budget_signal="demo",
        ),
        MockFactorySpec(
            name=reused_project.name,
            description="Reuse an existing mock factory project for launch-result checks.",
            repository_path=reused_project.repository_path,
            project_type="dashboards_reporting",
            expected_outcome="A reused project with an existing workflow and waiting signal.",
            target_users=["operator"],
            constraints=["test"],
            known_systems=["factory"],
            deadline="today",
            budget_signal="demo",
        ),
    )
    workflow_by_project = {
        created_project.id: SimpleNamespace(id=uuid.uuid4()),
        reused_project.id: SimpleNamespace(id=uuid.uuid4()),
    }
    existing_workflow = SimpleNamespace(id=workflow_by_project[reused_project.id].id)
    session = PreviewSession([])

    async def existing_project(
        self: MockEnterpriseAutonomyService,
        spec: MockFactorySpec,
    ) -> ProjectModel | None:
        if spec.name == reused_project.name:
            return reused_project
        return None

    async def has_formation_pack(
        self: MockEnterpriseAutonomyService,
        project_value: ProjectModel,
    ) -> bool:
        return project_value.id == reused_project.id

    async def workflow_for_project(
        self: MockEnterpriseAutonomyService,
        project_value: ProjectModel,
    ) -> object | None:
        if project_value.id == reused_project.id:
            return existing_workflow
        return None

    async def create_project(
        self: MockEnterpriseAutonomyService,
        spec: MockFactorySpec,
        *,
        actor_id: str,
    ) -> ProjectModel:
        assert actor_id == "operator"
        return created_project

    async def workflow_start(self: object, *, project_id: uuid.UUID, actor_id: str) -> object:
        assert actor_id == "operator"
        return workflow_by_project[project_id]

    async def noop(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(mock_factory_autonomy, "MOCK_FACTORY_SPECS", specs)
    monkeypatch.setattr(MockEnterpriseAutonomyService, "_existing_project", existing_project)
    monkeypatch.setattr(MockEnterpriseAutonomyService, "_has_formation_pack", has_formation_pack)
    monkeypatch.setattr(
        MockEnterpriseAutonomyService, "_workflow_for_project", workflow_for_project
    )
    monkeypatch.setattr(MockEnterpriseAutonomyService, "_create_project", create_project)
    monkeypatch.setattr(MockEnterpriseAutonomyService, "_create_formation_pack", noop)
    monkeypatch.setattr(MockEnterpriseAutonomyService, "_continue_autonomy", noop)
    monkeypatch.setattr(MockEnterpriseAutonomyService, "_ensure_autonomy_policy", noop)
    monkeypatch.setattr(MockEnterpriseAutonomyService, "_recover_demo_workflow", noop)
    monkeypatch.setattr(mock_factory_autonomy.WorkflowService, "start", workflow_start)
    monkeypatch.setattr(mock_factory_autonomy.WorkflowService, "notify", noop)

    response = await MockEnterpriseAutonomyService(  # type: ignore[arg-type]
        session, object()
    ).start_mock_factory(actor_id="operator")

    assert response.status == "started"
    assert response.created_count == 1
    assert response.reused_count == 1
    assert response.blocked_count == 0
    assert response.failed_count == 0
    assert response.launch_result.review_needed_count == 0
    assert response.launch_result.workflows_started_count == 1
    assert response.launch_result.workflows_waiting_count == 1
    assert response.launch_result.recommended_first_project_id == created_project.id
    assert response.launch_result.recommended_first_project_name == created_project.name
    assert response.launch_result.recommended_first_project_url == (
        f"/dashboard?project={created_project.id}"
    )
    assert response.projects[0].result_category == "created"
    assert response.projects[1].result_category == "reused_workflow_waiting"
    assert response.created == [response.projects[0]]
    assert response.reused == [response.projects[1]]


@pytest.mark.asyncio
async def test_project_formation_pack_requests_missing_information() -> None:
    project_id = uuid.uuid4()
    session = FormationSession(project(project_id))
    request = FormationRequest(
        project_id=project_id,
        idea="Create a live enterprise dashboard that explains project progress clearly.",
    )

    response = await ProjectFormationService(session).create_formation_pack(
        request, actor_id="operator"
    )

    artifacts = [item for item in session.added if isinstance(item, ArtifactModel)]
    audits = [item for item in session.added if isinstance(item, AuditEventModel)]
    assert response.status == "draft_needs_clarification"
    assert "target users" in response.missing_information
    assert response.next_action.startswith("Ask the client")
    assert len(response.artifacts) == 5
    assert len(artifacts) == 5
    assert artifacts[0].artifact_type == ArtifactType.PROJECT_BRIEF
    assert audits[0].event_type == "project_formation.pack_created"
    assert session.committed is True


@pytest.mark.asyncio
async def test_project_formation_pack_ready_for_approval() -> None:
    project_id = uuid.uuid4()
    session = FormationSession(project(project_id))
    request = FormationRequest(
        project_id=project_id,
        idea=(
            "Create a marketing platform dashboard with API integrations, telemetry, "
            "campaign planning, and reusable project blueprints."
        ),
        expected_outcome="A working platform demo with measurable project execution proof.",
        target_users=["client owner", "operator", "developer"],
        constraints=["local development first", "human approval before execution"],
        known_systems=["Git repository", "FastAPI dashboard"],
        deadline="first demo this week",
        budget_signal="reuse existing dashboard and workflow code",
    )

    response = await ProjectFormationService(session).create_formation_pack(
        request, actor_id="operator"
    )

    artifact_types = {item.artifact_type for item in response.artifacts}
    assert response.status == "ready_for_approval"
    assert response.missing_information == []
    assert response.next_action.startswith("Review the formation approval pack")
    assert ArtifactType.SOLUTION_PROPOSAL.value in artifact_types
    assert ArtifactType.FORMATION_APPROVAL_PACK.value in artifact_types
    assert response.traceability["manifest_hash"] == "0" * 64


@pytest.mark.asyncio
async def test_project_foundry_workspace_rejects_incomplete_intake(tmp_path) -> None:
    project_id = uuid.uuid4()
    source_project = project(project_id)
    source_project.repository_path = str(tmp_path / "foundry-project")
    session = FormationSession(source_project)
    settings = Settings(repository_allowed_root=tmp_path)

    with pytest.raises(ProjectFoundryWorkspaceError) as exc:
        await ProjectFoundryWorkspaceService(  # type: ignore[arg-type]
            session, settings
        ).generate_workspace(
            project_id,
            request=_foundry_request({"project": {"target_users": ["operator"]}}),
            actor_id="operator",
        )

    assert "scope section" in exc.value.missing_information
    assert "functional_requirements section" in exc.value.missing_information
    assert "project.expected_outcomes" in exc.value.missing_information
    assert session.committed is False


@pytest.mark.asyncio
async def test_project_foundry_workspace_creates_runtime_repository(tmp_path) -> None:
    project_id = uuid.uuid4()
    source_project = project(project_id)
    workspace = tmp_path / "foundry-project"
    source_project.repository_path = str(workspace)
    session = FormationSession(source_project)
    settings = Settings(repository_allowed_root=tmp_path)

    response = await ProjectFoundryWorkspaceService(  # type: ignore[arg-type]
        session, settings
    ).generate_workspace(
        project_id,
        request=_foundry_request(_complete_intake(), github_repository_url="https://github.com/acme/demo"),
        actor_id="operator",
    )

    assert response.status == "workspace_ready"
    assert response.workspace_path == str(workspace.resolve())
    assert response.github_repository_url == "https://github.com/acme/demo"
    assert response.missing_information == []
    assert "PROJECT.yaml" in response.created_files
    assert "AGENTS.md" in response.created_files
    assert "intake/project-intake.yaml" in response.created_files
    assert "requirements/requirements.yaml" in response.created_files
    assert "governance/authority-policy.yaml" in response.created_files
    assert "planning/execution-plan.yaml" in response.created_files
    assert (workspace / "PROJECT.yaml").exists()
    assert (workspace / "AGENTS.md").exists()
    assert (workspace / "requirements" / "traceability.csv").read_text(
        encoding="utf-8"
    ).startswith("requirement_id,source,status")
    assert "intake_hash:" in (workspace / "PROJECT.yaml").read_text(encoding="utf-8")
    assert source_project.repository_url == "https://github.com/acme/demo"
    assert session.committed is True


@pytest.mark.asyncio
async def test_project_foundry_workspace_reuses_existing_files_without_overwrite(tmp_path) -> None:
    project_id = uuid.uuid4()
    source_project = project(project_id)
    workspace = tmp_path / "foundry-project"
    source_project.repository_path = str(workspace)
    session = FormationSession(source_project)
    settings = Settings(repository_allowed_root=tmp_path)
    existing = workspace / "PROJECT.yaml"
    existing.parent.mkdir(parents=True)
    existing.write_text("custom: keep\n", encoding="utf-8")

    response = await ProjectFoundryWorkspaceService(  # type: ignore[arg-type]
        session, settings
    ).generate_workspace(
        project_id,
        request=_foundry_request(_complete_intake()),
        actor_id="operator",
    )

    assert "PROJECT.yaml" in response.reused_files
    assert existing.read_text(encoding="utf-8") == "custom: keep\n"


def _foundry_request(
    intake: dict,
    *,
    github_repository_url: str | None = None,
):
    from ai_enterprise.api.project_formation_schemas import FoundryWorkspaceRequest

    return FoundryWorkspaceRequest(
        intake=intake,
        github_repository_url=github_repository_url,
    )


def _complete_intake() -> dict:
    return {
        "project": {
            "name": "Demo Foundry Workspace",
            "description": "Create a complete Project Foundry runtime workspace.",
            "business_objective": "Generate a governed project repository from intake.",
            "target_users": ["operator", "client owner"],
            "project_type": "software_factory",
            "expected_outcomes": ["workspace ready", "traceable requirements"],
        },
        "scope": {
            "included": ["workspace generation", "governance files"],
            "excluded": ["production deployment"],
            "assumptions": ["human approval before execution"],
            "dependencies": ["GitHub repository"],
        },
        "functional_requirements": [
            {
                "id": "FR-001",
                "description": "Generate a source-of-truth repository structure.",
                "priority": "critical",
                "acceptance_criteria": ["PROJECT.yaml exists", "AGENTS.md exists"],
            }
        ],
        "non_functional_requirements": {
            "performance": "fast local generation",
            "scalability": "repeatable for many projects",
            "availability": "local-first",
            "security": "path boundary enforced",
            "privacy": "no production secrets in generated files",
            "accessibility": "plain text project files",
            "maintainability": "deterministic files",
        },
        "technical_constraints": {
            "languages": ["Python"],
            "frameworks": ["FastAPI"],
            "operating_systems": ["Linux"],
            "cloud_or_local": "local first",
            "existing_systems": ["AI Enterprise"],
            "prohibited_technologies": ["unapproved production secrets"],
        },
        "delivery": {
            "target_environment": "local",
            "milestones": ["intake", "workspace", "review"],
            "deployment_method": "GitHub collaboration after approval",
            "documentation_required": ["README", "PROJECT.yaml"],
            "support_model": "operator supervised",
        },
        "authority": {
            "allowed_actions": ["create workspace files"],
            "approval_required": ["repository push", "production deployment"],
            "prohibited_actions": ["delete production data"],
            "secret_access_policy": "no secrets in generated workspace",
            "production_access_policy": "human approval required",
        },
    }
