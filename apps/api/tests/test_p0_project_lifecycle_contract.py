import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from ai_enterprise.api.dependencies import Actor
from ai_enterprise.api.routes.projects import get_project
from ai_enterprise.application.project_workflow import ProjectWorkflowService
from ai_enterprise.domain.enums import ProjectStatus
from ai_enterprise.domain.hashing import canonical_json, hash_json
from ai_enterprise.infrastructure.audit.event_hasher import verify_chain_records
from ai_enterprise.infrastructure.database.foundation_models import AuditChainRecordModel
from ai_enterprise.infrastructure.database.models import (
    ArtifactModel,
    AuditEventModel,
    CrewRunModel,
    JobModel,
    ProjectModel,
)
from ai_enterprise.infrastructure.repositories.preparation import prepare_project_repository


class Session:
    def __init__(self, row: Any = None) -> None:
        self.row = row

    async def get(self, model: type, identity: uuid.UUID) -> Any:
        return self.row


class WriteSession:
    def __init__(self, row: Any = None) -> None:
        self.row = row
        self.added: list[Any] = []
        self.flushed = False
        self.committed = False

    def add(self, row: Any) -> None:
        self.added.append(row)

    def add_all(self, rows: list[Any]) -> None:
        self.added.extend(rows)

    async def scalar(self, statement: object) -> Any:
        chain_records = [row for row in self.added if isinstance(row, AuditChainRecordModel)]
        return chain_records[-1] if chain_records else None

    async def execute(self, statement: object) -> Any:
        return SimpleNamespace(scalar_one_or_none=lambda: self.row)

    async def flush(self) -> None:
        self.flushed = True

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, row: Any) -> None:
        return None


def project_reader(project_id: uuid.UUID) -> Actor:
    return Actor(
        "reader",
        "human",
        "operator",
        frozenset({"project.read"}),
        scopes=frozenset({f"project:{project_id}"}),
    )


def service_project_reader(project_id: uuid.UUID) -> Actor:
    return Actor(
        "project-service",
        "service",
        "operator",
        frozenset({"project.read"}),
        scopes=frozenset({f"project:{project_id}"}),
    )


@pytest.mark.asyncio
async def test_get_project_returns_current_p0_lifecycle_state() -> None:
    now = datetime.now(UTC)
    project_id = uuid.uuid4()
    manifest = {
        "schema_version": "1.0",
        "project_id": str(project_id),
        "name": "P0 Lifecycle",
        "description": "Project created from the P0 lifecycle contract.",
    }
    project = ProjectModel(
        id=project_id,
        name="P0 Lifecycle",
        description="Project created from the P0 lifecycle contract.",
        repository_path="/home/user/projects/p0-lifecycle",
        repository_url=None,
        default_branch="main",
        status=ProjectStatus.AWAITING_REQUIREMENTS_APPROVAL,
        manifest_hash=hash_json(manifest),
        manifest=manifest,
        created_at=now,
        updated_at=now,
    )

    response = await get_project(
        project_id,
        Session(project),  # type: ignore[arg-type]
        project_reader(project_id),
    )

    assert response.id == project_id
    assert response.status == ProjectStatus.AWAITING_REQUIREMENTS_APPROVAL
    assert response.manifest_hash == hash_json(manifest)


@pytest.mark.asyncio
async def test_get_project_returns_404_for_unknown_project() -> None:
    with pytest.raises(HTTPException) as exc:
        project_id = uuid.uuid4()
        await get_project(
            project_id,
            Session(),  # type: ignore[arg-type]
            project_reader(project_id),
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Project not found"


@pytest.mark.asyncio
async def test_get_project_rejects_wrong_project_scope() -> None:
    project_id = uuid.uuid4()
    project = ProjectModel(
        id=project_id,
        name="Scoped Project",
        description="Project protected by project-scoped authority.",
        repository_path="/home/user/projects/scoped-project",
        repository_url=None,
        default_branch="main",
        status=ProjectStatus.CREATED,
        manifest_hash="0" * 64,
        manifest={},
    )
    denied = project_reader(uuid.uuid4())

    with pytest.raises(HTTPException) as exc:
        await get_project(project_id, Session(project), denied)  # type: ignore[arg-type]

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_get_project_requires_human_actor() -> None:
    project_id = uuid.uuid4()
    project = ProjectModel(
        id=project_id,
        name="Human Project Read",
        description="Project protected from service actor reads.",
        repository_path="/home/user/projects/human-project-read",
        repository_url=None,
        default_branch="main",
        status=ProjectStatus.CREATED,
        manifest_hash="0" * 64,
        manifest={},
    )

    with pytest.raises(HTTPException) as exc:
        await get_project(
            project_id,
            Session(project),  # type: ignore[arg-type]
            service_project_reader(project_id),
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Human project authority is required"


def test_p0_manifest_content_is_canonical_json_not_python_repr() -> None:
    manifest = {"b": 2, "a": {"created_by": "local-user"}}

    content = canonical_json(manifest)

    assert content == '{"a":{"created_by":"local-user"},"b":2}'
    assert "'" not in content
    assert hash_json(manifest) == hash_json({"a": {"created_by": "local-user"}, "b": 2})


@pytest.mark.asyncio
async def test_create_project_persists_uploaded_manifest_content(tmp_path) -> None:
    session = WriteSession()
    uploaded_manifest = {
        "schema_version": "1.0",
        "client": "Example Client",
        "project_type": "dashboards_reporting",
        "constraints": ["EU data residency", "all changes through pull requests"],
    }
    repository_path = tmp_path / "manifest-project"
    service = ProjectWorkflowService(
        session=session,
        settings=SimpleNamespace(repository_allowed_root=tmp_path),  # type: ignore[arg-type]
    )

    project = await service.create_project(
        name="Manifest Project",
        description="A project created from an uploaded manifesto.",
        repository_path=str(repository_path),
        repository_url=None,
        default_branch="main",
        actor_id="local-user",
        manifest=uploaded_manifest,
        project_type="dashboards_reporting",
    )

    manifest_artifact = next(row for row in session.added if isinstance(row, ArtifactModel))
    audit_event = next(row for row in session.added if isinstance(row, AuditEventModel))
    chain_record = next(row for row in session.added if isinstance(row, AuditChainRecordModel))

    assert session.flushed and session.committed
    assert project.manifest["client"] == "Example Client"
    assert project.manifest["constraints"] == [
        "EU data residency",
        "all changes through pull requests",
    ]
    assert project.manifest["project_type"] == "dashboards_reporting"
    assert project.manifest["project_id"] == str(project.id)
    assert project.manifest["repository_preparation"]["head_ready"] is True
    assert manifest_artifact.content == canonical_json(project.manifest)
    assert manifest_artifact.content_hash == hash_json(project.manifest)
    assert audit_event.event_type == "project.created"
    assert audit_event.payload["audit_chain"]["sequence"] == 1
    assert chain_record.stream_id == f"project:{project.id}"
    assert chain_record.payload["event_type"] == "project.created"
    assert chain_record.payload["payload"]["manifest_hash"] == project.manifest_hash


@pytest.mark.asyncio
async def test_queue_requirements_run_writes_tamper_evident_audit_chain(tmp_path) -> None:
    project_id = uuid.uuid4()
    manifest = {
        "schema_version": "1.0",
        "project_id": str(project_id),
        "name": "Queued Project",
    }
    project = ProjectModel(
        id=project_id,
        name="Queued Project",
        description="Project queued for requirements.",
        repository_path=str(tmp_path / "queued-project"),
        repository_url=None,
        default_branch="main",
        status=ProjectStatus.CREATED,
        manifest_hash=hash_json(manifest),
        manifest=manifest,
    )
    session = WriteSession(project)
    service = ProjectWorkflowService(
        session=session,
        settings=SimpleNamespace(repository_allowed_root=tmp_path),  # type: ignore[arg-type]
    )

    run = await service.queue_requirements_run(project_id=project_id, actor_id="local-user")

    audit_event = next(
        row
        for row in session.added
        if isinstance(row, AuditEventModel) and row.event_type == "requirements.run.queued"
    )
    chain_record = next(row for row in session.added if isinstance(row, AuditChainRecordModel))
    job = next(row for row in session.added if isinstance(row, JobModel))

    assert session.flushed and session.committed
    assert isinstance(run, CrewRunModel)
    assert project.status == ProjectStatus.REQUIREMENTS_QUEUED
    assert audit_event.payload["audit_chain"]["sequence"] == 1
    assert audit_event.payload["audit_chain"]["record_hash"] == chain_record.record_hash
    assert chain_record.stream_id == f"project:{project_id}"
    assert chain_record.payload["event_type"] == "requirements.run.queued"
    assert chain_record.payload["payload"]["job_id"] == str(job.id)
    assert (
        verify_chain_records(
            [
                {
                    "stream_id": chain_record.stream_id,
                    "sequence": chain_record.sequence,
                    "previous_hash": chain_record.previous_hash,
                    "record_hash": chain_record.record_hash,
                    "payload": chain_record.payload,
                }
            ]
        )
        == []
    )


def test_prepare_project_repository_initializes_git_head(tmp_path) -> None:
    repository_path = tmp_path / "prepared-project"

    result = prepare_project_repository(
        str(repository_path),
        "main",
        allowed_root=tmp_path,
    )

    assert result["initialized"] is True
    assert result["initial_commit_created"] is True
    assert result["head_ready"] is True
    assert (repository_path / ".git").exists()
