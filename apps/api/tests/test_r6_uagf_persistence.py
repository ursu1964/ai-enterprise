from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from ai_enterprise.api.routes import r6_uagf as r6_routes
from ai_enterprise.domain.r6_uagf import UagfArtifactRepositoryKind
from ai_enterprise.infrastructure.knowledge.models import (
    R6ArtifactRepositoryPublicationModel,
    R6GeneratedFileModel,
    R6GenerationBuildModel,
    R6InstalledGeneratorPackModel,
    R6LifecycleEventModel,
    R6ParallelGenerationPlanModel,
    R6ValidationGateRunModel,
    R6ValidationReportModel,
)
from ai_enterprise.main import app

ROOT = Path(__file__).resolve().parents[3]


def _has_unique_constraint(model: type, *columns: str) -> bool:
    expected = set(columns)
    return any(
        getattr(constraint, "columns", None) is not None
        and {column.name for column in constraint.columns} == expected
        for constraint in model.__table__.constraints
    )


def test_r6_storage_models_cover_builds_files_and_validation_reports() -> None:
    assert R6GenerationBuildModel.__table__.c.manifest_document.type.__class__.__name__ == "JSONB"
    assert R6GenerationBuildModel.__table__.c.r5_export_bundle_id.foreign_keys
    assert _has_unique_constraint(
        R6GenerationBuildModel,
        "r5_export_bundle_id",
        "generator_pack_id",
        "generator_pack_version",
    )
    assert _has_unique_constraint(R6GenerationBuildModel, "project_id", "build_hash")

    assert R6GeneratedFileModel.__table__.c.file_document.type.__class__.__name__ == "JSONB"
    assert R6GeneratedFileModel.__table__.c.generation_build_id.foreign_keys
    assert _has_unique_constraint(R6GeneratedFileModel, "generation_build_id", "relative_path")
    assert _has_unique_constraint(R6GeneratedFileModel, "project_id", "file_hash")

    assert R6ValidationReportModel.__table__.c.report_document.type.__class__.__name__ == "JSONB"
    assert R6ValidationReportModel.__table__.c.report_hash.unique
    assert _has_unique_constraint(R6ValidationReportModel, "generation_build_id")

    assert R6LifecycleEventModel.__table__.c.policy_document.type.__class__.__name__ == "JSONB"
    assert R6LifecycleEventModel.__table__.c.generation_build_id.foreign_keys
    assert _has_unique_constraint(R6LifecycleEventModel, "generation_build_id", "event_id")
    assert _has_unique_constraint(R6LifecycleEventModel, "project_id", "event_hash")

    assert R6InstalledGeneratorPackModel.__table__.c.pack_document.type.__class__.__name__ == (
        "JSONB"
    )
    assert R6InstalledGeneratorPackModel.__table__.c.project_id.foreign_keys
    assert _has_unique_constraint(
        R6InstalledGeneratorPackModel, "project_id", "pack_id", "version"
    )

    assert R6ParallelGenerationPlanModel.__table__.c.plan_document.type.__class__.__name__ == (
        "JSONB"
    )
    assert R6ParallelGenerationPlanModel.__table__.c.generation_build_id.foreign_keys
    assert _has_unique_constraint(
        R6ParallelGenerationPlanModel, "generation_build_id", "plan_id"
    )

    assert R6ValidationGateRunModel.__table__.c.gate_document.type.__class__.__name__ == "JSONB"
    assert R6ValidationGateRunModel.__table__.c.generation_build_id.foreign_keys
    assert _has_unique_constraint(R6ValidationGateRunModel, "generation_build_id", "gate_run_id")

    assert (
        R6ArtifactRepositoryPublicationModel.__table__.c.publication_document.type.__class__.__name__
        == "JSONB"
    )
    assert R6ArtifactRepositoryPublicationModel.__table__.c.generation_build_id.foreign_keys
    assert _has_unique_constraint(
        R6ArtifactRepositoryPublicationModel, "generation_build_id", "publication_id"
    )


def test_r6_migration_is_linear_and_declares_append_only_generation_records() -> None:
    migration = (
        ROOT / "migrations/versions/6a2b8c9d1e5f_add_r6_uagf_records.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: str | None = "5e1a9c8d2f4b"' in migration
    for table in (
        "r6_generation_builds",
        "r6_generated_files",
        "r6_validation_reports",
    ):
        assert f'"{table}"' in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "postgresql.JSONB" in migration

    lifecycle_migration = (
        ROOT / "migrations/versions/7c4e2a9b8d1f_add_r6_lifecycle_events.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: str | None = "6a2b8c9d1e5f"' in lifecycle_migration
    assert '"r6_lifecycle_events"' in lifecycle_migration
    assert "BEFORE UPDATE OR DELETE" in lifecycle_migration
    assert "postgresql.JSONB" in lifecycle_migration

    factory_migration = (
        ROOT / "migrations/versions/c8d3e7f1a9b2_add_r6_production_factory_layer.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: str | None = "b7c2d9e4f1a6"' in factory_migration
    assert "uq_r6_generation_builds_bundle_pack_version" in factory_migration
    for table in (
        "r6_installed_generator_packs",
        "r6_parallel_generation_plans",
        "r6_validation_gate_runs",
        "r6_artifact_repository_publications",
    ):
        assert f'"{table}"' in factory_migration
    assert "BEFORE UPDATE OR DELETE" in factory_migration
    assert "postgresql.JSONB" in factory_migration


def test_r6_uagf_routes_are_exposed_in_openapi() -> None:
    paths = TestClient(app).get("/openapi.json").json()["paths"]

    assert "/api/v1/projects/{project_id}/uagf/builds" in paths
    assert "/api/v1/projects/{project_id}/uagf/builds/{build_id}" in paths
    assert (
        "/api/v1/projects/{project_id}/uagf/builds/from-r5-export-bundle/{bundle_id}"
        in paths
    )
    assert (
        "/api/v1/projects/{project_id}/uagf/regeneration-plans/from-r5-export-bundle/{bundle_id}"
        in paths
    )
    assert "/api/v1/projects/{project_id}/uagf/builds/{build_id}/lifecycle/events" in paths
    assert (
        "/api/v1/projects/{project_id}/uagf/builds/{build_id}/lifecycle/transitions"
        in paths
    )
    assert "/api/v1/projects/{project_id}/uagf/generator-packs/marketplace" in paths
    assert "/api/v1/projects/{project_id}/uagf/generator-packs/installations" in paths
    assert (
        "/api/v1/projects/{project_id}/uagf/builds/{build_id}/parallel-generation-plans"
        in paths
    )
    assert "/api/v1/projects/{project_id}/uagf/builds/{build_id}/validation-gates" in paths
    assert (
        "/api/v1/projects/{project_id}/uagf/builds/{build_id}/artifact-repository-publications"
        in paths
    )
    assert "/api/v1/projects/{project_id}/uagf/artifact-repositories/readiness" in paths
    assert (
        paths[
            "/api/v1/projects/{project_id}/uagf/builds/from-r5-export-bundle/{bundle_id}"
        ]["post"]["tags"]
        == ["r6-uagf"]
    )


def test_r6_uagf_git_repository_publication_pushes_real_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if shutil.which("git") is None:
        pytest.skip("git executable is required for real Git publication test")
    artifact_root = tmp_path / "artifacts"
    source_root = tmp_path / "source-build"
    source_root.mkdir()
    (source_root / "generated.json").write_text('{"ok": true}\n', encoding="utf-8")
    remote = tmp_path / "remote.git"
    subprocess.run(("git", "init", "--bare", str(remote)), check=True, capture_output=True)
    monkeypatch.setattr(
        r6_routes,
        "get_settings",
        lambda: SimpleNamespace(artifact_root=artifact_root),
    )
    build = SimpleNamespace(root_path=str(source_root), build_hash="a" * 64)

    repository_ref = r6_routes._materialize_repository_publication(
        project_id=uuid.uuid4(),
        build=build,
        repository_kind=UagfArtifactRepositoryKind.GIT,
        repository_ref=str(remote),
        version_ref="1.2.3",
    )

    assert repository_ref == str(remote)
    checkout = tmp_path / "checkout"
    subprocess.run(("git", "clone", str(remote), str(checkout)), check=True, capture_output=True)
    assert (checkout / "generated.json").read_text(encoding="utf-8") == '{"ok": true}\n'
    tag = subprocess.run(
        ("git", "--git-dir", str(remote), "rev-parse", "refs/tags/uagf-1.2.3"),
        check=True,
        capture_output=True,
        text=True,
    )
    assert tag.stdout.strip()


def test_r6_uagf_s3_publication_requires_real_backend_without_adapter_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_root = tmp_path / "artifacts"
    source_root = tmp_path / "source-build"
    source_root.mkdir()
    (source_root / "generated.json").write_text('{"ok": true}\n', encoding="utf-8")
    monkeypatch.setattr(
        r6_routes,
        "get_settings",
        lambda: SimpleNamespace(artifact_root=artifact_root),
    )
    monkeypatch.setattr(r6_routes.shutil, "which", lambda name: None if name == "aws" else name)
    build = SimpleNamespace(root_path=str(source_root), build_hash="a" * 64)

    with pytest.raises(HTTPException, match="AWS CLI is not installed"):
        r6_routes._materialize_repository_publication(
            project_id=uuid.uuid4(),
            build=build,
            repository_kind=UagfArtifactRepositoryKind.S3,
            repository_ref="s3://example-bucket/uagf",
            version_ref="1.2.3",
        )

    assert not (artifact_root / "r6-repositories").exists()


def test_r6_uagf_artifact_repository_readiness_reports_missing_s3_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_WEB_IDENTITY_TOKEN_FILE", raising=False)
    monkeypatch.delenv("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI", raising=False)
    monkeypatch.setattr(r6_routes.shutil, "which", lambda name: None if name == "aws" else name)
    monkeypatch.setattr(
        r6_routes,
        "get_settings",
        lambda: SimpleNamespace(
            artifact_root=tmp_path / "artifacts",
            r6_publication_aws_profile=None,
            r6_publication_aws_region=None,
        ),
    )

    report = r6_routes._artifact_repository_readiness(
        UagfArtifactRepositoryKind.S3,
        "s3://example-bucket/uagf",
    )

    assert report["ready"] is False
    checks = {item["name"]: item for item in report["checks"]}
    assert checks["aws_cli"]["ok"] is False
    assert checks["aws_credentials"]["ok"] is False
    assert "AWS credentials with s3:ListBucket/s3:PutObject" in report[
        "required_configuration"
    ]


def test_r6_uagf_artifact_repository_readiness_accepts_npm_token_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NPM_TOKEN", "token-value")
    monkeypatch.setattr(r6_routes.shutil, "which", lambda name: "/usr/bin/npm")
    monkeypatch.setattr(
        r6_routes,
        "_probe_npm_registry",
        lambda repository_ref: (True, f"identity verified for {repository_ref}"),
    )
    monkeypatch.setattr(
        r6_routes,
        "get_settings",
        lambda: SimpleNamespace(
            artifact_root=tmp_path / "artifacts",
            r6_publication_npm_token=None,
            r6_publication_npmrc_path=None,
        ),
    )

    report = r6_routes._artifact_repository_readiness(
        UagfArtifactRepositoryKind.PACKAGE_REGISTRY,
        "https://registry.example.test",
    )

    checks = {item["name"]: item for item in report["checks"]}
    assert checks["npm_executable"]["ok"] is True
    assert checks["npm_auth"]["ok"] is True
    assert checks["npm_registry_identity"]["ok"] is True


def test_r6_uagf_s3_readiness_runs_identity_and_repository_probes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(r6_routes.shutil, "which", lambda name: "/usr/bin/aws")

    def probe(
        command: tuple[str, ...],
        *,
        timeout: int,
        env: dict[str, str] | None = None,
    ) -> tuple[bool, str]:
        calls.append(command)
        assert timeout == 20
        assert env is not None
        return True, "probe passed"

    monkeypatch.setattr(r6_routes, "_probe_command", probe)
    monkeypatch.setattr(
        r6_routes,
        "get_settings",
        lambda: SimpleNamespace(
            artifact_root=tmp_path / "artifacts",
            r6_publication_aws_profile="prod",
            r6_publication_aws_region="eu-central-1",
            r6_publication_git_ssh_config_path=None,
        ),
    )

    report = r6_routes._artifact_repository_readiness(
        UagfArtifactRepositoryKind.S3,
        "s3://example-bucket/uagf",
    )

    checks = {item["name"]: item for item in report["checks"]}
    assert report["ready"] is True
    assert checks["aws_identity"]["ok"] is True
    assert checks["s3_repository_access"]["ok"] is True
    assert (
        "aws",
        "sts",
        "get-caller-identity",
        "--profile",
        "prod",
        "--region",
        "eu-central-1",
    ) in calls
    assert (
        "aws",
        "s3",
        "ls",
        "s3://example-bucket/uagf",
        "--profile",
        "prod",
        "--region",
        "eu-central-1",
    ) in calls
