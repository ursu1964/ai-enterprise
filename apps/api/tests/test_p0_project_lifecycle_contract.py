import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from ai_enterprise.api.routes.projects import get_project
from ai_enterprise.application.project_workflow import ProjectWorkflowService
from ai_enterprise.domain.enums import ProjectStatus
from ai_enterprise.domain.hashing import canonical_json, hash_json
from ai_enterprise.infrastructure.database.foundation_models import AuditChainRecordModel
from ai_enterprise.infrastructure.database.models import (
    ArtifactModel,
    AuditEventModel,
    ProjectModel,
)
from ai_enterprise.infrastructure.repositories.preparation import prepare_project_repository


class Session:
    def __init__(self, row: Any = None) -> None:
        self.row = row

    async def get(self, model: type, identity: uuid.UUID) -> Any:
        return self.row


class WriteSession:
    def __init__(self) -> None:
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

    async def flush(self) -> None:
        self.flushed = True

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, row: Any) -> None:
        return None


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

    response = await get_project(project_id, Session(project))  # type: ignore[arg-type]

    assert response.id == project_id
    assert response.status == ProjectStatus.AWAITING_REQUIREMENTS_APPROVAL
    assert response.manifest_hash == hash_json(manifest)


@pytest.mark.asyncio
async def test_get_project_returns_404_for_unknown_project() -> None:
    with pytest.raises(HTTPException) as exc:
        await get_project(uuid.uuid4(), Session())  # type: ignore[arg-type]

    assert exc.value.status_code == 404
    assert exc.value.detail == "Project not found"


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
