from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from ai_enterprise.config import Settings
from ai_enterprise.main import health, readiness, root


def repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "apps/api/Dockerfile").exists() and (
            candidate / "docker-compose.yml"
        ).exists():
            return candidate
    raise AssertionError("Repository root was not found")


@pytest.mark.asyncio
async def test_root_and_liveness_contracts() -> None:
    root_payload = await root()
    live = await health()
    assert root_payload["status"] == "running"
    assert root_payload["version"] == "0.1.0"
    assert live["database"] == "not_checked"


@pytest.mark.asyncio
async def test_readiness_checks_database() -> None:
    session = AsyncMock()
    context = AsyncMock()
    context.__aenter__.return_value = session
    with patch("ai_enterprise.main.SessionFactory", return_value=context):
        response = await readiness()
    assert response["database"] == "reachable"
    session.execute.assert_awaited_once()


def test_settings_validate_api_and_pool_bounds() -> None:
    settings = Settings(api_port=9000, database_pool_size=2, database_max_overflow=0)
    assert settings.api_port == 9000
    assert settings.app_version == "0.1.0"


def test_container_foundation_is_non_root_and_read_only() -> None:
    root = repo_root()
    dockerfile = (root / "apps/api/Dockerfile").read_text(encoding="utf-8")
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    assert "USER appuser" in dockerfile
    assert "--uid 10001" in dockerfile
    assert "read_only: true" in compose
    assert "condition: service_completed_successfully" in compose
    assert "127.0.0.1:8000:8000" in compose
    assert "127.0.0.1:5432:5432" in compose
    assert 'ARG UV_SYNC_ARGS="--no-dev"' in dockerfile
    assert "uv sync --frozen ${UV_SYNC_ARGS}" in dockerfile
    assert (
        "COPY docker-compose.server.example.yml /app/docker-compose.server.example.yml"
        in dockerfile
    )
    assert (
        "COPY docker-compose.observability.yml /app/docker-compose.observability.yml"
        in dockerfile
    )
    assert "COPY .env.server.example /app/.env.server.example" in dockerfile
    assert "COPY tools/backup_verify.py /app/tools/backup_verify.py" in dockerfile
    assert (
        "COPY tools/generate_server_secrets.py /app/tools/generate_server_secrets.py"
        in dockerfile
    )
    assert "COPY tools/sign_proxy_assertion.py /app/tools/sign_proxy_assertion.py" in dockerfile
    assert "COPY tools/model_endpoint_verify.py /app/tools/model_endpoint_verify.py" in dockerfile
    assert "COPY tools/deployment_blueprint.py /app/tools/deployment_blueprint.py" in dockerfile
    assert "COPY tools/infrastructure_choices.py /app/tools/infrastructure_choices.py" in dockerfile
    assert "COPY deploy/systemd /app/deploy/systemd" in dockerfile
    assert "COPY deploy/kubernetes /app/deploy/kubernetes" in dockerfile
    assert (
        "COPY docs/enterprise/deployment-blueprint-module.md "
        "/app/docs/enterprise/deployment-blueprint-module.md"
    ) in dockerfile
    assert (
        "COPY docs/enterprise/real-world-infrastructure-decisions.template.json "
        "/app/docs/enterprise/real-world-infrastructure-decisions.template.json"
    ) in dockerfile
    assert (
        "COPY examples/sample-project/aepm-0.1.json "
        "/app/examples/sample-project/aepm-0.1.json"
    ) in dockerfile


def test_server_compose_profile_removes_laptop_only_runtime_assumptions() -> None:
    root = repo_root()
    server_compose = (root / "docker-compose.server.example.yml").read_text(
        encoding="utf-8"
    )
    server_env = (root / ".env.server.example").read_text(encoding="utf-8")

    assert "DATABASE_URL: ${DATABASE_URL:?set DATABASE_URL}" in server_compose
    assert "POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}" in server_compose
    assert "host.docker.internal" not in server_compose
    assert "/home/user/projects" not in server_compose
    assert "127.0.0.1:5432:5432" not in server_compose
    assert (
        "${AI_ENTERPRISE_WORKSPACE_ROOT:?set AI_ENTERPRISE_WORKSPACE_ROOT}:/workspaces"
        in server_compose
    )
    assert "TRUSTED_PROXY_HMAC_SECRET=change-me-with-a-long-random-secret" in server_env
    assert "REPOSITORY_ALLOWED_ROOT=/srv/ai-enterprise/workspaces" in server_env


def test_test_compose_profile_installs_dev_dependencies() -> None:
    root = repo_root()
    test_compose = (root / "docker-compose.test.yml").read_text(encoding="utf-8")
    makefile = (root / "Makefile").read_text(encoding="utf-8")

    assert "api-test:" in test_compose
    assert 'UV_SYNC_ARGS: ""' in test_compose
    assert 'command: ["pytest", "-q", "apps/api/tests"]' in test_compose
    assert "./apps:/app/apps:ro" in test_compose
    assert "./templates:/app/templates:ro" in test_compose
    assert "docker-test:" in makefile


def test_local_executor_worker_targets_use_project_venv() -> None:
    root = repo_root()
    makefile = (root / "Makefile").read_text(encoding="utf-8")

    assert "local-executor-check:" in makefile
    assert (
        "apps/api/.venv/bin/python tools/local_executor_worker.py --json" in makefile
    )
    assert "local-executor-worker:" in makefile
    assert (
        "apps/api/.venv/bin/python tools/local_executor_worker.py --run" in makefile
    )


def test_broker_agent_images_use_pinned_reproducible_inputs() -> None:
    root = repo_root()
    requirements = (root / "docker/agent-runtime-requirements.txt").read_text(
        encoding="utf-8"
    )
    dockerfiles = [
        root / "docker/execution-agent/Dockerfile",
        root / "docker/review-agent/Dockerfile",
    ]

    for dockerfile_path in dockerfiles:
        dockerfile = dockerfile_path.read_text(encoding="utf-8")
        assert (
            "FROM python:3.12.11-slim-bookworm@sha256:"
            "519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7"
        ) in dockerfile
        assert "pip install --upgrade pip" not in dockerfile
        assert "pip install pytest==" not in dockerfile
        assert "python -m pip install --require-hashes --no-deps" in dockerfile
        assert "COPY docker/agent-runtime-requirements.txt" in dockerfile
        assert "ARG BASH_VERSION=5.2.15-2+b13" in dockerfile
        assert "ARG CA_CERTIFICATES_VERSION=20230311+deb12u1" in dockerfile
        assert "ARG GIT_VERSION=1:2.39.5-0+deb12u3" in dockerfile
        assert "ARG NODEJS_VERSION=18.20.4+dfsg-1~deb12u2" in dockerfile
        assert "ARG NPM_VERSION=9.2.0~ds1-1" in dockerfile
        assert "ARG PATCH_VERSION=2.7.6-7" in dockerfile
        assert '"bash=${BASH_VERSION}"' in dockerfile
        assert '"ca-certificates=${CA_CERTIFICATES_VERSION}"' in dockerfile
        assert '"git=${GIT_VERSION}"' in dockerfile
        assert '"nodejs=${NODEJS_VERSION}"' in dockerfile
        assert '"npm=${NPM_VERSION}"' in dockerfile
        assert '"patch=${PATCH_VERSION}"' in dockerfile

    assert "pytest==8.3.4" in requirements
    assert requirements.count("--hash=sha256:") == 4


def test_server_operations_artifacts_cover_later_phase_gaps() -> None:
    root = repo_root()
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    observability = (root / "docker-compose.observability.yml").read_text(
        encoding="utf-8"
    )
    prometheus = (root / "docker/observability/prometheus.yml").read_text(
        encoding="utf-8"
    )
    nginx = (root / "docker/reverse-proxy/nginx.conf.example").read_text(
        encoding="utf-8"
    )

    assert "backup-verify:" in makefile
    assert "server-secrets:" in makefile
    assert "model-verify:" in makefile
    assert "deployment-blueprint:" in makefile
    assert "infrastructure-choices-template:" in makefile
    assert "infrastructure-choices-verify:" in makefile
    assert "observability-check:" in makefile
    assert "prom/prometheus" in observability
    assert "grafana/grafana" in observability
    assert "alert_rules.yml" in observability
    assert "metrics_path: /metrics" in prometheus
    assert "rule_files:" in prometheus
    assert "listen 443 ssl" in nginx
    assert "X-Proxy-Signature" in nginx
    assert (root / "docker/observability/alert_rules.yml").exists()
    assert (root / "tools/deployment_blueprint.py").exists()
    assert (root / "tools/infrastructure_choices.py").exists()
    assert (root / "docs/enterprise/deployment-blueprint-module.md").exists()
    assert (
        root / "docs/enterprise/real-world-infrastructure-decisions.template.json"
    ).exists()
    assert (root / "deploy/systemd/ai-enterprise-backup.timer").exists()
    assert (root / "deploy/systemd/ai-enterprise-backup.service").exists()
    assert (root / "deploy/kubernetes/api-deployment.yaml").exists()
    assert (root / "deploy/kubernetes/worker-deployment.yaml").exists()


def test_platform_metadata_migration_is_reversible_and_linear() -> None:
    root = repo_root()
    migration = (
        root / "migrations/versions/b94e10d3f721_add_platform_metadata_foundation.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "a67c9e12b4d8"' in migration
    assert 'op.create_table(\n        "platform_metadata"' in migration
    assert 'op.drop_table("platform_metadata")' in migration
