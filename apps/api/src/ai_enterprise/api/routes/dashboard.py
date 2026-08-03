"""API-hosted operator dashboard."""

# ruff: noqa: E501

import importlib.util
import uuid
from pathlib import Path
from typing import Any, TypedDict

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from sqlalchemy import select

from ai_enterprise.api.dependencies import SessionDependency
from ai_enterprise.application.operator_job_resolution import (
    job_is_acknowledged,
    unresolved_problem_jobs,
)
from ai_enterprise.config import get_settings
from ai_enterprise.infrastructure.database.models import JobModel, ProjectModel
from ai_enterprise.infrastructure.organization.models import OrganizationModel
from ai_enterprise.infrastructure.performance.models import PerformanceMetricModel

router = APIRouter(tags=["dashboard"])

GRAPHIFY_HTML = Path("/app/graphify-out/graph.html")


class OperatorDocument(TypedDict):
    path: Path
    filename: str


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "docs/enterprise").exists() and (candidate / "tools").exists():
            return candidate
    return Path.cwd()


def _repo_path(path: str) -> Path:
    return _repo_root() / path


def _load_tool_function(module_name: str, function_name: str) -> Any:
    module_path = _repo_path(f"tools/{module_name}.py")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise HTTPException(status_code=503, detail=f"{module_name} tool is not available")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, function_name)


OPERATOR_DOCUMENT_FILES: dict[str, OperatorDocument] = {
    "operator-startup-guide": {
        "path": _repo_path("docs/enterprise/operator-startup-guide.md"),
        "filename": "operator-startup-guide.md",
    },
    "project-execution-walkthrough": {
        "path": _repo_path("docs/enterprise/project-execution-walkthrough.md"),
        "filename": "project-execution-walkthrough.md",
    },
    "working-method": {
        "path": _repo_path("docs/enterprise/working-method.md"),
        "filename": "working-method.md",
    },
    "real-world-infrastructure-choices": {
        "path": _repo_path("docs/enterprise/real-world-infrastructure-choices.md"),
        "filename": "real-world-infrastructure-choices.md",
    },
}


def _markdown_response(
    content: str, *, filename: str, download: bool = False
) -> PlainTextResponse:
    headers = (
        {"Content-Disposition": f'attachment; filename="{filename}"'}
        if download
        else None
    )
    return PlainTextResponse(
        content,
        media_type="text/markdown; charset=utf-8",
        headers=headers,
    )


@router.get("/dashboard", response_class=HTMLResponse)
async def enterprise_dashboard() -> HTMLResponse:
    return HTMLResponse(DASHBOARD_HTML)


@router.get("/dashboard/demo", response_class=HTMLResponse)
async def enterprise_demo() -> HTMLResponse:
    return HTMLResponse(DEMO_HTML)


@router.get("/dashboard/documentation-hub", response_class=HTMLResponse)
async def documentation_hub() -> HTMLResponse:
    return HTMLResponse(DOCUMENTATION_HUB_HTML)


@router.get("/dashboard/client-manifest-template", response_class=PlainTextResponse)
async def client_manifest_template() -> PlainTextResponse:
    return _markdown_response(
        CLIENT_MANIFEST_TEMPLATE,
        filename="ai-enterprise-client-project-manifest.md",
        download=True,
    )


@router.get("/dashboard/project-foundry-core", response_class=PlainTextResponse)
async def project_foundry_core() -> PlainTextResponse:
    return _markdown_response(
        PROJECT_FOUNDRY_CORE_DOWNLOAD,
        filename="project-foundry-core-v0.1.md",
        download=True,
    )


@router.get("/dashboard/documentation/{document_id}", response_class=PlainTextResponse)
async def dashboard_documentation_document(
    document_id: str, download: bool = False
) -> PlainTextResponse:
    if document_id == "client-manifest-template":
        return _markdown_response(
            CLIENT_MANIFEST_TEMPLATE,
            filename="ai-enterprise-client-project-manifest.md",
            download=download,
        )
    if document_id == "project-foundry-core":
        return _markdown_response(
            PROJECT_FOUNDRY_CORE_DOWNLOAD,
            filename="project-foundry-core-v0.1.md",
            download=download,
        )
    document = OPERATOR_DOCUMENT_FILES.get(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Operator document is not registered")
    path = document["path"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Operator document is not available")
    return _markdown_response(
        path.read_text(encoding="utf-8"),
        filename=document["filename"],
        download=download,
    )


@router.get("/dashboard/graphify", response_class=FileResponse)
async def graphify_dashboard() -> FileResponse:
    if not GRAPHIFY_HTML.exists():
        raise HTTPException(status_code=404, detail="Graphify dashboard is not mounted")
    return FileResponse(GRAPHIFY_HTML, media_type="text/html")


@router.get("/dashboard/context")
async def dashboard_context(session: SessionDependency) -> dict[str, object]:
    settings = get_settings()
    if settings.app_env.lower() in {"production", "staging"}:
        raise HTTPException(
            status_code=403,
            detail="Local dashboard context is disabled outside development.",
        )
    organization = await session.scalar(select(OrganizationModel).order_by(OrganizationModel.name))
    project = await session.scalar(select(ProjectModel).order_by(ProjectModel.updated_at.desc()))
    headers = {
        "X-Actor-ID": "local-dashboard-admin",
        "X-Actor-Type": "human",
        "X-Actor-Role": "platform-admin",
    }
    return {
        "actor_headers": headers,
        "organization_id": None if organization is None else str(organization.id),
        "organization_name": None if organization is None else organization.name,
        "project_id": None if project is None else str(project.id),
        "project_name": None if project is None else project.name,
        "authority": {
            "mode": "local-dashboard-context",
            "role": "platform-admin",
            "explanation": (
                "Local development context for dashboard graph checks. Production still requires "
                "trusted proxy authentication and durable authority grants."
            ),
        },
    }


@router.get("/dashboard/telemetry-summary")
async def dashboard_telemetry_summary(
    session: SessionDependency, organization_id: uuid.UUID | None = None
) -> dict[str, Any]:
    projects = list((await session.scalars(select(ProjectModel))).all())
    jobs = list((await session.scalars(select(JobModel))).all())
    performance_metrics: list[PerformanceMetricModel] = []
    if organization_id is not None:
        performance_metrics = list(
            (
                await session.scalars(
                    select(PerformanceMetricModel)
                    .where(PerformanceMetricModel.organization_id == organization_id)
                    .order_by(PerformanceMetricModel.calculated_at.desc())
                    .limit(20)
                )
            ).all()
        )
    problem_jobs = unresolved_problem_jobs(jobs)
    acknowledged_problem_jobs = [
        job
        for job in jobs
        if job.status in {"failed", "dead_letter", "abandoned"} and job_is_acknowledged(job)
    ]
    running_jobs = [job for job in jobs if job.status in {"running", "leased"}]
    queued_jobs = [job for job in jobs if job.status in {"queued", "retry_wait"}]
    return {
        "runtime": {
            "project_count": len(projects),
            "job_count": len(jobs),
            "running_job_count": len(running_jobs),
            "queued_job_count": len(queued_jobs),
            "problem_job_count": len(problem_jobs),
            "acknowledged_problem_job_count": len(acknowledged_problem_jobs),
            "signal": "attention_required" if problem_jobs else "nominal",
        },
        "governed_performance": {
            "organization_id": None if organization_id is None else str(organization_id),
            "metric_count": len(performance_metrics),
            "metrics": [
                {
                    "metric_name": row.metric_key,
                    "scope_type": row.scope_type,
                    "score": float(row.metric_value),
                    "calculated_at": row.calculated_at,
                    "policy_version": row.policy_version,
                }
                for row in performance_metrics
            ],
            "status": "context_required" if organization_id is None else "available",
        },
        "operator_summary": (
            "Telemetry is nominal."
            if not problem_jobs
            else "Telemetry shows failed or dead-letter work that needs operator attention."
        ),
    }


def _readiness_item(name: str, ok: bool, detail: str, action: str) -> dict[str, str]:
    return {
        "name": name,
        "status": "ready" if ok else "needs_setup",
        "detail": detail,
        "action": action,
    }


@router.get("/dashboard/server-readiness")
async def dashboard_server_readiness() -> dict[str, Any]:
    settings = get_settings()
    app_env = settings.app_env.lower()
    root = _repo_root()
    repository_root = settings.repository_allowed_root
    artifact_root = settings.artifact_root
    runtime_root = root / "runtime-data"
    server_compose = root / "docker-compose.server.example.yml"
    server_env = root / ".env.server.example"
    observability_compose = root / "docker-compose.observability.yml"
    prometheus_config = root / "docker/observability/prometheus.yml"
    prometheus_alerts = root / "docker/observability/alert_rules.yml"
    grafana_dashboard = Path(
        root / "docker/observability/grafana/dashboards/ai-enterprise-overview.json"
    )
    reverse_proxy_config = root / "docker/reverse-proxy/nginx.conf.example"
    backup_verify = root / "tools/backup_verify.py"
    secret_generator = root / "tools/generate_server_secrets.py"
    proxy_signer = root / "tools/sign_proxy_assertion.py"
    model_verifier = root / "tools/model_endpoint_verify.py"
    deployment_blueprint = root / "tools/deployment_blueprint.py"
    deployment_blueprint_doc = root / "docs/enterprise/deployment-blueprint-module.md"
    infrastructure_choices = root / "tools/infrastructure_choices.py"
    infrastructure_choices_template = Path(
        root / "docs/enterprise/real-world-infrastructure-decisions.template.json"
    )
    backup_timer = root / "deploy/systemd/ai-enterprise-backup.timer"
    backup_service = root / "deploy/systemd/ai-enterprise-backup.service"
    k8s_api = root / "deploy/kubernetes/api-deployment.yaml"
    k8s_worker = root / "deploy/kubernetes/worker-deployment.yaml"
    alembic_ini = root / "apps/api/alembic.ini"
    migrations_dir = root / "migrations/versions"
    server_env_text = server_env.read_text(encoding="utf-8") if server_env.exists() else ""
    checks = [
        _readiness_item(
            "API runtime",
            True,
            f"Application environment is {settings.app_env}.",
            "Use production only behind trusted proxy authentication.",
        ),
        _readiness_item(
            "Trusted proxy",
            bool(settings.trusted_proxy_hmac_secret) or app_env == "development",
            (
                "Local development can use dashboard context."
                if app_env == "development"
                else "Trusted proxy secret is configured."
            ),
            "Set TRUSTED_PROXY_HMAC_SECRET and sign identity headers on the server.",
        ),
        _readiness_item(
            "Project workspace",
            repository_root.exists(),
            f"Allowed repository root is {repository_root}.",
            "Create the server workspace root and mount it as /workspaces.",
        ),
        _readiness_item(
            "Artifact storage",
            artifact_root.exists(),
            f"Artifact root is {artifact_root}.",
            "Mount durable artifact storage on the server.",
        ),
        _readiness_item(
            "Runtime storage",
            runtime_root.exists(),
            f"Runtime root is {runtime_root}.",
            "Mount durable runtime storage for snapshots, recovery, and execution evidence.",
        ),
        _readiness_item(
            "Model service",
            bool(settings.ollama_base_url),
            f"Model endpoint is {settings.ollama_base_url}.",
            "Use an internal Ollama/GPU service or managed model bridge on the server.",
        ),
        _readiness_item(
            "Server compose profile",
            server_compose.exists() and server_env.exists(),
            "Server compose and environment templates are present.",
            "Create .env.server from .env.server.example and run server-readiness.",
        ),
        _readiness_item(
            "Backup verification",
            backup_verify.exists(),
            "Backup readiness command is available.",
            "Run make backup-verify before scheduling production backups.",
        ),
        _readiness_item(
            "Migration gate",
            alembic_ini.exists() and migrations_dir.exists(),
            "Database migration verification path is available.",
            "Run migration checks before starting the API on a server.",
        ),
        _readiness_item(
            "Server secret generator",
            secret_generator.exists(),
            "Secret generation helper is available.",
            "Run make server-secrets, review .env.server.generated, then install real server values.",
        ),
        _readiness_item(
            "Proxy signature helper",
            proxy_signer.exists(),
            "Trusted proxy signature helper is available.",
            "Use tools/sign_proxy_assertion.py to validate the identity service headers before exposing the dashboard.",
        ),
        _readiness_item(
            "Model endpoint verifier",
            model_verifier.exists(),
            "Production model endpoint checker is available.",
            "Set OLLAMA_BASE_URL and OLLAMA_MODEL, then run make model-verify.",
        ),
        _readiness_item(
            "GitHub access hooks",
            all(
                token in server_env_text
                for token in (
                    "LOCAL_GIT_REMOTE_URL=",
                    "GITHUB_INTEGRATION_MODE=",
                    "GITHUB_APP_ID=",
                    "GITHUB_APP_INSTALLATION_ID=",
                    "GITHUB_PRIVATE_KEY_PATH=",
                    "GITHUB_TOKEN_FILE=",
                )
            ),
            "GitHub and Git remote variables are documented.",
            "Choose SSH, token-file, or GitHub App integration before production project creation.",
        ),
        _readiness_item(
            "Scheduled backup templates",
            backup_timer.exists() and backup_service.exists(),
            "Systemd backup verification schedule templates are available.",
            "Install the timer on the server and run a restore drill before production use.",
        ),
        _readiness_item(
            "Managed storage hooks",
            all(
                token in server_env_text
                for token in (
                    "MANAGED_POSTGRES_URL=",
                    "OBJECT_STORAGE_PROVIDER=",
                    "OBJECT_STORAGE_BUCKET=",
                    "OBJECT_STORAGE_REGION=",
                )
            ),
            "Managed Postgres and object-storage variables are documented.",
            "Choose managed Postgres or object storage provider before multi-server rollout.",
        ),
        _readiness_item(
            "Kubernetes rollout templates",
            k8s_api.exists() and k8s_worker.exists(),
            "API and worker deployment templates are available.",
            "Replace image, secret, ingress, and storage values for the target cluster.",
        ),
        _readiness_item(
            "Prometheus and Grafana",
            observability_compose.exists()
            and prometheus_config.exists()
            and grafana_dashboard.exists(),
            "Observability compose and dashboard templates are present.",
            "Run make observability-check, then make observability-up when ready.",
        ),
        _readiness_item(
            "Production alert rules",
            prometheus_alerts.exists(),
            "Prometheus alert rules are present.",
            "Connect these alerts to the production notification channel before external use.",
        ),
        _readiness_item(
            "Reverse proxy and TLS",
            reverse_proxy_config.exists(),
            "Reverse proxy TLS template is present.",
            "Adapt docker/reverse-proxy/nginx.conf.example for the server domain and identity service.",
        ),
        _readiness_item(
            "Code graph",
            GRAPHIFY_HTML.exists(),
            "Graphify dashboard is mounted.",
            "Run graphify update . after code changes.",
        ),
        _readiness_item(
            "Deployment blueprint",
            deployment_blueprint.exists() and deployment_blueprint_doc.exists(),
            "Reusable deployment blueprint module is present.",
            "Run make deployment-blueprint before repeating this migration for another enterprise.",
        ),
        _readiness_item(
            "Infrastructure choices gate",
            infrastructure_choices.exists() and infrastructure_choices_template.exists(),
            "Real provider decision template and verifier are present.",
            "Create docs/enterprise/real-world-infrastructure-decisions.json and run make infrastructure-choices-verify.",
        ),
    ]
    failed = [item for item in checks if item["status"] != "ready"]
    return {
        "status": "ready" if not failed else "needs_setup",
        "summary": (
            "Server migration checks are ready to run."
            if not failed
            else f"{len(failed)} server readiness item(s) need setup."
        ),
        "checks": checks,
        "commands": [
            "make server-readiness-template",
            "make server-secrets",
            "cp .env.server.example .env.server",
            "make server-readiness",
            "OLLAMA_BASE_URL=http://model-service:11434 OLLAMA_MODEL=llama3.1:8b make model-verify",
            "make backup-verify",
            "make deployment-blueprint",
            "make infrastructure-choices-template",
            "make infrastructure-choices-verify",
            "make observability-check",
            "make observability-up",
            "docker compose --env-file .env.server -f docker-compose.server.example.yml config --quiet",
        ],
    }


def _deployment_blueprint_payload() -> dict[str, Any]:
    root = _repo_root()
    artifacts = {
        "server_env_template": root / ".env.server.example",
        "server_compose_profile": root / "docker-compose.server.example.yml",
        "reverse_proxy_tls": root / "docker/reverse-proxy/nginx.conf.example",
        "prometheus_config": root / "docker/observability/prometheus.yml",
        "prometheus_alerts": root / "docker/observability/alert_rules.yml",
        "grafana_dashboard": root
        / "docker/observability/grafana/dashboards/ai-enterprise-overview.json",
        "backup_timer": root / "deploy/systemd/ai-enterprise-backup.timer",
        "backup_service": root / "deploy/systemd/ai-enterprise-backup.service",
        "kubernetes_api": root / "deploy/kubernetes/api-deployment.yaml",
        "kubernetes_worker": root / "deploy/kubernetes/worker-deployment.yaml",
    }
    missing = [name for name, path in artifacts.items() if not path.exists()]
    return {
        "name": "AI Enterprise Deployment Blueprint",
        "status": "ready" if not missing else "needs_setup",
        "business_meaning": (
            "The migration path is reusable as an enterprise installation pattern."
            if not missing
            else "The migration pattern is not complete because some deployment artifacts are missing."
        ),
        "next_action": (
            "Choose real provider values, generate .env.server, and run the server-readiness gate."
            if not missing
            else f"Create missing artifacts: {', '.join(missing)}."
        ),
        "phases": [
            {
                "phase": 1,
                "name": "Stabilize local truth",
                "gate": "Dashboard reads the official manager read model and problem jobs are resolved or acknowledged.",
                "proof": ["/api/v1/query/dashboard-manager", "/dashboard/server-readiness"],
            },
            {
                "phase": 2,
                "name": "Create server profile",
                "gate": "Server compose and .env.server template remove laptop paths and placeholder runtime assumptions.",
                "proof": ["make server-readiness-template", "docker-compose.server.example.yml"],
            },
            {
                "phase": 3,
                "name": "Single server deployment",
                "gate": "API, worker, Postgres, volumes, reverse proxy, TLS, and trusted identity headers are configured.",
                "proof": ["make server-readiness", "tools/sign_proxy_assertion.py"],
            },
            {
                "phase": 4,
                "name": "Production observability",
                "gate": "Prometheus, Grafana, alerts, backups, and model endpoint verification are operational.",
                "proof": ["make observability-check", "make backup-verify", "make model-verify"],
            },
            {
                "phase": 5,
                "name": "Scalable factory",
                "gate": "Managed database, object storage, durable workspaces, and horizontally scalable workers are chosen.",
                "proof": ["MANAGED_POSTGRES_URL", "OBJECT_STORAGE_BUCKET", "deploy/kubernetes"],
            },
            {
                "phase": 6,
                "name": "Production multiserver deployment",
                "gate": "Kubernetes or separate worker nodes run API and worker pools with shared observability and backup controls.",
                "proof": [
                    "deploy/kubernetes/api-deployment.yaml",
                    "deploy/kubernetes/worker-deployment.yaml",
                ],
            },
        ],
        "artifacts": {name: {"path": str(path), "exists": path.exists()} for name, path in artifacts.items()},
        "missing": missing,
    }


@router.get("/dashboard/deployment-blueprint")
async def dashboard_deployment_blueprint() -> dict[str, Any]:
    return _deployment_blueprint_payload()


@router.get("/dashboard/infrastructure-choices")
async def dashboard_infrastructure_choices() -> dict[str, Any]:
    choices_path = _repo_path("docs/enterprise/real-world-infrastructure-decisions.json")
    template_path = _repo_path(
        "docs/enterprise/real-world-infrastructure-decisions.template.json"
    )
    verify = _load_tool_function("infrastructure_choices", "verify")

    if choices_path.exists():
        return verify(choices_path)
    report = verify(template_path, allow_placeholders=True)
    return {
        **report,
        "status": "needs_setup",
        "conformant": False,
        "summary": "The infrastructure decision template is ready, but real production choices have not been recorded yet.",
        "findings": [
            "Create docs/enterprise/real-world-infrastructure-decisions.json with real domain, identity, model, GitHub, database, storage, Kubernetes, backup, and alert values."
        ],
        "next_action": "Copy the template, replace placeholders with real provider choices, then run make infrastructure-choices-verify.",
    }


CLIENT_MANIFEST_TEMPLATE = """# AI-Enterprise Client Project Manifest

This document collects the information AI Enterprise needs before creating a project.
Complete what you know. If something is unknown, leave it blank and AI Enterprise will identify the
gap during intake.

## Chapter 1 - Project Identity

Project Name:
Company / Organization:
Primary Contact:
Project Sponsor:
Date:
Version:
Confidentiality Level:
Preferred Communication Method:
Project Base Directory:
GitHub Repository URL:
Default Branch: main

## Chapter 2 - Executive Vision

Why does this project exist?
What problem are you trying to solve?
Why is solving it important?
What would success look like?
What happens if this project is never built?
What business opportunity does it create?
Why now?

## Chapter 3 - Business Profile

Describe your company.
What industry are you in?
How large is the organization?
How many employees?
Which countries do you operate in?
Describe your business model.
What products or services do you offer?

## Chapter 4 - Current Situation

Describe your current environment.
Include current software, infrastructure, manual processes, pain points, repeated work, and current
workflows.

## Chapter 5 - Project Objectives

Critical Objectives:
High Priority:
Medium Priority:
Future Ideas:

## Chapter 6 - Problems to Solve

Problem:
Impact:
Frequency:
Business Cost:
Current Workaround:
Desired Outcome:

## Chapter 7 - Target Users

Who will use the system?
How many users?
Technical skill level?
Languages?
Accessibility requirements?

## Chapter 8 - Functional Expectations

Describe what the system should do. Examples: user management, reports, AI assistant, voice
commands, automation, notifications, dashboards, integrations, scheduling, payments, inventory,
CRM, ERP.

## Chapter 9 - Non-Functional Expectations

Performance:
Security:
Reliability:
Availability:
Scalability:
Offline Support:
Cloud:
Local Installation:
Cross Platform:
Mobile:
Accessibility:
Compliance:

## Chapter 10 - Existing Systems

What already exists? Include CRM, ERP, accounting, database, website, desktop software, cloud
services, email, authentication, storage, APIs, and legacy systems.

## Chapter 11 - Data

What data already exists?
Where is it stored?
Estimated size?
Sensitive data?
Retention rules?

## Chapter 12 - AI Requirements

Do you want chatbot, voice assistant, automation, document analysis, predictions, image processing,
speech recognition, natural language processing, agent teams, decision support, or other AI
capabilities?

## Chapter 13 - Automation

Which repetitive tasks should disappear?
What currently requires manual work?
What approvals exist?
Who performs them?

## Chapter 14 - Integrations

What systems should communicate? Include internal software, external APIs, hardware, IoT, payment
systems, email, cloud services, ERP, and CRM.

## Chapter 15 - Security

Required authentication:
Multi-factor authentication:
User roles:
Permissions:
Encryption:
Audit logs:
Compliance:
Backups:
Disaster recovery:

## Chapter 16 - Infrastructure

Desktop:
Web:
Mobile:
Windows:
Linux:
Mac:
Cloud:
On-premise:
Hybrid:
Virtualization:
Containers:

## Chapter 17 - User Experience

Preferred interface:
Dark Mode:
Accessibility:
Multiple languages:
Branding:
Voice:
Touch:
Keyboard:

## Chapter 18 - Constraints

Budget:
Deadline:
Technology restrictions:
Legal restrictions:
Existing contracts:
Mandatory software:
Forbidden software:
Performance limits:

## Chapter 19 - Risks

What worries you most? Budget, security, time, adoption, training, migration, data loss, or
compliance?

## Chapter 20 - Success Criteria

How will success be measured?
Business KPIs:
Technical KPIs:
User Satisfaction:
Performance:
Cost Reduction:
Time Savings:
Revenue:
Quality:

## Chapter 21 - Future Vision

Where should this system be in 1 year, 3 years, and 5 years?

## Chapter 22 - Supporting Material

List PDFs, Word documents, spreadsheets, architecture, images, videos, audio, emails, existing code,
diagrams, contracts, or anything useful.

## Chapter 23 - Final Notes

Anything not already covered. Ideas, concerns, or special requests.
"""


PROJECT_FOUNDRY_CORE_DOWNLOAD = """# Project Foundry Core v0.1

Project Foundry is the AEOS operating framework for turning a client idea into a governed project.

## Lifecycle

Project idea -> structured intake -> requirements -> risk analysis -> architecture -> work
breakdown -> specialist agents -> integration -> testing -> security validation -> deployment
package -> documentation -> operations -> improvement.

## Core Contracts

- Project Intake Schema
- Requirements Schema
- Execution Plan Schema
- Agent Task Schema
- Review Report Schema
- Approval Matrix
- Quality Gates
- Root AGENTS.md
- Prompt Contracts
- Repository Template

## Agent Hierarchy

- Executive Orchestrator
- Project Manager Agent
- Requirements Analyst Agent
- Solution Architect Agent
- Domain Expert Agents
- Implementation Agents
- Verification Agents
- Release Manager Agent

## Quality Gates

Gate 0: intake completeness.
Gate 1: requirements approval.
Gate 2: architecture approval.
Gate 3: implementation readiness.
Gate 4: component verification.
Gate 5: integration verification.
Gate 6: release readiness.

## Autonomy Boundary

Project Foundry targets controlled autonomy. It can analyze repositories, draft architecture,
decompose work, generate code, run tests, prepare integration, and create release artifacts. It must
not deploy to production, delete customer data, expose services publicly, change enterprise security
policy, use unrestricted administrator credentials, purchase services, make legal commitments, or
approve its own security exceptions.

Canonical repo artifacts:

- docs/aeos/README.md
- docs/aeos/project-foundry-core-v0.1.md
- specifications/aeos/
- templates/project-foundry/
"""


DOCUMENTATION_HUB_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Enterprise Documentation Hub</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #07090d;
      --panel: rgba(13, 18, 24, 0.9);
      --border: rgba(143, 166, 190, 0.24);
      --text: #edf4fb;
      --muted: #a6b4c2;
      --blue: #5db8ff;
      --green: #56e39f;
      --amber: #ffd166;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: radial-gradient(circle at 12% 12%, rgba(93, 184, 255, 0.22), transparent 30%),
        linear-gradient(135deg, #07090d, #0d1418 52%, #080a0e);
      color: var(--text);
    }
    main { width: min(1180px, calc(100vw - 32px)); margin: 0 auto; padding: 28px 0 40px; }
    header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 18px; }
    h1 { margin: 0 0 6px; font-size: clamp(1.5rem, 3vw, 2.35rem); }
    h2 { margin: 0 0 10px; font-size: 1rem; }
    p { color: var(--muted); line-height: 1.48; margin: 0; }
    a { color: inherit; }
    .button {
      min-height: 38px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: rgba(15, 23, 31, 0.86);
      color: var(--text);
      padding: 0 12px;
      font-weight: 650;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }
    .grid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 12px; }
    .panel {
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--panel);
      padding: 14px;
      box-shadow: 0 18px 60px rgba(0, 0, 0, 0.24);
    }
    .span-4 { grid-column: span 4; }
    .span-6 { grid-column: span 6; }
    .span-12 { grid-column: span 12; }
    .listbox { display: grid; gap: 8px; max-height: 360px; overflow: auto; padding-right: 4px; }
    .item {
      border: 1px solid rgba(143, 166, 190, 0.18);
      border-radius: 8px;
      background: rgba(7, 12, 18, 0.78);
      padding: 10px;
      display: grid;
      gap: 4px;
      text-decoration: none;
    }
    button.item {
      width: 100%;
      color: inherit;
      cursor: pointer;
      text-align: left;
      font: inherit;
    }
    .doc-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
    .doc-preview {
      min-height: 560px;
      max-height: 72vh;
      overflow-y: auto;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      border: 1px solid rgba(143, 166, 190, 0.18);
      border-radius: 8px;
      background: rgba(7, 12, 18, 0.78);
      color: var(--text);
      padding: 12px;
      line-height: 1.45;
    }
    .doc-status { margin-bottom: 10px; color: var(--muted); }
    .item strong { color: var(--text); }
    .item span, code { color: var(--muted); }
    code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    .pill { color: var(--green); font-weight: 700; }
    @media (max-width: 760px) { .span-4, .span-6 { grid-column: span 12; } header { flex-direction: column; } }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Documentation Hub</h1>
        <p>One place for project documents, graph views, operator commands, and the required close-out discipline.</p>
      </div>
      <a class="button" href="/dashboard">Back to Command Center</a>
    </header>
    <section class="grid">
      <article class="panel span-12">
        <h2>Working Method</h2>
        <div class="listbox">
          <div class="item"><strong>1. Plan</strong><span>Write or update the implementation plan before changing behavior.</span></div>
          <div class="item"><strong>2. Execute</strong><span>Implement the smallest disciplined slice connected to real data sources.</span></div>
          <div class="item"><strong>3. Verify</strong><span>Run focused tests, full gates when needed, live endpoint checks, and graphify update.</span></div>
          <div class="item"><strong>4. Document</strong><span>If verification passes, update affected documentation in the same change.</span></div>
        </div>
      </article>
      <article class="panel span-6">
        <h2>Operator Documents</h2>
        <div class="listbox">
          <button class="item doc-open" data-doc="client-manifest-template" data-download="/dashboard/client-manifest-template"><strong>Client Manifest Template</strong><span>Download and send to a client or requesting service.</span></button>
          <button class="item doc-open" data-doc="project-foundry-core" data-download="/dashboard/project-foundry-core"><strong>Project Foundry Core</strong><span>AEOS project factory contracts, gates, and prompt rules.</span></button>
          <button class="item doc-open" data-doc="operator-startup-guide" data-download="/dashboard/documentation/operator-startup-guide?download=true"><strong>Operator Startup Guide</strong><span><code>docs/enterprise/operator-startup-guide.md</code></span></button>
          <button class="item doc-open" data-doc="project-execution-walkthrough" data-download="/dashboard/documentation/project-execution-walkthrough?download=true"><strong>Project Execution Walkthrough</strong><span><code>docs/enterprise/project-execution-walkthrough.md</code></span></button>
          <button class="item doc-open" data-doc="working-method" data-download="/dashboard/documentation/working-method?download=true"><strong>Working Method</strong><span><code>docs/enterprise/working-method.md</code></span></button>
          <button class="item doc-open" data-doc="real-world-infrastructure-choices" data-download="/dashboard/documentation/real-world-infrastructure-choices?download=true"><strong>Infrastructure Choices</strong><span><code>docs/enterprise/real-world-infrastructure-choices.md</code></span></button>
        </div>
      </article>
      <article class="panel span-6">
        <h2>Graphs and Images</h2>
        <div class="listbox">
          <a class="item" href="/dashboard"><strong>Execution Graph</strong><span>Open the Execution tab for live project advancement.</span></a>
          <a class="item" href="/dashboard/graphify"><strong>Code Graph</strong><span>Architecture graph generated from graphify.</span></a>
          <div class="item"><strong>Enterprise Movement Graph</strong><span>Open Overview in the command center.</span></div>
          <div class="item"><strong>Future Visual Library</strong><span>Store reference images, project diagrams, and proof screenshots beside project docs.</span></div>
        </div>
      </article>
      <article class="panel span-12">
        <h2>Document Preview</h2>
        <p id="docStatus" class="doc-status">Select a document. It will appear here in a large reading box with a vertical scrollbar and a download action.</p>
        <pre id="docPreview" class="doc-preview">No document selected.</pre>
        <div class="doc-actions">
          <a id="docDownload" class="button" href="/dashboard/client-manifest-template">Download Selected Document</a>
          <a id="docOpenRaw" class="button" href="/dashboard/documentation/client-manifest-template" target="_blank" rel="noreferrer">Open Raw Text</a>
        </div>
      </article>
      <article class="panel span-12">
        <h2>Commands</h2>
        <div class="listbox">
          <div class="item"><strong>Start stack</strong><span><code>docker compose up --build -d</code></span></div>
          <div class="item"><strong>Readiness</strong><span><code>curl http://localhost:8000/health/ready</code></span></div>
          <div class="item"><strong>Execution manager</strong><span><code>curl /api/v1/query/dashboard-manager</code></span></div>
          <div class="item"><strong>Verification</strong><span><code>pytest -q</code>, <code>ruff check</code>, <code>mypy src</code></span></div>
          <div class="item"><strong>Graph update</strong><span><code>graphify update .</code></span></div>
        </div>
      </article>
    </section>
  </main>
  <script>
    const preview = document.getElementById("docPreview");
    const status = document.getElementById("docStatus");
    const download = document.getElementById("docDownload");
    const raw = document.getElementById("docOpenRaw");
    async function openDocument(button) {
      const id = button.dataset.doc;
      const title = button.querySelector("strong").textContent;
      const url = `/dashboard/documentation/${encodeURIComponent(id)}`;
      status.textContent = `Loading ${title}...`;
      preview.textContent = "";
      download.href = button.dataset.download || `${url}?download=true`;
      raw.href = url;
      try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        preview.textContent = await response.text();
        status.textContent = `${title} loaded. Use the scrollbar to read, or download the document.`;
      } catch (error) {
        preview.textContent = "Document preview needs attention. Check API readiness, confirm the document is registered in the Documentation Hub, then retry the preview or download action.";
        status.textContent = `${title} preview needs attention.`;
      }
    }
    document.querySelectorAll(".doc-open").forEach(button => {
      button.addEventListener("click", () => openDocument(button));
    });
    const firstDocument = document.querySelector(".doc-open");
    if (firstDocument) openDocument(firstDocument);
  </script>
</body>
</html>
"""


DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Enterprise Command Center</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #06080b;
      --panel: rgba(14, 18, 24, 0.86);
      --panel-strong: rgba(20, 27, 35, 0.94);
      --border: rgba(143, 166, 190, 0.24);
      --text: #edf4fb;
      --muted: #9eafbf;
      --green: #56e39f;
      --blue: #5db8ff;
      --amber: #ffd166;
      --red: #ff6b6b;
      --line: rgba(93, 184, 255, 0.28);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    * { box-sizing: border-box; }
    body {
      min-height: 100vh;
      margin: 0;
      background: radial-gradient(circle at 12% 10%, rgba(45, 115, 141, 0.24), transparent 30%),
        radial-gradient(circle at 88% 18%, rgba(78, 116, 99, 0.18), transparent 26%),
        linear-gradient(135deg, #06080b 0%, #0a1116 48%, #090b0f 100%);
      color: var(--text);
      overflow-x: hidden;
    }

    canvas#field {
      position: fixed;
      inset: 0;
      z-index: -1;
      opacity: 0.55;
    }

    a { color: inherit; }
    .shell {
      width: min(1440px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 24px 0 32px;
    }

    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 18px;
    }

    .identity h1 {
      margin: 0 0 4px;
      font-size: clamp(1.35rem, 3vw, 2.15rem);
      font-weight: 760;
      letter-spacing: 0;
    }

    .identity p {
      margin: 0;
      color: var(--muted);
      font-size: 0.94rem;
    }

    .top-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
    }

    button, .link-button {
      min-height: 38px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: rgba(15, 23, 31, 0.86);
      color: var(--text);
      padding: 0 12px;
      font-weight: 650;
      text-decoration: none;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      white-space: nowrap;
    }

    button:hover, .link-button:hover { border-color: rgba(93, 184, 255, 0.72); }

    .tabs {
      display: grid;
      grid-template-columns: repeat(7, minmax(0, 1fr));
      gap: 8px;
      margin-bottom: 16px;
    }

    .coach {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      align-items: center;
      margin-bottom: 16px;
      border-color: rgba(86, 227, 159, 0.36);
      background: rgba(8, 18, 18, 0.9);
    }

    .coach strong { display: block; margin-bottom: 4px; }
    .coach p { margin: 0; color: var(--muted); line-height: 1.45; }
    .coach .coach-actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
    .orientation {
      display: grid;
      gap: 10px;
      margin-bottom: 16px;
      border-color: rgba(93, 184, 255, 0.36);
    }

    .orientation-steps {
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 8px;
    }

    .orientation-step {
      min-height: 72px;
      border: 1px solid rgba(143, 166, 190, 0.18);
      border-radius: 8px;
      background: rgba(7, 12, 18, 0.74);
      padding: 10px;
    }

    .orientation-step strong { display: block; margin-bottom: 4px; font-size: 0.82rem; }
    .orientation-step span { display: block; color: var(--muted); font-size: 0.76rem; line-height: 1.3; }
    .orientation-step.done { border-color: rgba(86, 227, 159, 0.54); }
    .orientation-step.current { border-color: rgba(93, 184, 255, 0.9); background: rgba(93, 184, 255, 0.15); }

    .orientation-next {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: center;
    }

    .orientation-next p { margin: 0; color: var(--muted); line-height: 1.4; }
    .source-strip {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 8px;
      margin-bottom: 16px;
    }

    .source-card {
      min-height: 66px;
      border: 1px solid rgba(143, 166, 190, 0.18);
      border-radius: 8px;
      background: rgba(7, 12, 18, 0.76);
      padding: 10px;
      color: var(--text);
      text-align: left;
      display: block;
      width: 100%;
      white-space: normal;
    }

    .source-card:hover { border-color: rgba(93, 184, 255, 0.72); }
    .source-card strong { display: block; margin-bottom: 4px; }
    .source-card span { display: block; color: var(--muted); font-size: 0.8rem; line-height: 1.35; }

    .business-board {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }

    .business-card {
      min-height: 132px;
      border: 1px solid rgba(143, 166, 190, 0.2);
      border-radius: 8px;
      background: rgba(7, 12, 18, 0.82);
      padding: 12px;
      display: grid;
      align-content: space-between;
      gap: 10px;
    }

    .business-card strong { display: block; font-size: 0.92rem; }
    .business-card p { margin: 0; color: var(--muted); line-height: 1.42; font-size: 0.86rem; }
    .business-card button { width: 100%; }

    .tab[aria-selected="true"] {
      background: rgba(93, 184, 255, 0.17);
      border-color: rgba(93, 184, 255, 0.78);
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(12, minmax(0, 1fr));
      gap: 12px;
    }

    .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px;
      box-shadow: 0 18px 60px rgba(0, 0, 0, 0.28);
      backdrop-filter: blur(10px);
    }

    .span-3 { grid-column: span 3; }
    .span-4 { grid-column: span 4; }
    .span-6 { grid-column: span 6; }
    .span-8 { grid-column: span 8; }
    .span-12 { grid-column: span 12; }

    .panel h2 {
      margin: 0 0 10px;
      font-size: 0.95rem;
      letter-spacing: 0;
    }

    .metric {
      font-size: 2rem;
      font-weight: 800;
      line-height: 1;
    }

    .living-signal {
      display: grid;
      gap: 8px;
    }

    .pulse-row {
      display: grid;
      grid-template-columns: 120px minmax(0, 1fr) auto;
      gap: 10px;
      align-items: center;
      font-size: 0.86rem;
    }

    .pulse-track {
      height: 8px;
      border-radius: 999px;
      background: rgba(143, 166, 190, 0.14);
      overflow: hidden;
    }

    .pulse-fill {
      height: 100%;
      min-width: 8%;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--green), var(--blue));
      animation: breathe 2.8s ease-in-out infinite;
    }

    @keyframes breathe {
      50% { filter: brightness(1.35); opacity: 0.82; }
    }

    .muted { color: var(--muted); }
    .status {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      font-weight: 720;
    }

    .dot {
      width: 9px;
      height: 9px;
      border-radius: 999px;
      background: var(--muted);
      box-shadow: 0 0 12px currentColor;
    }

    .ok { color: var(--green); }
    .warn { color: var(--amber); }
    .bad { color: var(--red); }
    .info { color: var(--blue); }

    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 0.88rem;
    }

    th, td {
      padding: 9px 8px;
      border-bottom: 1px solid rgba(143, 166, 190, 0.14);
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }

    th {
      color: var(--muted);
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0;
      font-weight: 780;
    }

    .toolbar {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 10px;
    }

    input, select, textarea {
      min-height: 36px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: rgba(3, 7, 11, 0.72);
      color: var(--text);
      padding: 0 10px;
    }

    textarea {
      width: 100%;
      min-height: 108px;
      padding: 10px;
      resize: vertical;
    }

    .cards {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px;
    }

    .mini {
      background: var(--panel-strong);
      border: 1px solid rgba(143, 166, 190, 0.16);
      border-radius: 8px;
      padding: 12px;
      min-height: 92px;
    }

    .mini strong { display: block; margin-bottom: 6px; }
    .launch-contract {
      display: grid;
      gap: 10px;
      margin-top: 10px;
      border-color: rgba(93, 184, 255, 0.32);
    }
    .launch-contract-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 8px;
    }
    .launch-contract-cell {
      border: 1px solid rgba(143, 166, 190, 0.16);
      border-radius: 8px;
      background: rgba(3, 7, 11, 0.64);
      padding: 10px;
    }
    .launch-contract-cell span {
      display: block;
      color: var(--muted);
      font-size: 0.72rem;
      font-weight: 760;
      text-transform: uppercase;
    }
    .launch-contract-cell strong {
      display: block;
      margin-top: 4px;
      font-size: 0.98rem;
      line-height: 1.22;
      overflow-wrap: anywhere;
    }
    .launch-contract-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .launch-contract-list {
      display: grid;
      gap: 6px;
    }
    .launch-contract-list > strong {
      margin: 0;
      font-size: 0.86rem;
    }
    .launch-contract-list .listbox {
      max-height: 220px;
    }
    .info-card {
      display: grid;
      grid-template-rows: auto minmax(0, 1fr) auto;
      gap: 8px;
    }
    .card-kicker {
      color: var(--muted);
      font-size: 0.72rem;
      font-weight: 780;
      text-transform: uppercase;
    }
    .card-value {
      color: var(--text);
      font-size: 1rem;
      font-weight: 780;
      line-height: 1.22;
      overflow-wrap: anywhere;
    }
    .field-list {
      display: grid;
      gap: 6px;
      margin-top: 8px;
    }
    .field-row {
      display: grid;
      grid-template-columns: 112px minmax(0, 1fr);
      gap: 8px;
      align-items: start;
      color: var(--muted);
      font-size: 0.82rem;
      line-height: 1.32;
    }
    .field-row span:first-child {
      color: var(--muted);
      font-weight: 760;
    }
    .field-row span:last-child {
      color: var(--text);
      overflow-wrap: anywhere;
    }
    .listbox {
      display: grid;
      gap: 8px;
      max-height: 420px;
      overflow: auto;
      padding: 2px 4px 2px 0;
      scrollbar-color: rgba(93, 184, 255, 0.68) rgba(143, 166, 190, 0.12);
      scrollbar-width: thin;
    }

    .listbox::-webkit-scrollbar { width: 10px; }
    .listbox::-webkit-scrollbar-track { background: rgba(143, 166, 190, 0.12); border-radius: 999px; }
    .listbox::-webkit-scrollbar-thumb { background: rgba(93, 184, 255, 0.68); border-radius: 999px; }

    .list-item {
      width: 100%;
      min-height: 72px;
      border: 1px solid rgba(143, 166, 190, 0.18);
      border-radius: 8px;
      background: rgba(7, 12, 18, 0.72);
      color: var(--text);
      padding: 10px;
      text-align: left;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: start;
    }

    .list-item:hover { border-color: rgba(93, 184, 255, 0.72); }
    .list-item.selected { border-color: rgba(93, 184, 255, 0.88); background: rgba(93, 184, 255, 0.14); }
    .list-title { font-weight: 760; margin-bottom: 4px; overflow-wrap: anywhere; }
    .list-meta { color: var(--muted); font-size: 0.82rem; overflow-wrap: anywhere; }
    .pill {
      border: 1px solid currentColor;
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 0.72rem;
      font-weight: 780;
      white-space: nowrap;
    }

    .phase-graph {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 10px;
      margin-bottom: 12px;
    }

    .phase-node {
      min-height: 96px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: rgba(7, 12, 18, 0.76);
      color: var(--text);
      padding: 10px;
      text-align: left;
      position: relative;
      overflow: hidden;
    }

    .phase-node::after {
      content: "";
      position: absolute;
      inset: auto 10px 10px 10px;
      height: 3px;
      border-radius: 999px;
      background: var(--muted);
    }

    .phase-node.executed::after { background: var(--green); }
    .phase-node.current::after { background: var(--amber); }
    .phase-node.remaining::after { background: var(--blue); opacity: 0.45; }
    .phase-node.selected { border-color: rgba(93, 184, 255, 0.88); }
    .phase-node span { display: block; color: var(--muted); font-size: 0.78rem; margin-top: 5px; }
    .movement-wrap {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(260px, 0.36fr);
      gap: 12px;
      align-items: stretch;
    }

    .movement-graph {
      width: 100%;
      min-height: 430px;
      border: 1px solid rgba(143, 166, 190, 0.16);
      border-radius: 8px;
      background: rgba(3, 7, 11, 0.42);
    }

    .movement-edge {
      stroke: rgba(93, 184, 255, 0.44);
      stroke-width: 2;
      marker-end: url(#arrowhead);
    }

    .movement-edge.pulse {
      stroke: rgba(86, 227, 159, 0.72);
      stroke-dasharray: 8 9;
      animation: flowLine 2.4s linear infinite;
    }

    .movement-node { cursor: pointer; }
    .movement-node rect {
      fill: rgba(12, 20, 28, 0.94);
      stroke: rgba(143, 166, 190, 0.32);
      stroke-width: 1.2;
      rx: 8;
    }

    .movement-node:hover rect, .movement-node.selected rect {
      stroke: rgba(93, 184, 255, 0.92);
      fill: rgba(93, 184, 255, 0.16);
    }

    .movement-node text {
      fill: var(--text);
      font-weight: 740;
      font-size: 13px;
      letter-spacing: 0;
      pointer-events: none;
    }

    .movement-node .node-subtitle {
      fill: var(--muted);
      font-weight: 560;
      font-size: 11px;
    }

    .control-inspector {
      min-height: 430px;
      display: grid;
      align-content: start;
      gap: 10px;
    }

    .control-inspector .signal {
      display: grid;
      gap: 8px;
      max-height: 214px;
      overflow: auto;
      padding-right: 4px;
    }

    .surface-graph {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 10px;
      position: relative;
    }

    #problemGraph.surface-graph {
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    }

    .surface-node {
      min-height: 184px;
      border: 1px solid rgba(143, 166, 190, 0.2);
      border-radius: 8px;
      background: linear-gradient(180deg, rgba(12, 20, 28, 0.94), rgba(5, 10, 15, 0.88));
      color: var(--text);
      padding: 12px;
      text-align: left;
      display: grid;
      grid-template-rows: auto auto minmax(0, 1fr) auto;
      align-content: start;
      gap: 8px;
      position: relative;
      overflow: hidden;
      white-space: normal;
      min-width: 0;
    }

    .surface-node::before {
      content: "";
      position: absolute;
      inset: 0;
      border-top: 2px solid rgba(93, 184, 255, 0.4);
      transform: translateX(-100%);
      animation: scanNode 3.2s linear infinite;
    }

    .surface-node:hover, .surface-node.selected {
      border-color: rgba(93, 184, 255, 0.88);
      background: rgba(93, 184, 255, 0.14);
    }

    .surface-node strong, .surface-node span, .surface-node small {
      position: relative;
      z-index: 1;
      min-width: 0;
      max-width: 100%;
      overflow-wrap: anywhere;
      word-break: normal;
    }

    .surface-node strong {
      display: block;
      line-height: 1.18;
      font-size: 0.94rem;
    }

    .surface-node small {
      display: block;
      color: var(--muted);
      line-height: 1.32;
      font-size: 0.8rem;
    }

    .human-copy {
      position: relative;
      z-index: 1;
      display: grid;
      align-content: start;
      gap: 5px;
      color: var(--muted);
      font-size: 0.76rem;
      line-height: 1.32;
      min-width: 0;
      overflow: hidden;
    }

    .human-copy span {
      display: block;
      min-width: 0;
      overflow-wrap: anywhere;
    }

    .human-copy b { color: var(--text); font-weight: 760; }

    .surface-node > .pill {
      align-self: end;
      justify-self: start;
      max-width: 100%;
      white-space: normal;
      line-height: 1.15;
    }

    @keyframes scanNode {
      55%, 100% { transform: translateX(100%); }
    }

    @keyframes flowLine {
      to { stroke-dashoffset: -68; }
    }

    .hidden { display: none; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
    .footer-note { margin-top: 14px; color: var(--muted); font-size: 0.82rem; }

    @media (max-width: 900px) {
      header { align-items: flex-start; flex-direction: column; }
      .top-actions { justify-content: flex-start; }
      .coach { grid-template-columns: 1fr; }
      .coach .coach-actions { justify-content: flex-start; }
      .orientation-steps { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .orientation-next { grid-template-columns: 1fr; }
      .business-board { grid-template-columns: 1fr; }
      .tabs { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .span-3, .span-4, .span-6, .span-8 { grid-column: span 12; }
      .field-row { grid-template-columns: 1fr; gap: 2px; }
      .movement-wrap { grid-template-columns: 1fr; }
      table { font-size: 0.82rem; }
    }
  </style>
</head>
<body>
  <canvas id="field"></canvas>
  <main class="shell">
    <header>
      <div class="identity">
        <h1>AI Enterprise Command Center</h1>
        <p id="updated">Synchronizing operator surfaces...</p>
      </div>
      <div class="top-actions">
        <a class="link-button" href="/docs">API Docs</a>
        <a class="link-button" href="/dashboard/documentation-hub">Documentation Hub</a>
        <a class="link-button" href="/dashboard/demo">Demo Story</a>
        <a class="link-button" href="/metrics">Raw Metrics</a>
        <a class="link-button" href="/dashboard/graphify">Code Graph</a>
        <button id="refresh">Refresh</button>
      </div>
    </header>

    <nav class="tabs" aria-label="Dashboards">
      <button class="tab" data-view="overview" aria-selected="true">Overview</button>
      <button class="tab" data-view="execution" aria-selected="false">Execution</button>
      <button class="tab" data-view="factory" aria-selected="false">Factory</button>
      <button class="tab" data-view="problems" aria-selected="false">Problems</button>
      <button class="tab" data-view="metrics" aria-selected="false">Metrics</button>
      <button class="tab" data-view="projects" aria-selected="false">Projects</button>
      <button class="tab" data-view="graph" aria-selected="false">Graph</button>
    </nav>

    <section class="panel coach" aria-live="polite">
      <div>
        <strong id="coachTitle">Enterprise Guide</strong>
        <p id="coachMessage">Start with the Factory tab. Attach a manifesto, choose the project type, then start one project or a parallel manifesto batch. The manager will open the execution graph when work begins.</p>
      </div>
      <div class="coach-actions">
        <button id="coachPrimary">Go to Factory</button>
        <button id="coachSecondary">Open Projects</button>
      </div>
    </section>

    <section class="panel orientation" aria-live="polite">
      <div class="toolbar">
        <h2>Guided Route</h2>
        <span id="orientationStage" class="muted">Start with a client idea or manifesto.</span>
      </div>
      <div id="orientationSteps" class="orientation-steps"></div>
      <div class="orientation-next">
        <p id="orientationMessage">Step 1: go to Factory. Add a client idea or attach a manifesto. The dashboard will tell you the next action.</p>
        <button id="orientationAction">Go to Factory</button>
      </div>
    </section>

    <section id="sourceStrip" class="source-strip" aria-label="Data source freshness"></section>
    <section id="businessBoard" class="business-board" aria-label="Business decision board"></section>

    <section id="overview" class="view grid">
      <article class="panel span-3"><h2>API</h2><div id="apiStatus" class="status muted"><span class="dot"></span>Checking</div></article>
      <article class="panel span-3"><h2>Workers Online</h2><div id="workersOnline" class="metric">0</div></article>
      <article class="panel span-3"><h2>Needs Attention</h2><div id="problemJobs" class="metric">0</div></article>
      <article class="panel span-3"><h2>Projects</h2><div id="projectCount" class="metric">0</div></article>
      <article class="panel span-12"><h2>Living Enterprise Pulse</h2><div id="livingPulse" class="living-signal"></div></article>
      <article class="panel span-12">
        <div class="toolbar">
          <h2>Enterprise Ecosystem Modules</h2>
          <span class="muted">Optional growth paths. Activate only when the client or enterprise needs them.</span>
        </div>
        <div id="ecosystemModules" class="surface-graph"></div>
      </article>
      <article class="panel span-12">
        <div class="toolbar">
          <h2>Enterprise Movement Graph</h2>
          <span class="muted">Manifesto, factory, agents, telemetry, proof, blueprints, and evolution in one control panel.</span>
        </div>
        <div class="movement-wrap">
          <svg id="movementGraph" class="movement-graph" viewBox="0 0 980 430" role="img" aria-label="Enterprise movement graph"></svg>
          <div id="movementInspector" class="control-inspector mini"></div>
        </div>
      </article>
      <article class="panel span-12">
        <div class="toolbar">
          <h2>Operating Picture Signals</h2>
          <span class="muted">The same governed read model, translated into business signals.</span>
        </div>
        <div id="operatingPictureSignals" class="surface-graph"></div>
      </article>
      <article class="panel span-8"><h2>What Needs Attention</h2><div id="problemSummary" class="cards"></div></article>
      <article class="panel span-4"><h2>Start Here</h2><div id="quickLinks" class="cards"></div></article>
    </section>

    <section id="execution" class="view grid hidden">
      <article class="panel span-12">
        <div class="toolbar">
          <h2>Project Execution Control</h2>
          <span id="executionHeadline" class="muted">Manifesto projects, workflow phases, task movement, crews, events, and telemetry.</span>
        </div>
        <div class="movement-wrap">
          <svg id="executionGraph" class="movement-graph" viewBox="0 0 980 430" role="img" aria-label="Live project execution graph"></svg>
          <div id="executionInspector" class="control-inspector mini"></div>
        </div>
      </article>
      <article class="panel span-4"><h2>Parallel Projects</h2><div id="executionProjects" class="listbox"></div></article>
      <article class="panel span-4"><h2>Tasks and Crews</h2><div id="executionTasks" class="listbox"></div></article>
      <article class="panel span-4"><h2>Events and Telemetry</h2><div id="executionTelemetry" class="listbox"></div></article>
    </section>

    <section id="factory" class="view grid hidden">
      <article class="panel span-12">
        <div class="toolbar">
          <h2>Vision Clarifier</h2>
          <span class="muted">Turn unclear client input into objective, production route, proof, and market message.</span>
        </div>
        <textarea id="clientVision" placeholder="Write the client idea, even if it is not clear yet. The dashboard will structure it before project creation."></textarea>
        <div class="toolbar" style="margin-top: 10px;">
          <button id="clarifyVision">Clarify Vision</button>
          <span id="visionStatus" class="muted">Use this before creating a manifesto-driven project.</span>
        </div>
        <div id="visionGraph" class="surface-graph"></div>
      </article>
      <article class="panel span-12">
        <div class="toolbar">
          <h2>Factory Creation Graph</h2>
          <span id="factoryGraphStatus" class="muted">Manifesto to active workflow.</span>
        </div>
        <div id="factoryGraph" class="surface-graph"></div>
      </article>
      <article class="panel span-4">
        <h2>Project Type</h2>
        <div id="capabilityList" class="listbox"></div>
      </article>
      <article class="panel span-8">
        <div class="toolbar">
          <h2>Manifesto Launcher</h2>
          <a class="link-button" href="/dashboard/client-manifest-template">Download Client Manifest</a>
          <input id="manifestFile" type="file" accept="application/json,.json,text/plain,.txt,text/markdown,.md">
        </div>
        <div class="grid">
          <div class="span-6"><input id="factoryName" placeholder="Project name"></div>
          <div class="span-6"><input id="factoryBranch" placeholder="Default branch" value="main"></div>
          <div class="span-12"><input id="factoryRepo" placeholder="/home/user/projects/my-project"></div>
          <div class="span-12"><input id="factoryGithub" placeholder="GitHub repository URL, optional"></div>
          <div class="span-12"><textarea id="factoryDescription" placeholder="Project manifesto summary"></textarea></div>
        </div>
        <div class="toolbar" style="margin-top: 10px;">
          <button id="previewFactory">Preview Launch</button>
          <button id="startFactory">Start Process</button>
          <button id="startManifestBatch">Start Manifesto Batch</button>
          <button id="previewMockFactory">Preview Mock Factory</button>
          <button id="startMockFactory">Launch Mock Factory Test</button>
          <span id="factoryStatus" class="muted">Attach a manifesto or fill the fields manually.</span>
        </div>
        <div id="manifestPreview" class="mini muted">Download the client manifest, send it to the client or requesting service, then upload the completed document here.</div>
        <div id="launchContract" class="mini launch-contract">
          <strong>Launch Result</strong>
          <div class="muted">No launch has started yet. Preview or start a project to see what was created, what needs attention, and where to inspect first.</div>
        </div>
      </article>
    </section>

    <section id="problems" class="view grid hidden">
      <article class="panel span-12">
        <div class="toolbar">
          <h2>Problem Resolution Graph</h2>
          <span class="muted">Failures link to worker state, retry pressure, recovery, and improvement proposals.</span>
        </div>
        <div id="problemGraph" class="surface-graph"></div>
      </article>
      <article class="panel span-12">
        <div class="toolbar"><h2>Recovery and Work History</h2><select id="jobFilter"><option value="current">Current action</option><option value="history">Reviewed history</option><option value="">All records</option><option value="queued">Queued</option><option value="running">Running</option><option value="failed">Failed</option><option value="dead_letter">Dead Letter</option><option value="succeeded">Succeeded</option></select></div>
        <div id="jobActionStatus" class="mini muted">Select a recovery action to inspect attempts or acknowledge reviewed failures.</div>
        <div id="jobsTable"></div>
      </article>
      <article class="panel span-12">
        <div class="toolbar">
          <h2>Worker Capacity</h2>
          <select id="workerFilter" aria-label="Worker capacity view">
            <option value="current">Current capacity</option>
            <option value="history">Offline history</option>
            <option value="all">All worker signals</option>
          </select>
        </div>
        <div id="workersTable"></div>
      </article>
    </section>

    <section id="metrics" class="view grid hidden">
      <article class="panel span-12">
        <div class="toolbar">
          <h2>Telemetry Pulse Graph</h2>
          <span class="muted">Runtime signals remain active and feed calibration decisions.</span>
        </div>
        <div id="telemetryGraph" class="surface-graph"></div>
      </article>
      <article class="panel span-12"><h2>Business Telemetry</h2><div id="metricsTable"></div></article>
      <article class="panel span-12"><h2>Server Readiness</h2><div id="serverReadinessTable"></div></article>
      <article class="panel span-12"><h2>Real Infrastructure Choices</h2><div id="infrastructureChoicesTable"></div></article>
    </section>

    <section id="projects" class="view grid hidden">
      <article class="panel span-12"><h2>Projects</h2><div id="projectsTable"></div></article>
      <article class="panel span-12">
        <div class="toolbar">
          <h2>Project Intelligence Graph</h2>
          <div>
            <select id="projectSelect"></select>
            <button id="loadProject">Open Project Dashboard</button>
          </div>
        </div>
        <div id="projectGraph"></div>
        <div id="phaseDetail"></div>
      </article>
      <article class="panel span-12"><h2>Workflow Lookup</h2><div class="toolbar"><input id="workflowId" placeholder="Workflow ID"><button id="loadWorkflow">Load</button></div><div id="workflowDetail"></div></article>
    </section>

    <section id="graph" class="view grid hidden">
      <article class="panel span-12">
        <div class="toolbar">
          <h2>Blueprint Graph Hub</h2>
          <span class="muted">Code graph, ecosystem graph, evidence graph, decomposition graph, and project blueprints.</span>
        </div>
        <div id="blueprintGraph" class="surface-graph"></div>
      </article>
      <article class="panel span-6"><h2>Architecture Graph</h2><p class="muted">The code graph is ready when graphify output is mounted.</p><div class="cards"><a class="link-button" href="/dashboard/graphify">Open Code Graph</a><a class="link-button" href="/docs">Open API Docs</a></div></article>
      <article class="panel span-6">
        <h2>Authenticated Graph Context</h2>
        <p class="muted">Use this panel to confirm whether enterprise relationships and project proof are linked for the current work.</p>
        <div class="grid">
          <div class="span-12"><input id="graphOrganizationId" placeholder="Current organization context"></div>
          <div class="span-12"><input id="graphProjectId" placeholder="Current project context"></div>
        </div>
        <div class="toolbar" style="margin-top: 10px;">
          <button id="checkEcosystemGraph">Check Ecosystem</button>
          <button id="checkEvidenceGraph">Check Evidence</button>
        </div>
        <div id="authenticatedGraphStatus" class="mini muted">The dashboard will use the current organization and project when you check a graph.</div>
      </article>
      <article class="panel span-6"><h2>Development Map</h2><div id="graphStatus" class="mini muted">Graphify output is available when graphify-out/graph.html is mounted.</div></article>
    </section>

    <p class="footer-note">Local dashboard context loads development graph authority and IDs automatically; production still requires trusted identity and durable grants.</p>
  </main>

  <script>
    let actorHeaders = {
      "X-Actor-ID": "local-admin",
      "X-Actor-Type": "human",
      "X-Actor-Role": "admin"
    };
    const state = { jobs: [], workers: [], projects: [], metrics: {}, telemetrySummary: null, operatingPicture: null, dashboardManager: null, serverReadiness: null, infrastructureChoices: null, context: null, sources: {} };
    let loadedManifestDocument = null;
    let selectedMovementNode = "manifesto";
    let selectedExecutionNode = "factory";
    let orientationIndex = 0;
    const orientationFlow = [
      { key: "idea", title: "Idea", detail: "Listen or attach manifesto", target: "factory", action: "Go to Factory" },
      { key: "direction", title: "Direction", detail: "Choose the version", target: "factory", action: "Clarify Vision" },
      { key: "launch", title: "Launch", detail: "Start project or batch", target: "factory", action: "Start Process" },
      { key: "execution", title: "Execution", detail: "Open live execution", target: "execution", action: "Open Execution" },
      { key: "proof", title: "Proof", detail: "Check telemetry and issues", target: "metrics", action: "Open Metrics" },
      { key: "demo", title: "Demo", detail: "Show product story", target: "demo", action: "Open Demo" }
    ];
    const capabilities = [
      ["requirements_engineering", "Requirements Engineering"],
      ["architecture_design", "Architecture Design"],
      ["ai_software_development", "AI Software Development"],
      ["multi_agent_orchestration", "Multi-Agent Orchestration"],
      ["automated_testing", "Automated Testing"],
      ["security_compliance", "Security & Compliance"],
      ["data_engineering", "Data Engineering"],
      ["ai_ml_solutions", "AI/ML Solutions"],
      ["web_mobile_app_development", "Web & Mobile App Development"],
      ["api_integration_development", "API & Integration Development"],
      ["devops_infrastructure", "DevOps & Infrastructure"],
      ["monitoring_observability", "Monitoring & Observability"],
      ["dashboards_reporting", "Dashboards & Reporting"],
      ["user_tenant_management", "User & Tenant Management"],
      ["chatbots_ai_assistants", "Chatbots & AI Assistants"],
      ["voice_modules", "Voice Assistants & Modules"],
      ["rpa_process_automation", "RPA & Process Automation"],
      ["document_processing", "Document Processing"],
      ["globalization", "Multi-Language & Globalization"],
      ["scalability_performance", "Scalability & Performance"]
    ];
    let selectedCapability = capabilities[0][0];

    function byId(id) { return document.getElementById(id); }
    function esc(value) {
      return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[char]));
    }
    async function json(url, options = {}) {
      const response = await fetch(url, options);
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      return response.json();
    }
    async function text(url) {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      return response.text();
    }

    function table(rows, columns, emptyMessage = "No evidence has been recorded for this section yet.") {
      if (!rows.length) return `<div class="mini muted">${esc(emptyMessage)}</div>`;
      return `<table><thead><tr>${columns.map(col => `<th>${esc(col.label)}</th>`).join("")}</tr></thead><tbody>` +
        rows.map(row => `<tr>${columns.map(col => `<td>${esc(col.value(row))}</td>`).join("")}</tr>`).join("") +
        `</tbody></table>`;
    }

    function listbox(rows, renderItem, emptyMessage = "No live records are available for this section yet.") {
      if (!rows.length) return `
        <div class="listbox">
          <div class="list-item empty-state">
            <div>
              <div class="list-title">Waiting for live evidence</div>
              <div class="list-meta">${esc(emptyMessage)}</div>
              <div class="list-meta">Next: follow the panel guidance, then refresh. When the factory creates data, it will appear here automatically.</div>
            </div>
            <span class="pill info">ready</span>
          </div>
        </div>
      `;
      return `<div class="listbox">${rows.map(renderItem).join("")}</div>`;
    }

    function countSentence(count, singular, plural = `${singular}s`) {
      const word = Number(count) === 1 ? singular : plural;
      return `${count} ${word}`;
    }

    function coach(title, message, primary = ["Go to Factory", "factory"], secondary = ["Open Projects", "projects"]) {
      byId("coachTitle").textContent = title;
      byId("coachMessage").textContent = message;
      byId("coachPrimary").textContent = primary[0];
      byId("coachPrimary").dataset.target = primary[1];
      byId("coachSecondary").textContent = secondary[0];
      byId("coachSecondary").dataset.target = secondary[1];
    }

    function goTarget(target) {
      if (target === "demo") {
        window.location.href = "/dashboard/demo";
        return;
      }
      switchView(target);
    }

    function setOrientation(index, message = "") {
      orientationIndex = Math.max(0, Math.min(index, orientationFlow.length - 1));
      const current = orientationFlow[orientationIndex];
      byId("orientationStage").textContent = `${current.title}: ${current.detail}`;
      byId("orientationMessage").textContent = message || `Next: ${current.detail}.`;
      byId("orientationAction").textContent = current.action;
      byId("orientationAction").dataset.target = current.target;
      byId("orientationSteps").innerHTML = orientationFlow.map((step, index) => `
        <div class="orientation-step ${index < orientationIndex ? "done" : ""} ${index === orientationIndex ? "current" : ""}">
          <strong>${esc(index + 1)}. ${esc(step.title)}</strong>
          <span>${esc(step.detail)}</span>
        </div>
      `).join("");
    }

    function sourceStatus(result, label, target, summary) {
      if (result.status === "fulfilled") {
        return { label, target, status: "fresh", className: "ok", detail: `${summary}. Updated ${new Date().toLocaleTimeString()}` };
      }
      return {
        label,
        target,
        status: "connection needs attention",
        className: "bad",
        detail: `${summary}. Open this panel, refresh, and verify API readiness before making delivery decisions.`,
      };
    }

    function managerSectionSource(section, target) {
      if (!section) {
        return {
          label: "Source",
          target,
          status: "not_observed",
          className: "info",
          detail: "This source section is not reported by the dashboard manager yet.",
        };
      }
      const status = section.freshness || section.state || "not_observed";
      const className = section.state === "unavailable"
        ? "bad"
        : section.state === "stale"
          ? "warn"
          : section.state === "empty"
            ? "info"
            : "ok";
      const age = section.freshness_age_seconds == null
        ? "Waiting for the first source timestamp"
        : `${Math.round(section.freshness_age_seconds)}s old`;
      const staleWindow = section.stale_after_seconds == null
        ? ""
        : ` · stale after ${section.stale_after_seconds}s`;
      return {
        label: section.source,
        target,
        status,
        className,
        detail: `${section.operator_action || section.empty_reason || "Use this section for the current operating picture."} ${age}${staleWindow}`,
      };
    }

    function dashboardManagerSources(fallbackSources) {
      const sections = state.dashboardManager?.sections;
      if (!sections) return fallbackSources;
      return {
        ...fallbackSources,
        projects: managerSectionSource(sections.projects, "projects"),
        jobs: managerSectionSource(sections.jobs, "problems"),
        workers: managerSectionSource(sections.workers, "problems"),
        metrics: managerSectionSource(sections.telemetry, "metrics"),
        manager: managerSectionSource(sections.graph, "execution"),
        workflows: managerSectionSource(sections.workflows, "projects"),
      };
    }

    function isProblemJob(job) {
      return ["failed", "dead_letter", "abandoned"].includes(job.status);
    }

    function isAcknowledgedJob(job) {
      return job.operator_resolution && job.operator_resolution.state === "acknowledged";
    }

    function unresolvedProblemJobs() {
      return state.jobs.filter(job => isProblemJob(job) && !isAcknowledgedJob(job));
    }

    function renderSourceStrip() {
      const sources = Object.values(state.sources);
      byId("sourceStrip").innerHTML = sources.map(source => `
        <button class="source-card" data-source-target="${esc(source.target)}">
          <strong class="${esc(source.className)}">${esc(source.label)} · ${esc(source.status)}</strong>
          <span>${esc(source.detail)}</span>
        </button>
      `).join("");
      document.querySelectorAll(".source-card").forEach(item => {
        item.addEventListener("click", () => goTarget(item.dataset.sourceTarget));
      });
    }

    function businessBrief() {
      if (state.operatingPicture) {
        const headline = state.operatingPicture.headline;
        const firstAction = state.operatingPicture.recommendations?.[0];
        const target = firstAction?.next_action?.toLowerCase().includes("problem")
          ? "problems"
          : firstAction?.next_action?.toLowerCase().includes("project")
            ? "projects"
            : "factory";
        const unresolved = state.operatingPicture.counts?.unresolved_problem_jobs ?? 0;
        const online = state.operatingPicture.status_counts?.workers?.online ?? state.workers.filter(worker => worker.status === "online").length;
        const nextMessage = firstAction ? firstAction.message : headline.business_meaning;
        return {
          health: headline.state.replace(/_/g, " "),
          value: headline.summary,
          risk: unresolved
            ? `${unresolved} issue(s) need review before scaling parallel work.`
            : headline.business_meaning,
          next: [
            firstAction?.next_action || "Open Projects",
            target,
            nextMessage
          ],
          online
        };
      }
      const online = state.workers.filter(worker => worker.status === "online").length;
      const failed = unresolvedProblemJobs().length;
      const moving = state.jobs.filter(job => ["queued", "running"].includes(job.status)).length;
      const staleSources = Object.values(state.sources).filter(source => source.status !== "fresh").length;
      const health = staleSources ? "Data is incomplete" : failed ? "Action required" : "Factory is stable";
      const value = state.projects.length
        ? `${countSentence(state.projects.length, "project")} visible. ${countSentence(moving, "work item")} moving or waiting.`
        : "No active project is visible. Start with a manifesto to create business value.";
      const risk = failed
        ? `${failed} issue(s) need review. Open Problems and follow the recommended recovery path.`
        : staleSources
          ? `${staleSources} data source(s) need attention. Refresh and confirm readiness before making delivery decisions.`
          : "No urgent delivery risk is visible. Continue creating or inspecting projects.";
      const next = failed
        ? ["Resolve Issues", "problems", "Review failed work first."]
        : state.projects.length
          ? ["Inspect Projects", "projects", "Open a project graph and check phase, crew, proof, and remaining work."]
          : ["Create Project", "factory", "Attach a manifesto and start the first governed workflow."];
      return { health, value, risk, next, online };
    }

    function renderBusinessBoard() {
      const brief = businessBrief();
      const cards = [
        ["Business State", brief.health, `${brief.online} worker(s) online. The board refreshes every 15 seconds.`, "overview"],
        ["Value in Motion", brief.value, "Use this to see whether delivery capacity is producing outcomes.", "projects"],
        ["Risk and Attention", brief.risk, "Fix risk before scaling parallel work.", brief.next[1]],
        ["Recommended Next Move", brief.next[2], "This is the best next action from the current live state.", brief.next[1]]
      ];
      byId("businessBoard").innerHTML = cards.map(([title, message, effect, target], index) => `
        <article class="business-card">
          <div>
            <strong>${esc(title)}</strong>
            <p>${esc(message)}</p>
            <p>${esc(effect)}</p>
          </div>
          <button class="business-open" data-target="${esc(target)}">${index === 3 ? esc(brief.next[0]) : "Open"}</button>
        </article>
      `).join("");
      document.querySelectorAll(".business-open").forEach(item => {
        item.addEventListener("click", () => goTarget(item.dataset.target));
      });
      coach("Decision Ready", `${brief.health}. ${brief.next[2]}`, [brief.next[0], brief.next[1]], ["Open Overview", "overview"]);
    }

    function renderEcosystemModules() {
      const hasProjects = state.projects.length > 0;
      const hasProblems = unresolvedProblemJobs().length > 0;
      const modules = [
        { title: "Listen and Clarify", detail: "Use when the client idea is weak or emotional.", idea: "Create practical, growth, and visionary options.", effect: "Turns poor input into a choice the client can understand.", signal: "optional", kind: "info", action: "factory" },
        { title: "Vision Presentation", detail: "Use when the client must see the future before buying.", idea: "Prepare objective, proof, route, and market message.", effect: "Improves trust and makes the offer easier to sell.", signal: "optional", kind: "ok", action: "factory" },
        { title: "ISO and Compliance", detail: "Use when governance, certification, or audit readiness matters.", idea: "Create evidence, controls, gaps, and corrective actions.", effect: "Connects delivery to business assurance.", signal: "optional", kind: "warn", action: "factory" },
        { title: "Verification and Debug", detail: "Use when quality or failures are blocking progress.", idea: "Inspect defects, test, fix, and convert lessons into patterns.", effect: hasProblems ? "Recommended now: issues are visible." : "Prevents repeated failures later.", signal: hasProblems ? "recommended" : "optional", kind: hasProblems ? "bad" : "info", action: "problems" },
        { title: "Production Route", detail: "Use when the client asks how the idea becomes real.", idea: "Show steps from manifesto to workflow, proof, and release.", effect: hasProjects ? "Recommended now: projects exist." : "Clarifies delivery before work starts.", signal: hasProjects ? "recommended" : "optional", kind: hasProjects ? "ok" : "info", action: "projects" },
        { title: "Blueprint Marketplace", detail: "Use when repeated work should become a product asset.", idea: "Promote proven workflows and crew patterns into templates.", effect: "Creates brand value and reusable enterprise capability.", signal: "future", kind: "ok", action: "graph" }
      ];
      renderSurfaceNodes("ecosystemModules", modules);
    }

    function switchView(viewName) {
      const tab = document.querySelector(`[data-view="${viewName}"]`);
      if (!tab) return;
      document.querySelectorAll(".tab").forEach(item => item.setAttribute("aria-selected", "false"));
      document.querySelectorAll(".view").forEach(view => view.classList.add("hidden"));
      tab.setAttribute("aria-selected", "true");
      byId(viewName).classList.remove("hidden");
      const nextHash = `#${viewName}`;
      if (window.location.hash !== nextHash) {
        history.replaceState(null, "", `${window.location.pathname}${window.location.search}${nextHash}`);
      }
    }

    function movementModel() {
      const problemCount = unresolvedProblemJobs().length;
      const online = state.workers.filter(worker => worker.status === "online").length;
      const metricCount = Object.keys(state.metrics).length;
      return [
        { id: "manifesto", label: "Manifesto", subtitle: "project intent", x: 36, y: 38, target: "factory", details: "Attach one or more manifestos, select a project type, and start the process from the Factory tab." },
        { id: "factory", label: "Factory", subtitle: "parallel launch", x: 258, y: 38, target: "factory", details: "Creates projects, starts workflows, and keeps the enterprise active while multiple plans run in parallel." },
        { id: "projects", label: "Projects", subtitle: `${state.projects.length} active`, x: 480, y: 38, target: "projects", details: "The project switchboard opens each project dashboard with phase graph, life signals, estimates, and remaining steps." },
        { id: "agents", label: "Agent Crew", subtitle: `${online} workers online`, x: 702, y: 38, target: "problems", details: "Specialist crews execute requirements, architecture, planning, development, testing, review, integration, recovery, and governance work." },
        { id: "telemetry", label: "Telemetry", subtitle: `${metricCount} signals`, x: 148, y: 176, target: "metrics", details: "Metrics stay active so performance, queues, runtime health, and operating pressure are visible continuously." },
        { id: "calibration", label: "Calibration", subtitle: "quality gates", x: 370, y: 176, target: "projects", details: "Calibration checks manifest integrity, workflow phase alignment, error follow-up, reuse capture, and evidence quality." },
        { id: "errors", label: "Errors", subtitle: `${problemCount} followed`, x: 592, y: 176, target: "problems", details: "Problems are surfaced as first-class operating signals with worker/job context and improvement recommendations." },
        { id: "proof", label: "Economic Proof", subtitle: "viability", x: 814, y: 176, target: "projects", details: "Each project exposes avoided manual effort, reusable assets, automation units, risk signals, and viability basis." },
        { id: "blueprints", label: "Blueprints", subtitle: "reusable patterns", x: 258, y: 314, target: "graph", details: "Successful structures become workflow, specialist-crew, and economic-proof patterns for future projects." },
        { id: "evolution", label: "Evolution", subtitle: "future factory", x: 592, y: 314, target: "graph", details: "Telemetry and reusable blueprints feed the next generation of projects, agents, templates, and enterprise operating maturity." }
      ];
    }

    function renderMovementGraph() {
      const svg = byId("movementGraph");
      if (!svg) return;
      const nodes = movementModel();
      const byNode = Object.fromEntries(nodes.map(node => [node.id, node]));
      const edges = [
        ["manifesto", "factory"], ["factory", "projects"], ["projects", "agents"],
        ["agents", "telemetry"], ["telemetry", "calibration"], ["calibration", "errors"],
        ["errors", "proof"], ["proof", "blueprints"], ["blueprints", "evolution"],
        ["evolution", "manifesto"], ["projects", "calibration"], ["telemetry", "proof"]
      ];
      const edgeMarkup = edges.map(([from, to], index) => {
        const a = byNode[from];
        const b = byNode[to];
        return `<line class="movement-edge ${index < 9 ? "pulse" : ""}" x1="${a.x + 136}" y1="${a.y + 38}" x2="${b.x}" y2="${b.y + 38}"></line>`;
      }).join("");
      const nodeMarkup = nodes.map(node => `
        <g class="movement-node ${node.id === selectedMovementNode ? "selected" : ""}" data-node="${esc(node.id)}" data-target="${esc(node.target)}">
          <rect x="${node.x}" y="${node.y}" width="136" height="76"></rect>
          <text x="${node.x + 14}" y="${node.y + 31}">${esc(node.label)}</text>
          <text class="node-subtitle" x="${node.x + 14}" y="${node.y + 53}">${esc(node.subtitle)}</text>
        </g>
      `).join("");
      svg.innerHTML = `
        <defs>
          <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="rgba(93, 184, 255, 0.62)"></polygon>
          </marker>
        </defs>
        ${edgeMarkup}
        ${nodeMarkup}
      `;
      svg.querySelectorAll(".movement-node").forEach(node => {
        node.addEventListener("click", () => {
          selectedMovementNode = node.dataset.node;
          renderMovementGraph();
          switchView(node.dataset.target);
          coach(
            `${byNode[selectedMovementNode].label} Selected`,
            byNode[selectedMovementNode].details,
            [`Open ${byNode[selectedMovementNode].label}`, node.dataset.target],
            ["Review Projects", "projects"]
          );
        });
      });
      const selected = byNode[selectedMovementNode] || nodes[0];
      byId("movementInspector").innerHTML = `
        <strong>${esc(selected.label)}</strong>
        <div class="muted">${esc(selected.details)}</div>
        <div class="mini">
          <strong>Why it matters</strong>
          <div class="muted">This keeps the enterprise understandable: the operator sees what is being created, what is moving, what is blocked, what improved, and what becomes reusable.</div>
        </div>
        <div class="mini">
          <strong>Measurable effect</strong>
          <div class="muted">${esc(countSentence(state.projects.length, "project"))}, ${esc(countSentence(state.jobs.length, "job signal"))}, ${esc(countSentence(Object.keys(state.metrics).length, "telemetry signal"))}, ${esc(countSentence(state.workers.filter(worker => worker.status === "online").length, "online worker"))}.</div>
        </div>
        <div class="signal">
          <div class="list-item"><div><div class="list-title">Creation</div><div class="list-meta">Manifesto becomes governed project workflow.</div></div><span class="pill info">live</span></div>
          <div class="list-item"><div><div class="list-title">Movement</div><div class="list-meta">Workers, jobs, telemetry, and phase transitions update the graph.</div></div><span class="pill ok">tracked</span></div>
          <div class="list-item"><div><div class="list-title">Evolution</div><div class="list-meta">Blueprints and improvements are captured for the next project.</div></div><span class="pill ok">reusable</span></div>
        </div>
        <button data-open-node="${esc(selected.target)}">Open ${esc(selected.label)} Surface</button>
      `;
      byId("movementInspector").querySelector("button").addEventListener("click", event => {
        switchView(event.currentTarget.dataset.openNode);
      });
    }

    function executionNodeModel() {
      const manager = state.dashboardManager;
      if (!manager || !manager.projects) {
        return {
          nodes: [{
            id: "factory",
            label: "Manifesto Factory",
            subtitle: "waiting",
            kind: "factory",
            status: "waiting_for_manifesto",
            x: 38,
            y: 46,
            details: "Attach a manifesto in Factory to create governed projects and live execution proof."
          }],
          edges: []
        };
      }
      const nodes = [{
        id: "factory",
        label: "Manifesto Factory",
        subtitle: `${manager.projects.length} projects`,
        kind: "factory",
        status: manager.headline.state,
        x: 38,
        y: 46,
        details: manager.headline.business_meaning
      }];
      const edges = [];
      manager.projects.slice(0, 5).forEach((project, index) => {
        const phaseDetail = project.phase_detail || {};
        const y = 42 + index * 74;
        const projectId = `project:${project.id}`;
        const workflowId = `workflow:${project.id}`;
        const crewId = `crew:${project.id}`;
        const telemetryId = `telemetry:${project.id}`;
        nodes.push(
          {
            id: projectId,
            label: project.name,
            subtitle: `${phaseDetail.label || project.phase} · ${phaseDetail.confidence || project.tasks.active + " active"}`,
            kind: "project",
            status: project.state,
            x: 218,
            y,
            project
          },
          {
            id: workflowId,
            label: phaseDetail.label || project.phase,
            subtitle: project.workflow ? humanStatus(project.workflow.state) : "Not started",
            kind: "workflow",
            status: project.workflow ? project.workflow.state : "not_started",
            x: 406,
            y,
            project
          },
          {
            id: crewId,
            label: "Crew",
            subtitle: `${project.crews.length} signal(s)`,
            kind: "crew",
            status: project.crews.length || project.tasks.active ? "active" : "standby",
            x: 594,
            y,
            project
          },
          {
            id: telemetryId,
            label: "Telemetry",
            subtitle: `${project.telemetry.event_count} event(s)`,
            kind: "telemetry",
            status: project.telemetry.signal,
            x: 782,
            y,
            project
          }
        );
        edges.push(
          ["factory", projectId],
          [projectId, workflowId],
          [workflowId, crewId],
          [crewId, telemetryId],
          [telemetryId, projectId]
        );
      });
      return { nodes, edges };
    }

    function phaseIssueCount(project) {
      const detail = project.phase_detail || {};
      return (detail.current_issues || []).length;
    }

    function phaseHistoryCount(project) {
      const detail = project.phase_detail || {};
      return (detail.historical_issues || []).length;
    }

    function phaseEvidenceText(project) {
      const evidence = project.phase_detail?.completed_evidence || [];
      return evidence.length ? evidence.join(", ") : "No completed phase evidence yet.";
    }

    function renderPhaseDetailRows(project) {
      const detail = project.phase_detail || {};
      return `
        <div class="list-item">
          <div><div class="list-title">Phase confidence</div><div class="list-meta">${esc(detail.remaining_work || "Start or relink the workflow before treating this phase as live.")}</div></div>
          <span class="pill ${statusClass(detail.confidence || "early estimate")}">${esc(humanStatus(detail.confidence || "early estimate"))}</span>
        </div>
        <div class="list-item">
          <div><div class="list-title">Owner crew</div><div class="list-meta">${esc(phaseEvidenceText(project))}</div></div>
          <span class="pill info">${esc(detail.owner_crew || "workflow engine")}</span>
        </div>
        <div class="list-item">
          <div><div class="list-title">Issue split</div><div class="list-meta">${esc(phaseIssueCount(project))} current issue(s), ${esc(phaseHistoryCount(project))} reviewed history item(s).</div></div>
          <span class="pill ${phaseIssueCount(project) ? "bad" : "ok"}">${esc(phaseIssueCount(project) ? "needs action" : "clear")}</span>
        </div>
      `;
    }

    function renderExecutionInspector(node) {
      const project = node.project;
      if (!project) {
        byId("executionInspector").innerHTML = `
          <strong>${esc(node.label)}</strong>
          <div class="muted">${esc(node.details || "The manifesto factory creates projects and connects workflows, crews, events, and telemetry.")}</div>
          <div class="signal">
            <div class="list-item"><div><div class="list-title">Next action</div><div class="list-meta">Open Factory, attach a manifesto, and start the governed process.</div></div><span class="pill info">start</span></div>
          </div>
          <button data-execution-target="factory">Open Factory</button>
        `;
        byId("executionInspector").querySelector("button").addEventListener("click", () => switchView("factory"));
        return;
      }
      byId("executionInspector").innerHTML = `
        <strong>${esc(project.name)}</strong>
        <div class="muted">${esc(project.human_summary)}</div>
        <div class="signal">
          <div class="list-item"><div><div class="list-title">Where we are</div><div class="list-meta">${esc(project.phase)} · ${esc(project.next_action)}</div></div><span class="pill ${statusClass(project.state)}">${esc(humanStatus(project.state))}</span></div>
          ${renderPhaseDetailRows(project)}
          <div class="list-item"><div><div class="list-title">Tasks</div><div class="list-meta">${esc(project.tasks.done)} done, ${esc(project.tasks.active)} active, ${esc(project.tasks.standby)} standby, ${esc(project.tasks.problems)} problem.</div></div><span class="pill info">${esc(project.tasks.total)} total</span></div>
          <div class="list-item"><div><div class="list-title">Crew</div><div class="list-meta">${esc(project.crews[0]?.assignment || "No active crew signal yet.")}</div></div><span class="pill ${project.crews.length ? "ok" : "info"}">${esc(project.crews.length)} signal(s)</span></div>
          <div class="list-item"><div><div class="list-title">Telemetry</div><div class="list-meta">${esc(project.telemetry.job_signal_count)} job signal(s), ${esc(project.telemetry.event_count)} event(s), ${esc(project.telemetry.work_package_count)} work package(s).</div></div><span class="pill ${statusClass(project.telemetry.signal)}">${esc(humanStatus(project.telemetry.signal))}</span></div>
        </div>
        <button data-project-id="${esc(project.id)}">Open Full Project Graph</button>
      `;
      byId("executionInspector").querySelector("button").addEventListener("click", event => {
        switchView("projects");
        byId("projectSelect").value = event.currentTarget.dataset.projectId;
        loadProjectDashboard(event.currentTarget.dataset.projectId);
      });
    }

    function renderExecutionDashboard() {
      const manager = state.dashboardManager;
      const headline = manager ? manager.headline : null;
      byId("executionHeadline").textContent = headline
        ? `${headline.summary} ${headline.business_meaning}`
        : "Execution manager is loading project, task, crew, event, and telemetry signals.";
      const svg = byId("executionGraph");
      const model = executionNodeModel();
      const byNode = Object.fromEntries(model.nodes.map(node => [node.id, node]));
      const edgeMarkup = model.edges.map(([from, to]) => {
        const a = byNode[from];
        const b = byNode[to];
        return `<line class="movement-edge pulse" x1="${a.x + 136}" y1="${a.y + 38}" x2="${b.x}" y2="${b.y + 38}"></line>`;
      }).join("");
      const nodeMarkup = model.nodes.map(node => `
        <g class="movement-node ${node.id === selectedExecutionNode ? "selected" : ""}" data-node="${esc(node.id)}">
          <rect x="${node.x}" y="${node.y}" width="136" height="66"></rect>
          <text x="${node.x + 12}" y="${node.y + 28}">${esc(node.label).slice(0, 22)}</text>
          <text class="node-subtitle" x="${node.x + 12}" y="${node.y + 49}">${esc(node.subtitle || humanStatus(node.status)).slice(0, 24)}</text>
        </g>
      `).join("");
      svg.innerHTML = `
        <defs>
          <marker id="executionArrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="rgba(93, 184, 255, 0.62)"></polygon>
          </marker>
        </defs>
        ${edgeMarkup}
        ${nodeMarkup}
      `;
      svg.querySelectorAll(".movement-node").forEach(node => {
        node.addEventListener("click", () => {
          selectedExecutionNode = node.dataset.node;
          renderExecutionDashboard();
        });
      });
      renderExecutionInspector(byNode[selectedExecutionNode] || model.nodes[0]);
      const projects = manager?.projects || [];
      byId("executionProjects").innerHTML = listbox(projects, project => `
        <button class="list-item execution-project-open" data-execution-node="project:${esc(project.id)}">
          <div>
            <div class="list-title">${esc(project.name)}</div>
            <div class="list-meta">${esc(project.human_summary)}</div>
            <div class="list-meta">Phase: ${esc(project.phase_detail?.label || project.phase)} · confidence ${esc(project.phase_detail?.confidence || "early estimate")} · owner ${esc(project.phase_detail?.owner_crew || "workflow engine")}</div>
          </div>
          <span class="pill ${statusClass(project.phase_detail?.confidence || project.state)}">${esc(humanStatus(project.phase_detail?.confidence || project.state))}</span>
        </button>
      `, "No manifesto project is visible yet. Open Factory, attach a manifesto, and start a governed project.");
      document.querySelectorAll(".execution-project-open").forEach(item => {
        item.addEventListener("click", () => {
          selectedExecutionNode = item.dataset.executionNode;
          renderExecutionDashboard();
        });
      });
      byId("executionTasks").innerHTML = listbox(projects, project => `
        <div class="list-item">
          <div>
            <div class="list-title">${esc(project.name)}</div>
            <div class="list-meta">Done ${esc(project.tasks.done)} · active ${esc(project.tasks.active)} · standby ${esc(project.tasks.standby)} · problems ${esc(project.tasks.problems)}</div>
            <div class="list-meta">Evidence: ${esc(phaseEvidenceText(project))}</div>
            <div class="list-meta">Remaining: ${esc(project.phase_detail?.remaining_work || "Continue the guided workflow.")}</div>
          </div>
          <span class="pill ${phaseIssueCount(project) ? "bad" : "info"}">${esc(phaseIssueCount(project))} current</span>
        </div>
      `, "No tasks have been created yet. Start the workflow so crews can produce work signals.");
      const telemetryRows = projects.flatMap(project =>
        (project.recent_events.length ? project.recent_events : [{ event_type: "No event yet", summary: "Project is waiting for more execution evidence.", created_at: "" }])
          .slice(0, 2)
          .map(event => ({ project, event }))
      );
      byId("executionTelemetry").innerHTML = listbox(telemetryRows, row => `
        <div class="list-item">
          <div><div class="list-title">${esc(row.project.name)}</div><div class="list-meta">${esc(row.event.summary)}</div><div class="list-meta">${esc(row.event.created_at || "No timestamp yet")}</div></div>
          <span class="pill ${statusClass(row.project.telemetry.signal)}">${esc(humanStatus(row.project.telemetry.signal))}</span>
        </div>
      `, "No event telemetry is visible yet. Project events will appear as workflow and crew activity progresses.");
    }

    function renderSurfaceNodes(containerId, nodes) {
      const container = byId(containerId);
      if (!container) return;
      container.innerHTML = nodes.map(node => `
        <button class="surface-node" data-action="${esc(node.action || "")}">
          <strong>${esc(node.title)}</strong>
          <small>${esc(node.detail)}</small>
          <div class="human-copy">
            <span><b>Idea:</b> ${esc(node.idea || "Use this signal to decide the next controlled action.")}</span>
            <span><b>Effect:</b> ${esc(node.effect || "Improves visibility, reduces operator guesswork, and preserves evidence.")}</span>
          </div>
          <span class="pill ${esc(node.kind || "info")}">${esc(node.signal)}</span>
        </button>
      `).join("");
      container.querySelectorAll(".surface-node").forEach(node => {
        node.addEventListener("click", () => {
          const model = nodes.find(item => item.action === node.dataset.action);
          if (model) {
            coach(
              model.title,
              `${model.detail} Idea: ${model.idea || "Use this signal for the next controlled action"}. Effect: ${model.effect || "better visibility and reduced operator delay"}.`,
              ["Continue Here", model.action || "factory"],
              ["Open Projects", "projects"]
            );
          }
          const action = node.dataset.action;
          if (action === "manifest") byId("manifestFile").click();
          if (action === "name") byId("factoryName").focus();
          if (action === "start") byId("startFactory").focus();
          if (action === "batch") byId("startManifestBatch").focus();
          if (action === "previewMock") previewMockFactoryTest().catch(error => {
            byId("factoryStatus").textContent = friendlyLaunchError(error);
          });
          if (action === "mock") startMockFactoryTest().catch(error => {
            byId("factoryStatus").textContent = friendlyLaunchError(error);
          });
          if (action === "factory") goTarget("factory");
          if (action === "execution") goTarget("execution");
          if (action === "projects") goTarget("projects");
          if (action === "problems") goTarget("problems");
          if (action === "metrics") goTarget("metrics");
          if (action === "graphify") window.location.href = "/dashboard/graphify";
          if (action === "foundry") window.location.href = "/dashboard/project-foundry-core";
          if (action === "ecosystem" || action === "evidence") {
            switchView("graph");
            byId("authenticatedGraphStatus").innerHTML = `<strong>Ready to check</strong><div class="muted">The dashboard has loaded the current organization${action === "evidence" ? " and project" : ""}. Press the check button to see whether records are linked yet.</div>`;
          }
        });
      });
    }

    function capabilityLabel() {
      const found = capabilities.find(([key]) => key === selectedCapability);
      return found ? found[1] : "Enterprise Project";
    }

    function visionVersions(rawVision, type) {
      const input = rawVision || "Create a clear enterprise product from a client idea.";
      return [
        {
          name: "Practical Version",
          objective: `Deliver a focused ${type.toLowerCase()} solution for the clearest client need.`,
          route: "Define scope, create the project, execute the governed workflow, verify quality, then prepare a production handoff.",
          proof: "Show working output, test evidence, issue status, and reusable delivery notes.",
          market: `A reliable ${type} service for clients who need controlled delivery and visible progress.`,
          best_for: "Fast validation with low risk.",
          source: input
        },
        {
          name: "Growth Version",
          objective: `Create a reusable ${type.toLowerCase()} module that can serve multiple clients or departments.`,
          route: "Clarify the offer, build the first module, capture reusable blueprints, then package it as a repeatable service.",
          proof: "Measure reusable patterns, avoided manual work, quality checks, and client-ready reporting.",
          market: `A scalable AI Enterprise capability that turns one client idea into a repeatable business offer.`,
          best_for: "Building a productized service.",
          source: input
        },
        {
          name: "Visionary Version",
          objective: `Transform the rough idea into an intelligent operating capability with specialist agents, telemetry, proof, and continuous improvement.`,
          route: "Map the client vision, launch parallel work, coordinate specialist crews, prove value live, then evolve the result into future templates.",
          proof: "Show the idea becoming reality through project graph movement, crew activity, telemetry, economic proof, and blueprints.",
          market: `An AI Enterprise factory experience where clients see their idea become governed production work in real time.`,
          best_for: "Strong presentation, differentiation, and long-term platform value.",
          source: input
        }
      ];
    }

    function applyVisionVersion(version) {
      byId("factoryName").value = version.name.replace("Version", capabilityLabel()).trim();
      byId("factoryDescription").value = [
        `Client vision: ${version.source}`,
        `Chosen direction: ${version.name}`,
        `Objective: ${version.objective}`,
        `Production route: ${version.route}`,
        `Proof: ${version.proof}`,
        `Market message: ${version.market}`
      ].join("\n\n");
      byId("visionStatus").textContent = `${version.name} selected. Start the process when repository details are ready.`;
      setOrientation(2, `${version.name} selected. Check repository details, then start the project or manifesto batch.`);
      coach(
        "Client Direction Selected",
        `${version.name} is now prepared as a project brief. Verify repository details, then start the governed workflow.`,
        ["Start Project", "factory"],
        ["Open Projects", "projects"]
      );
    }

    function clarifyVision() {
      const rawVision = byId("clientVision").value.trim();
      const type = capabilityLabel();
      const versions = visionVersions(rawVision, type);
      byId("visionStatus").textContent = "Three directions created. Select the one the client understands and wants.";
      setOrientation(1, "Three directions are ready. Choose practical, growth, or visionary before creating the project.");
      byId("visionGraph").innerHTML = versions.map((version, index) => `
        <button class="surface-node vision-choice" data-version="${index}">
          <strong>${esc(version.name)}</strong>
          <small>${esc(version.objective)}</small>
          <div class="human-copy">
            <span><b>Route:</b> ${esc(version.route)}</span>
            <span><b>Proof:</b> ${esc(version.proof)}</span>
            <span><b>Market:</b> ${esc(version.market)}</span>
          </div>
          <span class="pill ${index === 2 ? "warn" : index === 1 ? "ok" : "info"}">${esc(version.best_for)}</span>
        </button>
      `).join("");
      document.querySelectorAll(".vision-choice").forEach(item => {
        item.addEventListener("click", () => applyVisionVersion(versions[Number(item.dataset.version)]));
      });
      coach(
        "Vision Versions Ready",
        "The same rough idea is now shown as practical, growth, and visionary options. Select one direction so the client can see how the idea becomes real work.",
        ["Choose Direction", "factory"],
        ["Open Projects", "projects"]
      );
    }

    function renderManagementGraphs() {
      const queued = state.jobs.filter(job => job.status === "queued").length;
      const running = state.jobs.filter(job => job.status === "running").length;
      const failed = unresolvedProblemJobs().length;
      const online = state.workers.filter(worker => worker.status === "online").length;
      const requestCount = state.metrics.ai_enterprise_http_requests_total || 0;
      const dashboardHits = state.metrics.ai_enterprise_http_route_dashboard_total || 0;
      const improvementProposals = dashboardRecoveryProposals();
      renderSurfaceNodes("factoryGraph", [
        { title: "Attach Manifesto", detail: "Load the business goal, repository path, default branch, project type, and reusable operating rules.", idea: "Treat the manifesto as the contract between the human operator and the AI factory.", effect: "Cuts setup ambiguity before work starts.", signal: loadedManifestDocument ? "loaded" : "input", kind: loadedManifestDocument ? "ok" : "info", action: "manifest" },
        { title: "Select Factory Type", detail: `Current template: ${selectedCapability.replace(/_/g, " ")}. This controls which specialist path the project follows.`, idea: "Match the project type to the economic outcome you want to prove.", effect: "Improves crew routing and reusable blueprint quality.", signal: "template", kind: "info", action: "name" },
        { title: "Create Project", detail: "Register repository, branch, manifest hash, and governed project identity.", idea: "Create one clean project record before any agent work starts.", effect: "Preserves auditability and prevents orphan execution.", signal: "ready", kind: "warn", action: "start" },
        { title: "Parallel Batch", detail: "Start all manifesto projects together and open the project switchboard.", idea: "Use batch launch when one manifesto describes a portfolio of related work.", effect: "Turns planning time into parallel workflow throughput.", signal: "parallel", kind: "ok", action: "batch" },
        { title: "Preview Mock Factory", detail: "Check which demo projects will be created, reused, blocked, or inspected first.", idea: "Preview before creating records so the launch is supervised.", effect: "Shows readiness, reuse, and the recommended first dashboard.", signal: "preview", kind: "info", action: "previewMock" },
        { title: "Mock Autonomy", detail: "Launch a safe demo portfolio that proves the factory can start producing from a manifesto-style operating loop.", idea: "Use this after preview when you want to see the enterprise wake up and begin real workflow activity.", effect: "Creates or reuses demo projects, formation packs, workflows, jobs, and telemetry links.", signal: "demo", kind: "ok", action: "mock" },
        { title: "Open Execution", detail: "Move directly to live execution control after launch.", idea: "Inspect the project life immediately after creation.", effect: `${countSentence(state.projects.length, "project")} visible in Execution.`, signal: `${state.projects.length} projects`, kind: "info", action: "execution" }
      ]);
      renderSurfaceNodes("problemGraph", [
        { title: "Queued Work", detail: "Work waiting for a worker lease.", idea: "If this grows, add capacity or inspect blocked workers.", effect: `${queued} job(s) waiting.`, signal: `${queued}`, kind: queued ? "warn" : "ok", action: "problems" },
        { title: "Running Work", detail: "Active jobs connected to projects and crews.", idea: "Use this to confirm the factory is moving, not idle.", effect: `${running} job(s) currently active.`, signal: `${running}`, kind: running ? "info" : "ok", action: "problems" },
        { title: "Followed Errors", detail: "Failed and dead-letter jobs are visible improvement inputs.", idea: "Every error should become a fix, guardrail, or reusable lesson.", effect: `${failed} problem(s) require follow-up.`, signal: `${failed}`, kind: failed ? "bad" : "ok", action: "problems" },
        { title: "Worker Topology", detail: "Worker instances show profile, heartbeat, and operating readiness.", idea: "Healthy workers are the enterprise production capacity.", effect: `${online} worker(s) online.`, signal: `${online} online`, kind: online ? "ok" : "warn", action: "problems" },
        { title: "Solutions", detail: "Project intelligence converts problems into calibration and recommendations.", idea: "Review improvements before restarting failed work.", effect: "Reduces repeat failures across future projects.", signal: "improve", kind: "info", action: "projects" }
      ].concat(improvementProposals));
      renderSurfaceNodes("telemetryGraph", [
        { title: "HTTP Flow", detail: "Request and route counters prove the service is receiving traffic.", idea: "Use traffic as a basic heartbeat for the operator system.", effect: `${requestCount} recorded request(s).`, signal: `${requestCount}`, kind: "info", action: "metrics" },
        { title: "Dashboard Pulse", detail: "Manager surface usage is tracked as a runtime signal.", idea: "The dashboard itself becomes part of operations telemetry.", effect: `${dashboardHits} dashboard hit(s).`, signal: `${dashboardHits}`, kind: "ok", action: "metrics" },
        { title: "Worker Health", detail: "Worker counts calibrate enterprise operating capacity.", idea: "Capacity should match project parallelism.", effect: `${online} worker(s) available.`, signal: `${online}`, kind: online ? "ok" : "warn", action: "problems" },
        { title: "Problem Pressure", detail: "Failed work changes the operating picture and recommended action.", idea: "Problem pressure should drive recovery and blueprint hardening.", effect: `${failed} followed issue(s).`, signal: `${failed}`, kind: failed ? "bad" : "ok", action: "problems" },
        { title: "Calibration Feed", detail: "Telemetry supports phase completion, errors followed, and economic proof.", idea: "Use metrics to decide, not to decorate.", effect: "Improves estimate quality and future automation design.", signal: "active", kind: "ok", action: "projects" }
      ]);
      if (state.operatingPicture) {
        const nodes = state.operatingPicture.graph.nodes || [];
        const important = nodes.slice(0, 8).map(node => ({
          title: node.label,
          detail: node.human_summary,
          idea: `This is a ${node.kind.replace(/-/g, " ")} signal from the read model.`,
          effect: "Keeps dashboards connected to the same governed operating picture.",
          signal: node.status,
          kind: statusClass(node.status),
          action: node.kind === "project" ? "projects" : "overview"
        }));
        renderSurfaceNodes("operatingPictureSignals", important);
      } else if (byId("operatingPictureSignals")) {
        byId("operatingPictureSignals").innerHTML = `<div class="mini muted">Operating picture is not loaded yet. Refresh to reconnect the governed read model.</div>`;
      }
      const reuse = state.dashboardManager?.reuse || {};
      const blueprintLearning = reuse.blueprint_candidates || [];
      const guardrailLearning = reuse.guardrail_candidates || [];
      const reuseReadiness = reuse.readiness || {};
      const nextCatalogReview = reuse.next_catalog_review;
      const nextReviewEvidence = nextCatalogReview?.evidence_bundle?.sources || {};
      const nextReviewEvidenceCount = Object.values(nextReviewEvidence).reduce((total, value) => total + Number(value || 0), 0);
      const nextReviewCriteriaPassed = (nextCatalogReview?.evidence_bundle?.criteria_status || []).filter(item => item.passed).length;
      renderSurfaceNodes("blueprintGraph", [
        { title: "Code Graph", detail: "Graphify architecture map for the repository.", idea: "Use it to understand what code areas a change touches.", effect: "Reduces blind edits and improves architecture navigation.", signal: "open", kind: "info", action: "graphify" },
        { title: "Project Foundry Core", detail: "AEOS project factory specification, schemas, prompt contracts, gates, and repository template.", idea: "Use it as the standard operating contract for every governed project.", effect: "Turns the Corel manifest into reusable enterprise factory rules.", signal: "download", kind: "ok", action: "foundry" },
        { title: "Ecosystem Graph", detail: "Shows enterprise relationships after governed records are linked.", idea: "Inspect enterprise relationships before broad changes.", effect: "Improves cross-object governance.", signal: "check map", kind: "info", action: "ecosystem" },
        { title: "Evidence Graph", detail: "Shows project proof after requirements, decisions, and evidence are recorded.", idea: "Trace decisions back to requirements and proof.", effect: "Improves audit readiness.", signal: "check proof", kind: "info", action: "evidence" },
        { title: "Project Blueprints", detail: "Workflow, specialist-crew, and economic-proof patterns produced by project intelligence.", idea: "Promote repeated successful structures into templates.", effect: "Increases reuse across future projects.", signal: "reuse", kind: "ok", action: "projects" },
        { title: "Blueprint Learning Queue", detail: `${reuse.summary || "No reusable learning candidates have been observed yet."} Review-ready: ${reuseReadiness.catalog_review_ready || 0}; needs proof: ${reuseReadiness.needs_more_proof || 0}. Next review: ${nextCatalogReview ? nextCatalogReview.project_name : "none ready"} with ${nextReviewEvidenceCount} proof item(s) and ${nextReviewCriteriaPassed} passed criterion/criteria.`, idea: "Successful project proof becomes candidate blueprint material after review.", effect: reuse.operator_action || "Promote reusable patterns only after proof review.", signal: `${blueprintLearning.length} blueprint`, kind: (reuseReadiness.catalog_review_ready || 0) ? "ok" : blueprintLearning.length ? "warn" : "info", action: "projects" },
        { title: "Guardrail Learning Queue", detail: `${guardrailLearning.length} repeated-failure guardrail candidate(s). Evidence required: ${reuseReadiness.guardrails_evidence_required || 0}.`, idea: "Repeated failures should become recovery checklists, tests, or template guardrails.", effect: "Keeps the factory from repeating known failure classes.", signal: `${guardrailLearning.length} guardrail`, kind: guardrailLearning.length ? "warn" : "ok", action: "problems" },
        { title: "Future Templates", detail: "Reusable patterns become stronger starting points for later manifestos.", idea: "Feed lessons back into the next project creation cycle.", effect: "Compounds delivery speed and quality over time.", signal: "evolve", kind: "ok", action: "factory" }
      ]);
    }

    async function checkAuthenticatedGraph(kind) {
      const organizationId = byId("graphOrganizationId").value.trim();
      const projectId = byId("graphProjectId").value.trim();
      if (!organizationId) {
        byId("authenticatedGraphStatus").innerHTML = `<strong>Organization needed</strong><div class="muted">Refresh the dashboard or enter an organization ID before checking the ${esc(kind)} map.</div>`;
        return;
      }
      if (kind === "evidence" && !projectId) {
        byId("authenticatedGraphStatus").innerHTML = `<strong>Project needed</strong><div class="muted">Select a project or enter its project ID before checking project proof.</div>`;
        return;
      }
      const url = kind === "ecosystem"
        ? `/api/v1/ecosystem/graph?organization_id=${encodeURIComponent(organizationId)}`
        : `/api/v1/specifications/evidence/graph?organization_id=${encodeURIComponent(organizationId)}&project_id=${encodeURIComponent(projectId)}`;
      try {
        const payload = await json(url, { headers: actorHeaders });
        const graphNodes = payload.nodes || payload.entities || [];
        const nodes = Array.isArray(graphNodes) ? graphNodes.length : 0;
        const edges = Array.isArray(payload.edges) ? payload.edges.length : 0;
        if (nodes === 0 && edges === 0) {
          byId("authenticatedGraphStatus").innerHTML = `<strong class="warn">${esc(kind)} map is ready but empty</strong><div class="muted">The connection works. Link governed records during project execution, then refresh to see relationships here.</div>`;
          return;
        }
        byId("authenticatedGraphStatus").innerHTML = `<strong class="ok">${esc(kind)} map available</strong><div class="muted">${esc(nodes)} node(s), ${esc(edges)} edge(s). The dashboard is reading linked records for this project or organization.</div>`;
      } catch (error) {
        byId("authenticatedGraphStatus").innerHTML = `<strong class="bad">${esc(kind)} map needs attention</strong><div class="muted">The dashboard could not read this map. Refresh context first; if it repeats, inspect API readiness and permissions.</div>`;
      }
    }

    function renderCapabilities() {
      byId("capabilityList").innerHTML = capabilities.map(([key, label], index) => `
        <button class="list-item capability-item ${key === selectedCapability ? "selected" : ""}" data-capability="${esc(key)}">
          <div><div class="list-title">${esc(index + 1)}. ${esc(label)}</div><div class="list-meta">Factory template</div></div>
          <span class="pill info">${key === selectedCapability ? "selected" : "choose"}</span>
        </button>
      `).join("");
      document.querySelectorAll(".capability-item").forEach(item => {
        item.addEventListener("click", () => {
          selectedCapability = item.dataset.capability;
          renderCapabilities();
        });
      });
    }

    function normalizeManifest(document) {
      const defaults = document.defaults || {};
      const project = Array.isArray(document.projects) ? document.projects[0] : document;
      return { ...defaults, ...project };
    }

    function fieldFromText(text, labels) {
      const lines = text.split(/\r?\n/);
      for (const label of labels) {
        const pattern = new RegExp(`^\\\\s*(?:[-*]\\\\s*)?${label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\\\s*:?\\\\s*(.+?)\\\\s*$`, "i");
        for (const line of lines) {
          const match = line.match(pattern);
          if (match && match[1] && !match[1].startsWith("[") && !match[1].startsWith("<")) {
            return match[1].trim();
          }
        }
      }
      return "";
    }

    function sectionFromText(text, heading) {
      const escaped = heading.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const match = text.match(new RegExp(`(?:^|\\n)#{0,3}\\\\s*${escaped}\\\\s*(?:\\n|$)([\\s\\S]*?)(?=\\n#{1,3}\\\\s|\\nChapter\\\\s+\\d+|$)`, "i"));
      if (!match) return "";
      return match[1]
        .split(/\r?\n/)
        .map(line => line.replace(/^\s*[-*]\s*/, "").trim())
        .filter(line => line && !line.endsWith(":") && !line.startsWith("["))
        .slice(0, 12)
        .join("\n");
    }

    function parseClientManifestText(text) {
      const projectName = fieldFromText(text, ["Project Name", "Project name"]);
      const repositoryPath = fieldFromText(text, [
        "Project Base Directory",
        "Base Directory",
        "Repository Path",
        "Local Repository Path"
      ]);
      const githubUrl = fieldFromText(text, [
        "GitHub Repository URL",
        "Github Repository URL",
        "Repository URL",
        "Git Remote URL"
      ]);
      const defaultBranch = fieldFromText(text, ["Default Branch", "Branch"]) || "main";
      const vision = sectionFromText(text, "Executive Vision");
      const objectives = sectionFromText(text, "Project Objectives");
      const success = sectionFromText(text, "Success Criteria");
      const description = [vision, objectives, success].filter(Boolean).join("\n\n") ||
        text.split(/\r?\n/).filter(line => line.trim()).slice(0, 12).join("\n");
      return {
        name: projectName,
        description,
        repository_path: repositoryPath,
        repository_url: githubUrl,
        default_branch: defaultBranch,
        manifest: {
          source_document_type: "client_project_manifest",
          client_manifest_text: text,
          project_identity: {
            project_name: projectName,
            repository_path: repositoryPath,
            repository_url: githubUrl,
            default_branch: defaultBranch
          }
        }
      };
    }

    async function loadManifestFile(file) {
      const rawText = await file.text();
      const isJson = file.name.toLowerCase().endsWith(".json") || file.type === "application/json";
      const document = isJson ? JSON.parse(rawText) : parseClientManifestText(rawText);
      loadedManifestDocument = document;
      const project = normalizeManifest(document);
      byId("factoryName").value = project.name || "";
      byId("factoryDescription").value = project.description || "";
      byId("factoryRepo").value = project.repository_path || "";
      byId("factoryGithub").value = project.repository_url || "";
      byId("factoryBranch").value = project.default_branch || "main";
      byId("manifestPreview").innerHTML = `
        <strong>${esc(project.name || "Manifesto loaded")}</strong>
        <div>${esc(project.description || "No description")}</div>
        <div class="muted">${esc(project.repository_path || "No repository path")}</div>
        <div class="muted">${esc(project.repository_url || "No GitHub repository URL yet")}</div>
      `;
      setOrientation(2, "Manifesto inserted. Check project type, repository path, and branch, then start one process or the batch.");
      coach(
        "Manifesto Loaded",
        "The factory now has project intent. Verify project type, repository path, and branch, then start one process or the manifesto batch.",
        ["Check Project Type", "factory"],
        ["Open Projects", "projects"]
      );
      renderManagementGraphs();
    }

    async function createAndStartProject(projectInput) {
      const validation = validateProjectInput(projectInput);
      if (!validation.ok) {
        throw new Error(validation.message);
      }
      const sourceManifest = projectInput.manifest || projectInput;
      const manifest = {
        ...sourceManifest,
        project_type: selectedCapability,
        factory_type: selectedCapability,
        dashboard_created_at: new Date().toISOString()
      };
      const payload = {
        name: projectInput.name,
        description: `${projectInput.description}\n\nFactory type: ${selectedCapability}`,
        repository_path: projectInput.repository_path,
        repository_url: projectInput.repository_url || sourceManifest.repository_url || null,
        default_branch: projectInput.default_branch || "main",
        project_type: selectedCapability,
        manifest
      };
      const project = await json("/api/v1/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      await json(`/api/v1/project-formation/projects/${project.id}/packs`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...actorHeaders },
        body: JSON.stringify({
          project_id: project.id,
          idea: projectInput.description,
          expected_outcome: sourceManifest.expected_outcome || "Create visible governed project proof.",
          target_users: sourceManifest.target_users || ["operator", "client owner"],
          constraints: sourceManifest.constraints || ["human approval before execution"],
          known_systems: sourceManifest.known_systems || [projectInput.repository_path],
          deadline: sourceManifest.deadline || null,
          budget_signal: sourceManifest.budget_signal || "reuse existing enterprise workflow assets"
        })
      });
      await json(`/api/v1/projects/${project.id}/workflow`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ actor_id: "factory-dashboard" })
      });
      return project;
    }

    function validateProjectInput(projectInput) {
      const missing = [];
      if (!String(projectInput.name || "").trim()) missing.push("project name");
      if (!String(projectInput.repository_path || "").trim()) missing.push("repository path");
      if (!String(projectInput.default_branch || "").trim()) missing.push("default branch");
      if (!String(projectInput.description || "").trim()) missing.push("project summary");
      if (missing.length) {
        return {
          ok: false,
          message: `Project name, repository path, default branch, and project summary are required before the factory can start. Missing: ${missing.join(", ")}.`
        };
      }
      return { ok: true, message: "Ready" };
    }

    function friendlyLaunchError(error) {
      const message = String(error?.message || "");
      if (message.includes("required before the factory can start")) return message;
      if (message.includes("JSON")) return "The manifesto format is not valid JSON. Check the file, then load it again.";
      if (message.includes("409")) return "The factory found an existing record or workflow conflict. Open Projects and inspect the existing work before retrying.";
      if (message.includes("422")) return "The factory could not start this project. Check project name, repository path, branch, and manifesto format.";
      if (message.includes("500")) return "The factory service failed during launch. Refresh, check source freshness, and inspect API logs before retrying.";
      return "The factory could not start this project. Check project details, manifesto format, and source freshness before retrying.";
    }

    function currentFactoryProjectInput() {
      return {
        name: byId("factoryName").value.trim(),
        description: byId("factoryDescription").value.trim(),
        repository_path: byId("factoryRepo").value.trim(),
        repository_url: byId("factoryGithub").value.trim() || null,
        default_branch: byId("factoryBranch").value.trim() || "main",
        manifest: loadedManifestDocument ? normalizeManifest(loadedManifestDocument) : {}
      };
    }

    function previewFactoryLaunch() {
      const document = loadedManifestDocument;
      if (document && Array.isArray(document.projects) && document.projects.length) {
        const defaults = document.defaults || {};
        const validations = document.projects.map(project => validateProjectInput({ ...defaults, ...project }));
        const blocked = validations.filter(result => !result.ok);
        const ready = validations.length - blocked.length;
        byId("factoryStatus").textContent = blocked.length
          ? `Preview found ${countSentence(blocked.length, "project")} that needs correction before batch launch.`
          : `Preview ready: ${countSentence(ready, "project")} can start in parallel.`;
        renderLaunchContract({
          status: blocked.length ? "blocked" : "ready",
          summary: blocked.length
            ? "No records were created. The batch manifesto needs correction before launch."
            : "No records were created. The batch manifesto is ready for supervised parallel launch.",
          started: 0,
          created: ready,
          reused: 0,
          blocked: blocked.length,
          failed: 0,
          recommendedName: ready ? (document.projects.find((_, index) => validations[index].ok)?.name || "First ready project") : "Fix manifesto first",
          recommendedUrl: "/dashboard#factory",
          nextAction: blocked.length
            ? blocked[0].message
            : "Press Start Manifesto Batch to create projects, formation packs, and workflows.",
          proof: "Client-side preflight only. No database record, workflow, job, or artifact was created.",
          items: document.projects.map((project, index) => ({
            name: project.name || `Project ${index + 1}`,
            status: validations[index].ok ? "ready" : "blocked",
            detail: validations[index].ok
              ? `Ready to create at ${(project.repository_path || defaults.repository_path || "repository path not shown")}.`
              : validations[index].message,
            action: validations[index].ok
              ? "Start Manifesto Batch when you want to create this project."
              : "Correct this project in the manifesto before launch."
          }))
        });
        setOrientation(2, blocked.length ? "Preview found missing batch details. Correct them before launch." : "Preview is ready. Start the manifesto batch when you want the factory to create work.");
        coach(
          blocked.length ? "Batch Preview Needs Input" : "Batch Preview Ready",
          blocked.length ? blocked[0].message : "The manifesto batch has enough information to create governed work.",
          ["Continue in Factory", "factory"],
          ["Open Execution", "execution"]
        );
        return;
      }

      const projectInput = currentFactoryProjectInput();
      const validation = validateProjectInput(projectInput);
      byId("factoryStatus").textContent = validation.ok
        ? "Preview ready: the project can be created."
        : validation.message;
      renderLaunchContract({
        status: validation.ok ? "ready" : "blocked",
        summary: validation.ok
          ? "No records were created. This project is ready for supervised launch."
          : "No records were created. Missing launch details must be fixed first.",
        started: 0,
        created: validation.ok ? 1 : 0,
        reused: 0,
        blocked: validation.ok ? 0 : 1,
        failed: 0,
        recommendedName: projectInput.name || "Complete project name",
        recommendedUrl: "/dashboard#factory",
        nextAction: validation.ok
          ? "Press Start Process to create the project, formation pack, and workflow."
          : validation.message,
        proof: "Client-side preflight only. No database record, workflow, job, or artifact was created.",
        items: [{
          name: projectInput.name || "Single project",
          status: validation.ok ? "ready" : "blocked",
          detail: validation.ok
            ? `Ready to create at ${projectInput.repository_path}.`
            : validation.message,
          action: validation.ok
            ? "Press Start Process when you want to create governed work."
            : "Complete the required fields before starting."
        }]
      });
      setOrientation(2, validation.ok ? "Preview is ready. Start the process when you want the factory to create work." : "Preview found missing details. Complete the fields before starting.");
      coach(
        validation.ok ? "Launch Preview Ready" : "Launch Preview Needs Input",
        validation.ok ? "The project has enough information to start governed factory work." : validation.message,
        ["Continue in Factory", "factory"],
        ["Open Execution", "execution"]
      );
    }

    async function startFactoryProject() {
      const projectInput = currentFactoryProjectInput();
      const validation = validateProjectInput(projectInput);
      if (!validation.ok) {
        byId("factoryStatus").textContent = validation.message;
        coach(
          "Factory Needs Input",
          validation.message,
          ["Complete Details", "factory"],
          ["Open Projects", "projects"]
        );
        return;
      }
      byId("factoryStatus").textContent = "Creating project...";
      const project = await createAndStartProject(projectInput);
      byId("factoryStatus").textContent = "Formation pack created. Opening execution graph...";
      renderLaunchContract({
        status: "started",
        summary: "One governed project was created, a formation pack was prepared, and workflow execution was started.",
        started: 1,
        created: 1,
        reused: 0,
        blocked: 0,
        failed: 0,
        recommendedName: project.name,
        recommendedUrl: `/dashboard?project=${project.id}`,
        nextAction: "Open Execution and watch the project graph for phase, task, crew, event, and telemetry movement.",
        proof: "Project record, formation pack, workflow start, and dashboard graph.",
        items: [{
          name: project.name,
          status: "started",
          detail: `Created at ${project.repository_path || projectInput.repository_path}.`,
          action: "Open the project graph and verify live execution movement."
        }]
      });
      setOrientation(3, "Formation pack created and workflow started. Inspect the live project graph next.");
      coach(
        "Project Formed",
        "The project now has a formation pack and workflow execution started. Watch the Execution graph for phase, tasks, crew, events, telemetry, and problems.",
        ["Open Execution", "execution"],
        ["Review Problems", "problems"]
      );
      await refresh();
      selectedExecutionNode = `project:${project.id}`;
      document.querySelector('[data-view="execution"]').click();
      renderExecutionDashboard();
    }

    async function startManifestBatch() {
      const document = loadedManifestDocument;
      if (!document || !Array.isArray(document.projects) || !document.projects.length) {
        await startFactoryProject();
        return;
      }
      const defaults = document.defaults || {};
      const invalid = document.projects
        .map((project, index) => ({ index, validation: validateProjectInput({ ...defaults, ...project }) }))
        .filter(item => !item.validation.ok);
      if (invalid.length) {
        byId("factoryStatus").textContent = `Manifesto batch needs correction before launch. Project ${invalid[0].index + 1}: ${invalid[0].validation.message}`;
        coach(
          "Batch Needs Input",
          "One or more manifesto projects are missing required launch details. Correct the manifesto before starting parallel work.",
          ["Fix Manifesto", "factory"],
          ["Open Projects", "projects"]
        );
        return;
      }
      byId("factoryStatus").textContent = `Starting ${countSentence(document.projects.length, "project")} in parallel...`;
      const results = await Promise.allSettled(document.projects.map(project =>
        createAndStartProject({ ...defaults, ...project })
      ));
      const started = results.filter(result => result.status === "fulfilled").map(result => result.value);
      const failed = results.length - started.length;
      const launchItems = results.map((result, index) => {
        const sourceProject = { ...defaults, ...document.projects[index] };
        if (result.status === "fulfilled") {
          return {
            name: result.value.name,
            status: "started",
            detail: `Created at ${result.value.repository_path || sourceProject.repository_path}.`,
            action: "Open Execution and inspect this project graph."
          };
        }
        return {
          name: sourceProject.name || `Project ${index + 1}`,
          status: "failed",
          detail: friendlyLaunchError(result.reason),
          action: "Correct the manifesto or inspect API logs before retrying."
        };
      });
      byId("factoryStatus").textContent = `Started ${started.length}; failed ${failed}. Opening execution control...`;
      renderLaunchContract({
        status: failed ? "partial" : "started",
        summary: failed
          ? "The batch started every valid project and reported launch issues for the rest."
          : "The batch started every manifesto project successfully.",
        started: started.length,
        created: started.length,
        reused: 0,
        blocked: 0,
        failed,
        recommendedName: started[0]?.name || "No project ready yet",
        recommendedUrl: started[0] ? `/dashboard?project=${started[0].id}` : "/dashboard#factory",
        nextAction: failed
          ? "Open Execution for started work, then inspect Problems or correct the manifesto before retrying failed launches."
          : "Open Execution and inspect the first project while the portfolio continues in parallel.",
        proof: "Manifesto batch, project records, formation packs, workflow starts, and execution graph.",
        items: launchItems
      });
      setOrientation(3, `Manifesto batch started: ${countSentence(started.length, "project")}, ${countSentence(failed, "launch issue")}. Inspect Execution first.`);
      coach(
        "Manifesto Batch Started",
        `The factory started ${countSentence(started.length, "project")} and detected ${countSentence(failed, "launch failure")}. Inspect Execution first, then Problems if any launch failed.`,
        ["Open Execution", "execution"],
        ["Review Problems", "problems"]
      );
      await refresh();
      if (started[0]) selectedExecutionNode = `project:${started[0].id}`;
      document.querySelector('[data-view="execution"]').click();
      renderExecutionDashboard();
    }

    function renderLaunchContract(contract) {
      const status = contract.status || "waiting";
      const recommendedUrl = contract.recommendedUrl || "/dashboard#execution";
      const recommendedTarget = recommendedUrl.includes("#")
        ? recommendedUrl.split("#").pop()
        : "";
      byId("launchContract").innerHTML = `
        <strong>Launch Result</strong>
        <div>${esc(contract.summary || "The factory is waiting for a preview or launch action.")}</div>
        <div class="launch-contract-grid">
          <div class="launch-contract-cell"><span>Status</span><strong class="${statusClass(status)}">${esc(humanStatus(status))}</strong></div>
          <div class="launch-contract-cell"><span>Started</span><strong>${esc(contract.started ?? 0)}</strong></div>
          <div class="launch-contract-cell"><span>Created</span><strong>${esc(contract.created ?? 0)}</strong></div>
          <div class="launch-contract-cell"><span>Reused</span><strong>${esc(contract.reused ?? 0)}</strong></div>
          <div class="launch-contract-cell"><span>Needs Action</span><strong>${esc((contract.blocked ?? 0) + (contract.failed ?? 0))}</strong></div>
          <div class="launch-contract-cell"><span>Inspect First</span><strong>${esc(contract.recommendedName || "Execution graph")}</strong></div>
        </div>
        <div class="human-copy">
          <span><b>Next:</b> ${esc(contract.nextAction || "Open Execution and inspect the current graph state.")}</span>
          <span><b>Proof:</b> ${esc(contract.proof || "Dashboard source freshness, project records, workflow state, and telemetry.")}</span>
        </div>
        <div class="launch-contract-list">
          <strong>Project Readiness</strong>
          ${listbox(contract.items || [], item => `
            <div class="list-item">
              <div>
                <div class="list-title">${esc(item.name || "Unnamed project")}</div>
                <div class="list-meta">${esc(item.detail || "No detail reported yet.")}</div>
                <div class="list-meta">Next: ${esc(item.action || "Continue with the guided launch path.")}</div>
              </div>
              <span class="pill ${statusClass(item.status)}">${esc(humanStatus(item.status))}</span>
            </div>
          `, "No project readiness items yet. Press Preview Launch or start the factory to populate this list.")}
        </div>
        <div class="launch-contract-actions">
          <button class="launch-open" data-target="${esc(recommendedTarget || "execution")}">Open Recommended View</button>
          <a class="link-button" href="${esc(recommendedUrl)}">Open Proof Path</a>
        </div>
      `;
      document.querySelectorAll(".launch-open").forEach(button => {
        button.addEventListener("click", () => goTarget(button.dataset.target || "execution"));
      });
    }

    function renderMockFactoryProjects(payload, mode) {
      const projects = payload.projects || [];
      const blocked = payload.blocked || [];
      const failed = payload.failed || [];
      const recommended = payload.recommended_first_project;
      const projectNodes = projects.map(project => ({
        title: project.name,
        detail: project.dashboard_url || project.repository_path,
        idea: mode === "preview"
          ? `Action: ${project.action || project.project_record || "create"}`
          : `Workflow: ${project.workflow || "not started"}`,
        effect: mode === "preview"
          ? project.operator_action || "Ready for supervised launch."
          : project.next_action || "Open this project dashboard for inspection.",
        signal: mode === "preview"
          ? (project.ready ? project.action || "ready" : "blocked")
          : project.project_record || "ready",
        kind: project.ready === false ? "bad" : project.project_record === "reused" || project.action === "reuse" ? "info" : "ok",
        action: "execution"
      }));
      const issueNodes = blocked.concat(failed).map(item => ({
        title: item.name,
        detail: item.issues.join("; ") || "Launch issue needs review.",
        idea: item.operator_action,
        effect: item.repository_path,
        signal: item.status,
        kind: item.status === "blocked" ? "warn" : "bad",
        action: "factory"
      }));
      const summary = [
        {
          title: mode === "preview" ? "Launch Preview" : "Launch Result",
          detail: payload.human_summary,
          idea: `Ready: ${payload.ready_count ?? payload.started_count ?? 0}; reused: ${payload.reused_count ?? 0}; blocked: ${payload.blocked_count ?? 0}; failed: ${payload.failed_count ?? 0}`,
          effect: recommended
            ? `Inspect first: ${recommended.name}`
            : "No recommended project is available yet.",
          signal: payload.status,
          kind: payload.status === "ready" || payload.status === "started" ? "ok" : "warn",
          action: recommended && recommended.dashboard_url ? "execution" : "factory"
        }
      ];
      byId("factoryGraphStatus").textContent = mode === "preview"
        ? "Preview complete: review readiness before launch."
        : "Launch complete: inspect created, reused, blocked, and failed work.";
      renderSurfaceNodes("factoryGraph", summary.concat(projectNodes, issueNodes));
    }

    async function previewMockFactoryTest() {
      byId("factoryStatus").textContent = "Previewing controlled mock autonomy...";
      const result = await json("/api/v1/project-formation/mock-factory/preview", {
        headers: actorHeaders
      });
      byId("factoryStatus").textContent = `${result.ready_count} ready; ${result.reused_count} reused; ${result.blocked_count} blocked.`;
      renderLaunchContract({
        status: result.status,
        summary: result.human_summary,
        started: 0,
        created: result.ready_count - result.reused_count,
        reused: result.reused_count,
        blocked: result.blocked_count,
        failed: 0,
        recommendedName: result.recommended_first_project?.name || "No ready project yet",
        recommendedUrl: result.recommended_first_project?.dashboard_url || "/dashboard#factory",
        nextAction: result.blocked_count
          ? "Correct blocked launch information before starting the mock factory."
          : "Launch the mock factory when you are ready to create or reuse the portfolio projects.",
        proof: "Preview contract, readiness count, reused projects, blocked projects, and recommended first inspection target.",
        items: (result.projects || []).map(project => ({
          name: project.name,
          status: project.ready ? (project.action || "ready") : "blocked",
          detail: project.ready
            ? `${project.action === "reuse" ? "Will reuse existing project" : "Ready to create"} at ${project.repository_path}.`
            : (project.missing_information || []).join("; "),
          action: project.operator_action || "Continue with the mock factory launch path."
        }))
      });
      renderMockFactoryProjects(result, "preview");
      coach(
        "Mock Factory Preview Ready",
        result.human_summary,
        ["Launch Mock Factory", "factory"],
        ["Open Projects", "projects"]
      );
    }

    async function startMockFactoryTest() {
      byId("factoryStatus").textContent = "Starting controlled mock autonomy...";
      const result = await json("/api/v1/project-formation/mock-factory/start", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...actorHeaders },
        body: JSON.stringify({})
      });
      byId("factoryStatus").textContent = `${result.started_count} demo project(s) ready; ${result.blocked_count || 0} blocked; ${result.failed_count || 0} failed. ${result.next_action}`;
      renderLaunchContract({
        status: result.status,
        summary: result.human_summary,
        started: result.started_count,
        created: result.created_count,
        reused: result.reused_count,
        blocked: result.blocked_count,
        failed: result.failed_count,
        recommendedName: result.recommended_first_project?.name || "No project ready yet",
        recommendedUrl: result.recommended_first_project?.dashboard_url || "/dashboard#factory",
        nextAction: result.next_action,
        proof: "Created or reused projects, formation packs, workflows, jobs, telemetry links, and recommended dashboard path.",
        items: (result.projects || []).map(project => ({
          name: project.name,
          status: project.workflow || project.project_record || "started",
          detail: `${project.project_record || "Project"}; formation pack ${project.formation_pack || "not reported"}; workflow ${project.workflow || "not reported"}.`,
          action: project.next_action || "Open this project dashboard for inspection."
        })).concat((result.blocked || []).map(item => ({
          name: item.name,
          status: "blocked",
          detail: (item.issues || []).join("; ") || "Launch needs more information.",
          action: item.operator_action || "Fix blocked launch information."
        }))).concat((result.failed || []).map(item => ({
          name: item.name,
          status: "failed",
          detail: (item.issues || []).join("; ") || "Launch failed.",
          action: item.operator_action || "Inspect logs and retry after correction."
        })))
      });
      renderMockFactoryProjects(result, "launch");
      setOrientation(3, "Mock autonomy started. Open Execution and select a demo project to watch graph movement, tasks, crews, events, and telemetry.");
      coach(
        "Mock Factory Started",
        result.human_summary,
        ["Open Execution", "execution"],
        ["Review Problems", "problems"]
      );
      await refresh();
      if (result.projects && result.projects[0]) selectedExecutionNode = `project:${result.projects[0].project_id}`;
      document.querySelector('[data-view="execution"]').click();
      renderExecutionDashboard();
    }

    function parseMetrics(raw) {
      const metrics = {};
      for (const line of raw.split("\n")) {
        if (!line || line.startsWith("#")) continue;
        const [left, value] = line.trim().split(/\s+/);
        if (!left || value === undefined) continue;
        metrics[left.replace(/\{.*$/, "")] = Number(value);
      }
      return metrics;
    }

    function applyDashboardContext(context) {
      if (!context) return;
      state.context = context;
      if (context.actor_headers) actorHeaders = context.actor_headers;
      if (context.organization_id && !byId("graphOrganizationId").value) {
        byId("graphOrganizationId").value = context.organization_id;
      }
      if (context.project_id && !byId("graphProjectId").value) {
        byId("graphProjectId").value = context.project_id;
      }
    }

    function statusClass(status) {
      const value = String(status || "").toLowerCase();
      if (["online", "ok", "succeeded", "completed", "active", "nominal", "complete", "calibrated", "ready", "started", "live workflow", "evidence backed"].includes(value)) return "ok";
      if (["queued", "running", "leased", "retry_wait", "degraded", "standby", "not_started", "waiting_for_manifesto", "candidate", "reviewed", "early", "early estimate", "observed", "needs_setup", "partial", "blocked"].includes(value)) return "warn";
      if (["failed", "dead_letter", "abandoned", "offline", "attention_required", "needs review"].includes(value)) return "bad";
      return "info";
    }

    function humanStatus(status) {
      const labels = {
        created: "Ready to start",
        reuse: "Will reuse existing work",
        reused: "Reused existing work",
        project_created: "Ready to start",
        work_package_approved: "Plan approved, execution not started",
        waiting_work_package_approval: "Ready for work-package review",
        manual_intervention: "Needs human review before work can continue",
        attention_required: "Needs operator decision",
        context_required: "Choose an organization to see governed metrics",
        dead_letter: "Reviewed failure or recovery needed",
        failed: "Needs recovery action",
        abandoned: "Stopped and needs review",
        queued: "Waiting for worker capacity",
        running: "Work is running",
        leased: "Worker has accepted the work",
        retry_wait: "Waiting before retry",
        succeeded: "Completed",
        nominal: "Healthy",
        ready: "Ready",
        started: "Started and ready to inspect",
        partial: "Partly started, needs review",
        blocked: "Blocked until missing details are fixed",
        needs_setup: "Needs setup",
        viable: "Viable",
        active: "Active",
        standby: "Standby",
        not_started: "Not started",
        waiting_for_manifesto: "Waiting for manifesto",
        candidate: "Candidate",
        reviewed: "Reviewed",
        reusable: "Reusable",
        deprecated: "Deprecated",
        improved: "Improved",
        early: "Early estimate",
        "early estimate": "Early estimate",
        observed: "Observed estimate",
        calibrated: "Calibrated estimate",
        "live workflow": "Live workflow",
        "evidence backed": "Evidence backed",
        "needs review": "Needs review",
        complete: "Complete",
        online: "Online",
        offline: "Offline",
        degraded: "Degraded"
      };
      return labels[String(status || "").toLowerCase()] || String(status || "Not reported").replace(/_/g, " ");
    }

    function workerBusinessSummary(worker) {
      if (worker.status === "online") return "Ready to accept enterprise work.";
      if (worker.status === "degraded") return "Online with reduced capacity. Keep an eye on this profile before scaling parallel projects.";
      if (worker.status === "offline") return "Historical worker instance. It is not part of current capacity.";
      return "Worker signal is recorded by the factory.";
    }

    function workerGroup(worker) {
      return ["online", "degraded"].includes(worker.status) ? "current" : "history";
    }

    function humanJobType(jobType) {
      const text = String(jobType || "background work").replace(/_/g, " ");
      return text.charAt(0).toUpperCase() + text.slice(1);
    }

    function jobBusinessSummary(job) {
      if (isAcknowledgedJob(job)) return "Reviewed history. The evidence is preserved and no current action is required.";
      if (isProblemJob(job)) return `${humanJobType(job.job_type)} needs recovery before this work should be retried.`;
      if (["queued", "retry_wait"].includes(job.status)) return `${humanJobType(job.job_type)} is waiting for capacity or retry timing.`;
      if (["running", "leased"].includes(job.status)) return `${humanJobType(job.job_type)} is currently moving.`;
      if (job.status === "succeeded") return `${humanJobType(job.job_type)} completed successfully.`;
      return `${humanJobType(job.job_type)} is tracked by the factory.`;
    }

    function failureImprovementProposals() {
      const counts = {};
      state.jobs
        .filter(job => isProblemJob(job) && !isAcknowledgedJob(job))
        .forEach(job => {
          const key = job.last_failure_class || "unknown";
          counts[key] = (counts[key] || 0) + 1;
        });
      return Object.entries(counts)
        .filter(([, count]) => count >= 2)
        .slice(0, 4)
        .map(([failureClass, count]) => ({
          title: `Guardrail proposal: ${failureClass.replace(/_/g, " ")}`,
          detail: `${count} current failure(s) share this class.`,
          idea: "Repeated failure classes should become a recovery checklist, test guardrail, or project template improvement.",
          effect: "Reduces repeat failures before more work is queued.",
          signal: "proposed",
          kind: "warn",
          action: "projects"
        }));
    }

    function dashboardRecoveryProposals() {
      const proposals = state.dashboardManager?.recovery?.improvement_proposals;
      if (proposals && proposals.length) {
        return proposals.map(proposal => {
          const evidence = proposal.evidence_status || {};
          const missingEvidence = (evidence.missing || []).join(", ") || "immutable evidence reference";
          const evidenceEffect = evidence.ready_to_submit === false
            ? `${evidence.operator_action || proposal.operator_action || "Record reusable guardrail evidence before queuing more work."} Missing: ${missingEvidence}. Draft target: ${evidence.submission_endpoint || proposal.evolution_endpoint}.`
            : `${proposal.operator_action || "Record reusable guardrail evidence before queuing more work."} Draft target: ${proposal.evolution_endpoint}. Evidence required from job attempts.`;
          return {
            title: proposal.title || `Guardrail proposal: ${String(proposal.failure_class || "unknown").replace(/_/g, " ")}`,
            detail: `${proposal.current_failure_count || 0} current failure(s) share this class. Source jobs: ${(proposal.source_jobs || []).map(job => job.job_type || job.job_id).join(", ") || "not listed"}.`,
            idea: proposal.recommendation || "Repeated failure classes should become a recovery checklist, test guardrail, or project template improvement.",
            effect: proposal.improvement_draft?.evidence_required
              ? evidenceEffect
              : proposal.operator_action || "Reduces repeat failures before more work is queued.",
            signal: evidence.ready_to_submit === false ? "evidence required" : proposal.status || "proposed",
            kind: "warn",
            action: "projects"
          };
        });
      }
      return failureImprovementProposals();
    }

    function jobGroup(job) {
      if (isProblemJob(job) && !isAcknowledgedJob(job)) return "current";
      if (["queued", "running", "leased", "retry_wait"].includes(job.status)) return "current";
      if (isAcknowledgedJob(job) || job.status === "succeeded") return "history";
      return "history";
    }

    function jobRecoveryGroup(job) {
      if (isProblemJob(job) && !isAcknowledgedJob(job)) {
        return recoveryGroupMeta("needs_action");
      }
      if (["queued", "running", "leased", "retry_wait"].includes(job.status)) {
        return recoveryGroupMeta("being_retried");
      }
      if (isAcknowledgedJob(job)) {
        return recoveryGroupMeta("reviewed_history");
      }
      return recoveryGroupMeta("healthy_history");
    }

    function recoveryGroupMeta(key) {
      return {
        needs_action: {
          key: "needs_action",
          label: "Needs action",
          className: "bad",
          summary: "Failed work that needs operator recovery before retry.",
        },
        being_retried: {
          key: "being_retried",
          label: "Being retried",
          className: "warn",
          summary: "Work that is queued, leased, running, or waiting for retry.",
        },
        reviewed_history: {
          key: "reviewed_history",
          label: "Reviewed history",
          className: "info",
          summary: "Acknowledged failures preserved as evidence, not current blockers.",
        },
        healthy_history: {
          key: "healthy_history",
          label: "Healthy history",
          className: "ok",
          summary: "Completed or non-blocking historical work evidence.",
        },
      }[key];
    }

    function groupedJobs(jobs) {
      const order = ["needs_action", "being_retried", "reviewed_history", "healthy_history"];
      const groups = Object.fromEntries(order.map(key => [key, []]));
      jobs.forEach(job => {
        const group = jobRecoveryGroup(job);
        groups[group.key].push(job);
      });
      return order
        .map(key => ({ ...recoveryGroupMeta(key), jobs: groups[key] }))
        .filter(group => group.jobs.length);
    }

    async function loadJobAttempts(jobId) {
      byId("jobActionStatus").innerHTML = `<strong>Loading attempts</strong><div class="muted">Reading worker attempts for this job.</div>`;
      const attempts = await json(`/api/v1/operator/jobs/by-id/${encodeURIComponent(jobId)}/attempts`, { headers: actorHeaders });
      byId("jobActionStatus").innerHTML = `
        <strong>Job Attempts</strong>
        ${listbox(attempts, attempt => `
          <div class="list-item">
            <div>
              <div class="list-title">Attempt ${esc(attempt.attempt_number)}</div>
              <div class="list-meta">Worker ${esc(attempt.worker_id || "not assigned")} · ${esc(attempt.status || "not reported")}</div>
              <div class="list-meta">Failure: ${esc(attempt.failure_class || attempt.failure_code || "none recorded")}</div>
            </div>
            <span class="pill ${statusClass(attempt.status)}">${esc(humanStatus(attempt.status))}</span>
          </div>
        `, "No worker attempts are recorded for this job yet.")}
      `;
    }

    async function acknowledgeProblemJob(jobId) {
      byId("jobActionStatus").innerHTML = `<strong>Acknowledging job</strong><div class="muted">Recording operator review and preserving evidence.</div>`;
      await json(`/api/v1/operator/jobs/by-id/${encodeURIComponent(jobId)}/acknowledge`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...actorHeaders },
        body: JSON.stringify({
          reason: "Reviewed from dashboard recovery board.",
          action_taken: "Preserved as historical evidence after operator review."
        })
      });
      byId("jobActionStatus").innerHTML = `<strong class="ok">Job acknowledged</strong><div class="muted">The failure remains visible as reviewed history and no longer counts as current risk.</div>`;
      await refresh();
    }

    function readableTime(value) {
      if (!value) return "Not reported yet";
      return new Date(value).toLocaleString();
    }

    function fieldRows(rows) {
      return `<div class="field-list">${rows.map(([label, value]) => `
        <div class="field-row"><span>${esc(label)}</span><span>${esc(value)}</span></div>
      `).join("")}</div>`;
    }

    function infoCard(kicker, value, rows, className = "") {
      return `
        <div class="mini info-card">
          <div class="card-kicker">${esc(kicker)}</div>
          <div class="card-value ${esc(className)}">${esc(value)}</div>
          ${fieldRows(rows)}
        </div>
      `;
    }

    function render() {
      const online = state.workers.filter(worker => worker.status === "online").length;
      const problemJobs = unresolvedProblemJobs().length;
      byId("workersOnline").textContent = online;
      byId("problemJobs").textContent = problemJobs;
      byId("projectCount").textContent = state.projects.length;
      const runningJobs = state.jobs.filter(job => job.status === "running").length;
      const queuedJobs = state.jobs.filter(job => job.status === "queued").length;
      const requestCount = state.metrics.ai_enterprise_http_requests_total || 0;
      const pulseRows = [
        ["Factory pulse", countSentence(state.projects.length, "project"), "registered"],
        ["Work in motion", countSentence(runningJobs + queuedJobs, "job"), "queued or running"],
        ["Crew capacity", countSentence(online, "worker"), "online"],
        ["Telemetry", countSentence(requestCount, "request signal"), "captured"]
      ];
      byId("livingPulse").innerHTML = pulseRows.map(([label, value, detail]) => {
        const width = Math.min(100, Math.max(8, Number.parseInt(value, 10) * 16 || 8));
        return `
          <div class="pulse-row">
            <strong>${esc(label)}</strong>
            <div class="pulse-track"><div class="pulse-fill" style="width: ${width}%"></div></div>
            <span class="muted">${esc(value)} ${esc(detail)}</span>
          </div>
        `;
      }).join("");
      const failedJobs = unresolvedProblemJobs();
      byId("problemSummary").innerHTML = failedJobs.slice(0, 4).map(job => `
        <div class="mini">
          <strong class="${statusClass(job.status)}">Action needed</strong>
          <div>${esc(humanJobType(job.job_type))} did not finish.</div>
          <div class="muted">Open Problems to see the cause, retry state, and next recovery step.</div>
        </div>
      `).join("") || `
        <div class="mini">
          <strong class="ok">No urgent action</strong>
          <div>The factory has no failed work right now.</div>
          <div class="muted">Continue from Factory to create work, or Projects to inspect delivery.</div>
        </div>
        <div class="mini">
          <strong class="info">Measured state</strong>
          <div>${esc(countSentence(state.projects.length, "project"))}, ${esc(countSentence(online, "online worker"))}, ${esc(countSentence(state.jobs.length, "tracked job"))}.</div>
          <div class="muted">This overview updates automatically every 15 seconds.</div>
        </div>
      `;
      byId("quickLinks").innerHTML = [
        ["factory", "Create work", "Attach a manifesto and start one project or a batch."],
        ["execution", "Watch execution", "See project advancement, task counts, crews, events, and telemetry."],
        ["projects", "Inspect projects", "Open the execution graph for a selected project."],
        ["problems", "Resolve issues", "Review failed or blocked work in human terms."],
        ["metrics", "Check telemetry", "Confirm live signals and source freshness."]
      ].map(([view, label, detail]) => `
        <button class="list-item quick-open" data-view-target="${view}">
          <div><div class="list-title">${label}</div><div class="list-meta">${detail}</div></div>
          <span class="pill info">open</span>
        </button>
      `).join("");
      document.querySelectorAll(".quick-open").forEach(item => {
        item.addEventListener("click", () => switchView(item.dataset.viewTarget));
      });
      const filter = byId("jobFilter").value;
      const filtered = state.jobs.filter(job => {
        if (!filter) return true;
        if (filter === "current" || filter === "history") return jobGroup(job) === filter;
        return job.status === filter;
      });
      byId("jobsTable").innerHTML = groupedJobs(filtered).map(group => `
        <div class="mini">
          <strong class="${esc(group.className)}">${esc(group.label)}</strong>
          <div class="list-meta">${esc(group.summary)}</div>
          ${listbox(group.jobs, job => `
            <div class="list-item">
              <div>
                <div class="list-title">${esc(humanJobType(job.job_type))}</div>
                <div class="list-meta">${esc(jobBusinessSummary(job))}</div>
                <div class="list-meta">Attempt ${esc(job.attempt_count)} of ${esc(job.max_attempts)}${isAcknowledgedJob(job) ? " · acknowledged by operator" : ""}</div>
                <details><summary>Technical detail</summary><div class="list-meta">${esc(job.last_error || "No raw diagnostic reported.")}</div></details>
                <div class="toolbar" style="justify-content: flex-start; margin-top: 8px;">
                  <button class="job-attempts" data-job-id="${esc(job.id)}">Open Attempts</button>
                  ${isProblemJob(job) && !isAcknowledgedJob(job) ? `<button class="job-acknowledge" data-job-id="${esc(job.id)}">Acknowledge Reviewed Failure</button>` : ""}
                </div>
              </div>
              <span class="pill ${isAcknowledgedJob(job) ? "info" : statusClass(job.status)}">${esc(isAcknowledgedJob(job) ? "reviewed history" : humanStatus(job.status))}</span>
            </div>
          `, "No jobs in this recovery group.")}
        </div>
      `).join("") || listbox([], job => job, filter === "history"
        ? "No reviewed history is visible yet. Resolved jobs will appear here after completion or acknowledgment."
        : "No current work needs action. The factory is clear to inspect projects or create new work.");
      document.querySelectorAll(".job-attempts").forEach(button => {
        button.addEventListener("click", () => {
          loadJobAttempts(button.dataset.jobId).catch(error => {
            byId("jobActionStatus").innerHTML = `<strong class="bad">Attempts unavailable</strong><div class="muted">${esc(error.message)}</div>`;
          });
        });
      });
      document.querySelectorAll(".job-acknowledge").forEach(button => {
        button.addEventListener("click", () => {
          acknowledgeProblemJob(button.dataset.jobId).catch(error => {
            byId("jobActionStatus").innerHTML = `<strong class="bad">Acknowledge failed</strong><div class="muted">${esc(error.message)}</div>`;
          });
        });
      });
      const workerFilter = byId("workerFilter").value;
      const workerRows = state.workers.filter(worker => {
        if (workerFilter === "all") return true;
        return workerGroup(worker) === workerFilter;
      });
      byId("workersTable").innerHTML = listbox(workerRows, worker => `
        <div class="list-item">
          <div><div class="list-title">${esc(worker.profile || "Worker")}</div><div class="list-meta">${esc(workerBusinessSummary(worker))}</div><div class="list-meta">Last heartbeat ${esc(readableTime(worker.last_heartbeat_at))}</div></div>
          <span class="pill ${statusClass(worker.status)}">${esc(humanStatus(worker.status))}</span>
        </div>
      `, workerFilter === "history"
        ? "No offline worker history is visible. Current capacity is clean."
        : "No current worker capacity is visible. Start worker services before launching parallel work.");
      const telemetry = state.telemetrySummary;
      const governed = telemetry ? telemetry.governed_performance : null;
      const runtime = telemetry ? telemetry.runtime : null;
      const summaryRows = telemetry ? [
        { name: "Operator summary", value: telemetry.operator_summary, detail: "Human-readable telemetry guidance" },
        { name: "Runtime signal", value: humanStatus(runtime.signal), detail: `${countSentence(runtime.project_count, "project")} and ${countSentence(runtime.problem_job_count, "current problem job")} are visible.` },
        { name: "Governed performance", value: humanStatus(governed.status), detail: `${countSentence(governed.metric_count, "governed metric")} available.` }
      ] : [];
      if (state.operatingPicture) {
        summaryRows.unshift({
          name: "Operating picture",
          value: humanStatus(state.operatingPicture.headline.state),
          detail: state.operatingPicture.headline.business_meaning
        });
      }
      byId("metricsTable").innerHTML = listbox(summaryRows, metric => `
        <div class="list-item">
          <div><div class="list-title">${esc(metric.name)}</div><div class="list-meta">${esc(metric.detail)}</div></div>
          <span class="pill ${statusClass(metric.value)}">${esc(metric.value)}</span>
        </div>
      `, "Telemetry summary is not available yet. Refresh the dashboard or check API readiness.") + `
        <details class="mini" style="margin-top: 10px;">
          <summary>Advanced raw metrics</summary>
          ${listbox(Object.entries(state.metrics).map(([name, value]) => ({ name, value })), metric => `
            <div class="list-item">
              <div><div class="list-title mono">${esc(metric.name)}</div><div class="list-meta">Raw runtime counter or gauge.</div></div>
              <span class="pill info">${esc(metric.value)}</span>
            </div>
          `, "No raw metrics have been emitted yet. Open the dashboard or API routes, then refresh.")}
        </details>
      `;
      const readiness = state.serverReadiness;
      const readinessRows = readiness ? readiness.checks || [] : [];
      byId("serverReadinessTable").innerHTML = readiness ? `
        <div class="mini">
          <strong class="${readiness.status === "ready" ? "ok" : "warn"}">${esc(humanStatus(readiness.status))}</strong>
          <div>${esc(readiness.summary)}</div>
        </div>
        ${listbox(readinessRows, item => `
          <div class="list-item">
            <div><div class="list-title">${esc(item.name)}</div><div class="list-meta">${esc(item.detail)}</div><div class="list-meta">Next: ${esc(item.action)}</div></div>
            <span class="pill ${item.status === "ready" ? "ok" : "warn"}">${esc(humanStatus(item.status))}</span>
          </div>
        `, "No server readiness checks are registered.")}
        <details class="mini" style="margin-top: 10px;">
          <summary>Deployment commands</summary>
          ${listbox(readiness.commands || [], command => `<div class="list-item"><div class="list-title mono">${esc(command)}</div><span class="pill info">run</span></div>`, "No deployment commands are registered.")}
        </details>
      ` : listbox([], item => item, "Server readiness is not available yet. Refresh the dashboard or check API readiness.");
      const choices = state.infrastructureChoices;
      byId("infrastructureChoicesTable").innerHTML = choices ? `
        <div class="mini">
          <strong class="${choices.status === "ready" ? "ok" : "warn"}">${esc(humanStatus(choices.status))}</strong>
          <div>${esc(choices.summary)}</div>
          <div class="muted">Next: ${esc(choices.next_action)}</div>
        </div>
        ${listbox((choices.sections || []).map(section => ({ section })), item => `
          <div class="list-item">
            <div><div class="list-title">${esc(String(item.section).replace(/_/g, " "))}</div><div class="list-meta">This production decision must have a real owner, provider, and proof path.</div></div>
            <span class="pill ${choices.status === "ready" ? "ok" : "warn"}">${esc(choices.status === "ready" ? "recorded" : "needs value")}</span>
          </div>
        `, "No infrastructure decision sections are registered.")}
        <details class="mini" style="margin-top: 10px;">
          <summary>Current findings</summary>
          ${listbox(choices.findings || [], finding => `<div class="list-item"><div class="list-title">${esc(finding)}</div><span class="pill warn">action</span></div>`, "No findings. Real infrastructure choices are recorded.")}
        </details>
      ` : listbox([], item => item, "Infrastructure choices are not available yet. Refresh the dashboard or check API readiness.");
      byId("projectsTable").innerHTML = listbox(state.projects, project => `
        <button class="list-item project-open" data-project-id="${esc(project.id)}">
          <div><div class="list-title">${esc(project.name)}</div><div class="list-meta">${esc(project.repository_path)}</div><div class="list-meta">Updated ${esc(project.updated_at)}</div></div>
          <span class="pill ${statusClass(project.status)}">${esc(humanStatus(project.status))}</span>
        </button>
      `, "No projects are visible yet. Open Factory, attach a client manifest, and start a governed project.");
      document.querySelectorAll(".project-open").forEach(item => {
        item.addEventListener("click", () => {
          byId("projectSelect").value = item.dataset.projectId;
          loadProjectDashboard(item.dataset.projectId);
        });
      });
      const currentProject = byId("projectSelect").value;
      byId("projectSelect").innerHTML = state.projects.map(project =>
        `<option value="${esc(project.id)}">${esc(project.name)}</option>`
      ).join("");
      if (currentProject && state.projects.some(project => project.id === currentProject)) {
        byId("projectSelect").value = currentProject;
      }
      renderMovementGraph();
      renderExecutionDashboard();
      renderManagementGraphs();
      byId("updated").textContent = `Last synchronized ${new Date().toLocaleTimeString()}`;
    }

    function renderProjectIntelligence(payload) {
      const workflow = payload.workflow || {};
      const selectedName = byId("phaseDetail").dataset.phase || "";
      const projectStatus = humanStatus(payload.project.status);
      const workflowStatus = humanStatus(workflow.state || "not_started");
      const workflowLinkStatus = payload.operating_state.degraded ? "Needs workflow link" : "Workflow linked";
      const telemetryStatus = humanStatus(payload.telemetry.signal);
      const economicStatus = humanStatus(payload.economic_effects.viability);
      byId("projectGraph").innerHTML = `
        <div class="cards">
          ${infoCard("Project", payload.project.name, [
            ["Status", projectStatus],
            ["Repository", payload.project.repository_path],
            ["Project ID", payload.project.id]
          ], statusClass(payload.project.status))}
          ${infoCard("Workflow", workflowStatus, [
            ["Current step", workflow.current_step || "No active step"],
            ["Next action", workflow.recommended_operator_action || "Continue with the guided route."]
          ], statusClass(workflow.state || "not_started"))}
          ${infoCard("Link Health", workflowLinkStatus, [
            ["Reason", payload.operating_state.reason || "Project state and workflow tracking agree."],
            ["Action", payload.operating_state.recommended_action || "Continue with the guided route."]
          ], payload.operating_state.degraded ? "warn" : "ok")}
          ${infoCard("Time Estimate", `${payload.estimate.estimated_minutes_remaining} min`, [
            ["Meaning", payload.estimate.label || "Estimated remaining work"],
            ["Confidence", humanStatus(payload.estimate.confidence || "early")],
            ["Historical samples", `${payload.estimate.historical_sample_count || 0}`],
            ["Average phase", `${payload.estimate.average_phase_minutes || 0} min`],
            ["Basis", payload.estimate.basis]
          ], statusClass(payload.estimate.confidence || "early"))}
          ${infoCard("Evidence", `${payload.reuse.work_package_count} packages`, [
            ["Artifacts", `${payload.reuse.artifact_count}`],
            ["Types", payload.reuse.artifact_types.join(", ") || "No artifact types yet"]
          ], "info")}
          ${infoCard("Telemetry", telemetryStatus, [
            ["Phase complete", `${payload.telemetry.phase_completion_percent}%`],
            ["Problems", `${payload.telemetry.problem_count} current problem(s)`]
          ], statusClass(payload.telemetry.signal))}
          ${infoCard("Reusable Template", payload.reuse.template.template_key, [
            ["Project type", payload.reuse.template.project_type],
            ["Use", "Starting point for similar future projects"]
          ], "ok")}
          ${infoCard("Economic Proof", economicStatus, [
            ["Manual work avoided", `${payload.economic_effects.estimated_manual_hours_avoided}h`],
            ["Reuse multiplier", `x${payload.economic_effects.reuse_multiplier}`]
          ], statusClass(payload.economic_effects.viability))}
        </div>
        <div class="phase-graph">
          ${payload.phases.map(phase => `
            <button class="phase-node ${esc(phase.status)} ${phase.name === selectedName ? "selected" : ""}" data-phase="${esc(phase.name)}">
              <strong>${esc(phase.label || phase.name.replace(/_/g, " "))}</strong>
              <span>Status: ${esc(humanStatus(phase.status))}</span>
              <span>Confidence: ${esc(phase.confidence || "Not calibrated")}</span>
              <span>Owner: ${esc(phase.owner_crew || "workflow-engine")}</span>
              <span>Next: ${esc(phase.next_action || "Continue the guided workflow.")}</span>
            </button>
          `).join("")}
        </div>
      `;
      document.querySelectorAll(".phase-node").forEach(node => {
        node.addEventListener("click", () => {
          const phase = payload.phases.find(item => item.name === node.dataset.phase);
          byId("phaseDetail").dataset.phase = phase.name;
          byId("phaseDetail").innerHTML = `
            <div class="cards">
              ${infoCard("Selected Phase", phase.label || phase.name.replace(/_/g, " "), [
                ["Status", humanStatus(phase.status)],
                ["Confidence", phase.confidence || "Not calibrated"],
                ["Owner crew", phase.owner_crew || "workflow-engine"],
                ["Next action", phase.next_action || "Continue the guided workflow."]
              ], statusClass(phase.status))}
              ${infoCard("Completed Evidence", phase.completed_evidence && phase.completed_evidence.length ? `${phase.completed_evidence.length} proof item(s)` : "No proof yet", [
                ["Evidence", (phase.completed_evidence || []).join(", ") || "No evidence recorded for this phase yet."],
                ["Last transition", phase.last_transition_at || "No transition recorded"]
              ], phase.completed_evidence && phase.completed_evidence.length ? "ok" : "warn")}
              ${infoCard("Remaining Work", phase.remaining_work || "Continue the guided workflow.", [
                ["Current issues", `${(phase.current_issues || []).length}`],
                ["Reviewed history", `${(phase.historical_issues || []).length}`]
              ], (phase.current_issues || []).length ? "bad" : "info")}
              ${infoCard("Executed Steps", payload.executed_steps.length ? `${payload.executed_steps.length} done` : "None yet", [
                ["Steps", payload.executed_steps.join(" -> ") || "No transitions recorded"]
              ], payload.executed_steps.length ? "ok" : "warn")}
              ${infoCard("Remaining Steps", payload.remaining_steps.length ? `${payload.remaining_steps.length} left` : "Complete", [
                ["Steps", payload.remaining_steps.join(" -> ") || "No remaining phases"]
              ], payload.remaining_steps.length ? "info" : "ok")}
              ${infoCard("Project Life", `${payload.life.transition_count} transitions`, [
                ["Jobs", `${payload.life.job_count}`],
                ["Meaning", "Recorded project movement and work history"]
              ], "info")}
            </div>
            <div class="mini" style="margin-top: 10px;"><strong>Phase Information</strong><div class="list-meta">Phase confidence, owner crew, executed work, remaining work, and proof are explained here in human language.</div>${table(phase.details.map(detail => ({ detail })), [{ label: "Detail", value: row => row.detail }], "This phase has no transition notes yet.")}</div>
            <div class="grid" style="margin-top: 10px;">
              <div class="mini span-6"><strong>Current Issues</strong><div class="list-meta">Used to show active blockers for the selected phase, with cause and next recovery action.</div>${listbox(phase.current_issues || [], item => `<div class="list-item"><div><div class="list-title">${esc(item.explanation)}</div><div class="list-meta">${esc(item.likely_cause)} Next: ${esc(item.next_action)}</div><details><summary>Diagnostic detail</summary><div class="list-meta">${esc(item.raw_diagnostic || "No raw diagnostic")}</div></details></div><span class="pill ${statusClass(item.status)}">${esc(humanStatus(item.status))}</span></div>`, "This phase has no active blockers. If work fails, the cause and next recovery action will appear here.")}</div>
              <div class="mini span-6"><strong>Reviewed History</strong><div class="list-meta">Used to preserve old problems after they are resolved or acknowledged, so proof is not lost.</div>${listbox(phase.historical_issues || [], item => `<div class="list-item"><div><div class="list-title">${esc(item.explanation)}</div><div class="list-meta">${esc(item.next_action)}</div><details><summary>Diagnostic detail</summary><div class="list-meta">${esc(item.raw_diagnostic || "No raw diagnostic")}</div></details></div><span class="pill info">reviewed history</span></div>`, "No resolved or acknowledged issues are attached to this phase yet. Past problems will appear here after review.")}</div>
              <div class="mini span-6"><strong>Crew Activity</strong>${table(payload.crew, [{ label: "Crew", value: row => row.crew_name }, { label: "Status", value: row => humanStatus(row.status) }, { label: "Error", value: row => row.error_message || "" }], "This table shows which specialist crew worked on the project. No crew run is linked to this phase yet.")}</div>
              <div class="mini span-6"><strong>Project Jobs</strong>${table(payload.jobs, [{ label: "Type", value: row => row.job_type }, { label: "Status", value: row => humanStatus(row.status) }, { label: "Attempts", value: row => row.attempt_count }, { label: "Error", value: row => row.last_error || "" }], "This table shows worker jobs, attempts, and errors. No job history is linked to this project yet.")}</div>
              <div class="mini span-6"><strong>Calibration</strong>${listbox(payload.calibration, item => `<div class="list-item"><div><div class="list-title">${esc(item.name)}</div><div class="list-meta">${esc(item.detail)}</div></div><span class="pill ${statusClass(item.status)}">${esc(humanStatus(item.status))}</span></div>`, "No calibration checks are available yet.")}</div>
              <div class="mini span-6"><strong>Improvements & Solutions</strong>${listbox(payload.improvements, item => `<div class="list-item"><div><div class="list-title">${esc(item.source)}</div><div class="list-meta">${esc(item.recommendation)}</div></div><span class="pill info">${esc(humanStatus(item.status))}</span></div>`, "No improvement proposals are needed right now.")}</div>
              <div class="mini span-6"><strong>Errors Followed</strong>${listbox(payload.errors, item => `<div class="list-item"><div><div class="list-title">${esc(item.explanation)}</div><div class="list-meta">${esc(item.likely_cause)} Next: ${esc(item.next_action)}</div><details><summary>Diagnostic detail</summary><div class="list-meta">${esc(item.raw_diagnostic || "No raw diagnostic")}</div></details></div><span class="pill ${statusClass(item.status)}">${esc(humanStatus(item.status))}</span></div>`, "No active errors are attached to this project. Reviewed history remains preserved in job records.")}</div>
              <div class="mini span-6"><strong>Specialist Agents</strong>${listbox(payload.specialist_agents, item => `<div class="list-item"><div><div class="list-title">${esc(item.agent_key)}</div><div class="list-meta">${esc(item.specialty)} · ${esc(item.mission)}</div></div><span class="pill ok">${esc(humanStatus(item.status))}</span></div>`, "No specialist agents are suggested for this project type yet.")}</div>
              <div class="mini span-6"><strong>Economic Effects</strong>${listbox(Object.entries(payload.economic_effects).map(([name, value]) => ({ name, value })), item => `<div class="list-item"><div><div class="list-title">${esc(item.name)}</div><div class="list-meta">${esc(item.value)}</div></div><span class="pill info">proof</span></div>`, "Economic proof will appear after project evidence is collected.")}</div>
              <div class="mini span-12"><strong>Blueprints of Patterns</strong>${listbox(payload.blueprints, item => {
                const lifecycle = item.lifecycle_detail || {};
                const blockers = (lifecycle.promotion_blockers || []).join(", ") || "No promotion blockers";
                const proposalSummary = (item.improvement_proposals || []).map(proposal => {
                  const evidence = (proposal.evidence_sources || []).map(source => `${source.type}:${source.job_type || source.job_id}`).join(", ") || "evidence source not listed";
                  const evidenceState = proposal.evidence_required ? "evidence required" : "evidence optional";
                  return `${proposal.phase}: ${proposal.proposal_type || "proposal"} · ${evidenceState} · ${proposal.proposal} · source ${evidence} · action ${proposal.operator_action || "Review before reuse."}`;
                }).join(" | ") || "No guardrail or template improvements proposed yet.";
                return `<div class="list-item"><div><div class="list-title">${esc(item.blueprint_key)}</div><div class="list-meta">${esc(item.title)} · ${esc(item.kind)} · ${esc(lifecycle.label || humanStatus(item.lifecycle))} · trust ${esc(lifecycle.trust_level || item.lifecycle)}</div><div class="list-meta">${esc(lifecycle.meaning || "Blueprint lifecycle is waiting for project proof.")}</div><div class="list-meta">Next action: ${esc(lifecycle.next_action || "Collect governed evidence before reuse.")}</div><div class="list-meta">Promotion blockers: ${esc(blockers)}</div><div class="list-meta">Source phase: ${esc(item.source_phase || "project")} · reuse x${esc(item.reuse_proof?.reuse_multiplier || "1")} · assets ${esc(item.reuse_proof?.reusable_asset_count || 0)}</div><details><summary>Improvement proposals</summary><div class="list-meta">${esc(proposalSummary)}</div></details></div><span class="pill ${statusClass(item.lifecycle)}">${esc(lifecycle.label || humanStatus(item.lifecycle))}</span></div>`;
              }, "Reusable blueprints will appear when the project produces enough evidence.")}</div>
            </div>
          `;
          renderProjectIntelligence(payload);
        });
      });
      if (!byId("phaseDetail").innerHTML && payload.phases.length) {
        byId("phaseDetail").dataset.phase = payload.phases[0].name;
        document.querySelector(".phase-node").click();
      }
    }

    async function loadProjectDashboard(projectId) {
      const id = projectId || byId("projectSelect").value;
      if (!id) return;
      const payload = await json(`/api/v1/projects/${id}/intelligence`);
      const url = new URL(window.location.href);
      url.searchParams.set("project", id);
      history.replaceState(null, "", url);
      byId("phaseDetail").innerHTML = "";
      byId("phaseDetail").dataset.phase = "";
      setOrientation(4, "Project graph opened. Check phase, crew, telemetry, issues, proof, then open the demo story when ready.");
      coach(
        "Project Dashboard Open",
        "Use the phase graph first. Click a phase to see steps, crew, calibration, errors, economic proof, and blueprints.",
        ["Review Project", "projects"],
        ["Open Metrics", "metrics"]
      );
      renderProjectIntelligence(payload);
    }

    async function refresh() {
      byId("apiStatus").className = "status muted";
      byId("apiStatus").innerHTML = `<span class="dot"></span>Checking`;
      let dashboardContext = null;
      try {
        dashboardContext = await json("/dashboard/context");
        applyDashboardContext(dashboardContext);
      } catch (error) {
        dashboardContext = null;
      }
      const telemetryUrl = dashboardContext && dashboardContext.organization_id
        ? `/dashboard/telemetry-summary?organization_id=${encodeURIComponent(dashboardContext.organization_id)}`
        : "/dashboard/telemetry-summary";
      const operatingPictureUrl = dashboardContext && dashboardContext.organization_id
        ? `/api/v1/query/operating-picture?organization_id=${encodeURIComponent(dashboardContext.organization_id)}`
        : "/api/v1/query/operating-picture";
      const dashboardManagerUrl = dashboardContext && dashboardContext.organization_id
        ? `/api/v1/query/dashboard-manager?organization_id=${encodeURIComponent(dashboardContext.organization_id)}`
        : "/api/v1/query/dashboard-manager";
      const [ready, jobs, workers, projects, rawMetrics, operatingPicture, dashboardManager, serverReadiness, infrastructureChoices] = await Promise.allSettled([
        json("/health/ready"),
        json("/api/v1/operator/jobs", { headers: actorHeaders }),
        json("/api/v1/operator/jobs/worker-instances", { headers: actorHeaders }),
        json("/api/v1/projects"),
        text("/metrics"),
        json(operatingPictureUrl, { headers: actorHeaders }),
        json(dashboardManagerUrl, { headers: actorHeaders }),
        json("/dashboard/server-readiness"),
        json("/dashboard/infrastructure-choices")
      ]);
      const telemetrySummary = await Promise.allSettled([json(telemetryUrl)]);
      if (ready.status === "fulfilled" && ready.value.status === "ok") {
        byId("apiStatus").className = "status ok";
        byId("apiStatus").innerHTML = `<span class="dot"></span>Ready`;
      } else {
        byId("apiStatus").className = "status bad";
        byId("apiStatus").innerHTML = `<span class="dot"></span>Not ready`;
      }
      state.jobs = jobs.status === "fulfilled" ? jobs.value : [];
      state.workers = workers.status === "fulfilled" ? workers.value : [];
      state.projects = projects.status === "fulfilled" ? projects.value : [];
      state.metrics = rawMetrics.status === "fulfilled" ? parseMetrics(rawMetrics.value) : {};
      state.telemetrySummary = telemetrySummary[0].status === "fulfilled" ? telemetrySummary[0].value : null;
      state.operatingPicture = operatingPicture.status === "fulfilled" ? operatingPicture.value : null;
      state.dashboardManager = dashboardManager.status === "fulfilled" ? dashboardManager.value : null;
      state.serverReadiness = serverReadiness.status === "fulfilled" ? serverReadiness.value : null;
      state.infrastructureChoices = infrastructureChoices.status === "fulfilled" ? infrastructureChoices.value : null;
      state.sources = {
        ready: sourceStatus(ready, "API", "overview", ready.status === "fulfilled" && ready.value.status === "ok" ? "Service is ready" : "Service readiness is not confirmed"),
        jobs: sourceStatus(jobs, "Work", "problems", `${state.jobs.length} tracked job(s)`),
        workers: sourceStatus(workers, "Crew", "problems", `${state.workers.length} worker signal(s)`),
        projects: sourceStatus(projects, "Projects", "projects", `${countSentence(state.projects.length, "project")} visible`),
        metrics: sourceStatus(rawMetrics, "Telemetry", "metrics", `${Object.keys(state.metrics).length} raw signal(s), ${state.telemetrySummary?.governed_performance?.metric_count ?? 0} governed metric(s)`),
        query: sourceStatus(operatingPicture, "Operating Picture", "overview", state.operatingPicture ? state.operatingPicture.headline.summary : "Operating picture connection needs attention"),
        manager: sourceStatus(dashboardManager, "Execution Manager", "execution", state.dashboardManager ? state.dashboardManager.headline.summary : "Execution manager connection needs attention"),
        server: sourceStatus(serverReadiness, "Server Readiness", "metrics", state.serverReadiness ? state.serverReadiness.summary : "Server readiness connection needs attention"),
        infrastructure: sourceStatus(infrastructureChoices, "Infrastructure Choices", "metrics", state.infrastructureChoices ? state.infrastructureChoices.summary : "Infrastructure choices connection needs attention")
      };
      state.sources = dashboardManagerSources(state.sources);
      render();
      renderSourceStrip();
      renderBusinessBoard();
      renderEcosystemModules();
    }

    document.querySelectorAll(".tab").forEach(tab => {
      tab.addEventListener("click", () => {
        switchView(tab.dataset.view);
        const guidance = {
          overview: ["Enterprise Overview", "Read the business board first, then follow Guided Route. It shows the next clear action."],
          execution: ["Execution Guide", "Click a project node to see phase, task counts, active crew signals, events, telemetry, and next action."],
          factory: ["Factory Guide", "Add a client idea or manifesto. Choose direction, check repository details, then start work."],
          problems: ["Problems Guide", "Use this when work is stuck. Resolve issues before scaling more parallel work."],
          metrics: ["Telemetry Guide", "Use metrics as proof that the system is alive and work is measurable."],
          projects: ["Projects Guide", "Open one project. The graph explains phase, crew, jobs, proof, and remaining work."],
          graph: ["Blueprint Guide", "Use graph context and blueprints when proof must become reusable structure."]
        };
        const [title, message] = guidance[tab.dataset.view] || guidance.overview;
        coach(title, message, ["Continue Here", tab.dataset.view], ["Open Projects", "projects"]);
      });
    });
    byId("refresh").addEventListener("click", refresh);
    byId("coachPrimary").addEventListener("click", event => goTarget(event.currentTarget.dataset.target));
    byId("coachSecondary").addEventListener("click", event => goTarget(event.currentTarget.dataset.target));
    byId("orientationAction").addEventListener("click", event => goTarget(event.currentTarget.dataset.target));
    byId("jobFilter").addEventListener("change", render);
    byId("workerFilter").addEventListener("change", render);
    byId("loadProject").addEventListener("click", () => loadProjectDashboard());
    byId("clarifyVision").addEventListener("click", clarifyVision);
    byId("checkEcosystemGraph").addEventListener("click", () => checkAuthenticatedGraph("ecosystem"));
    byId("checkEvidenceGraph").addEventListener("click", () => checkAuthenticatedGraph("evidence"));
    byId("manifestFile").addEventListener("change", event => {
      const file = event.target.files[0];
      if (!file) return;
      loadManifestFile(file).catch(error => {
        byId("factoryStatus").textContent = `Manifesto error: ${error.message}`;
      });
    });
    byId("previewFactory").addEventListener("click", previewFactoryLaunch);
    byId("startFactory").addEventListener("click", () => {
      startFactoryProject().catch(error => {
        byId("factoryStatus").textContent = friendlyLaunchError(error);
        coach(
          "Factory Launch Stopped",
          friendlyLaunchError(error),
          ["Fix Details", "factory"],
          ["Open Projects", "projects"]
        );
      });
    });
    byId("startManifestBatch").addEventListener("click", () => {
      startManifestBatch().catch(error => {
        byId("factoryStatus").textContent = friendlyLaunchError(error);
        coach(
          "Batch Launch Stopped",
          friendlyLaunchError(error),
          ["Fix Manifesto", "factory"],
          ["Open Projects", "projects"]
        );
      });
    });
    byId("previewMockFactory").addEventListener("click", () => {
      previewMockFactoryTest().catch(error => {
        byId("factoryStatus").textContent = friendlyLaunchError(error);
        coach(
          "Mock Factory Preview Failed",
          friendlyLaunchError(error),
          ["Review Factory", "factory"],
          ["Open Problems", "problems"]
        );
      });
    });
    byId("startMockFactory").addEventListener("click", () => {
      startMockFactoryTest().catch(error => {
        byId("factoryStatus").textContent = friendlyLaunchError(error);
        coach(
          "Mock Factory Stopped",
          friendlyLaunchError(error),
          ["Review Factory", "factory"],
          ["Open Problems", "problems"]
        );
      });
    });
    byId("loadWorkflow").addEventListener("click", async () => {
      const workflowId = byId("workflowId").value.trim();
      if (!workflowId) return;
      try {
        const [workflow, history] = await Promise.all([
          json(`/api/v1/workflows/${workflowId}`),
          json(`/api/v1/workflows/${workflowId}/history`)
        ]);
        byId("workflowDetail").innerHTML = `<div class="cards"><div class="mini"><strong>${esc(workflow.state)}</strong><div>${esc(workflow.current_step || "No active step")}</div><div class="muted">${esc(workflow.recommended_operator_action || "")}</div></div></div>` +
          table(history, [
            { label: "From", value: row => row.previous_state },
            { label: "To", value: row => row.current_state },
            { label: "Actor", value: row => row.actor_id },
            { label: "At", value: row => row.occurred_at }
          ]);
      } catch (error) {
        byId("workflowDetail").innerHTML = `<div class="mini bad">${esc(error.message)}</div>`;
      }
    });

    function animateField() {
      const canvas = byId("field");
      const ctx = canvas.getContext("2d");
      function resize() {
        canvas.width = window.innerWidth * devicePixelRatio;
        canvas.height = window.innerHeight * devicePixelRatio;
      }
      window.addEventListener("resize", resize);
      resize();
      let tick = 0;
      function frame() {
        tick += 0.006;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.strokeStyle = "rgba(93, 184, 255, 0.22)";
        ctx.lineWidth = devicePixelRatio;
        const spacing = 44 * devicePixelRatio;
        for (let x = -spacing; x < canvas.width + spacing; x += spacing) {
          ctx.beginPath();
          ctx.moveTo(x + Math.sin(tick + x * 0.002) * 18, 0);
          ctx.lineTo(x - 120, canvas.height);
          ctx.stroke();
        }
        for (let y = 0; y < canvas.height + spacing; y += spacing) {
          ctx.beginPath();
          ctx.moveTo(0, y + Math.cos(tick + y * 0.002) * 16);
          ctx.lineTo(canvas.width, y - 100);
          ctx.stroke();
        }
        requestAnimationFrame(frame);
      }
      frame();
    }
    animateField();
    renderCapabilities();
    setOrientation(0, "Start here: write a client idea or attach a manifesto in Factory.");
    refresh().then(() => {
      const projectId = new URL(window.location.href).searchParams.get("project");
      if (projectId) {
        switchView("projects");
        byId("projectSelect").value = projectId;
        loadProjectDashboard(projectId);
      } else if (window.location.hash) {
        switchView(window.location.hash.slice(1));
      }
    });
    window.addEventListener("hashchange", () => {
      if (window.location.hash) {
        switchView(window.location.hash.slice(1));
      }
    });
    setInterval(refresh, 15000);
  </script>
</body>
</html>
"""


DEMO_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Enterprise Demo Story</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #07090d;
      --panel: rgba(13, 18, 24, 0.9);
      --border: rgba(143, 166, 190, 0.24);
      --text: #edf4fb;
      --muted: #a6b4c2;
      --green: #56e39f;
      --blue: #5db8ff;
      --amber: #ffd166;
      --cyan: #5db8ff;
      --gold: #ffd166;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      background: radial-gradient(circle at 18% 18%, rgba(93, 184, 255, 0.22), transparent 30%),
        radial-gradient(circle at 88% 12%, rgba(86, 227, 159, 0.16), transparent 26%),
        linear-gradient(135deg, #07090d, #0c1117 52%, #06080b);
    }
    .shell { width: min(1180px, calc(100vw - 32px)); margin: 0 auto; padding: 28px 0 40px; }
    header { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 18px; }
    h1 { margin: 0 0 6px; font-size: clamp(1.7rem, 4vw, 3rem); letter-spacing: 0; }
    p { color: var(--muted); line-height: 1.45; }
    a, button {
      min-height: 38px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: rgba(15, 23, 31, 0.86);
      color: var(--text);
      padding: 0 12px;
      font-weight: 700;
      text-decoration: none;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }
    .hero, .panel {
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--panel);
      padding: 18px;
      box-shadow: 0 18px 60px rgba(0, 0, 0, 0.28);
    }
    .hero { min-height: 240px; display: grid; align-content: center; margin-bottom: 14px; }
    .hero strong { color: var(--green); }
    .grid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 12px; }
    .span-4 { grid-column: span 4; }
    .span-6 { grid-column: span 6; }
    .span-12 { grid-column: span 12; }
    .story-map {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 10px;
    }
    .node {
      min-height: 142px;
      border: 1px solid rgba(143, 166, 190, 0.22);
      border-radius: 8px;
      background: rgba(5, 10, 15, 0.76);
      padding: 12px;
      text-align: left;
      display: grid;
      align-content: space-between;
      gap: 8px;
    }
    .node[aria-pressed="true"] {
      border-color: rgba(93, 184, 255, 0.9);
      background: rgba(93, 184, 255, 0.15);
    }
    .node span { color: var(--muted); font-size: 0.86rem; line-height: 1.35; }
    .pill { color: var(--green); font-weight: 800; font-size: 0.78rem; }
    .output { min-height: 210px; }
    .output h2 { margin-top: 0; }
    .checklist { display: grid; gap: 8px; }
    .check {
      border: 1px solid rgba(143, 166, 190, 0.18);
      border-radius: 8px;
      padding: 10px;
      background: rgba(7, 12, 18, 0.7);
    }
    .check strong { display: block; margin-bottom: 4px; }
    .walkthrough {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px;
    }
    .step-card {
      min-height: 186px;
      border: 1px solid rgba(143, 166, 190, 0.22);
      border-radius: 8px;
      background: rgba(5, 10, 15, 0.78);
      padding: 12px;
      display: grid;
      grid-template-columns: 42px 1fr;
      gap: 10px;
      align-content: start;
    }
    .step-number {
      width: 34px;
      height: 34px;
      border-radius: 8px;
      display: grid;
      place-items: center;
      color: #031018;
      background: linear-gradient(135deg, var(--gold), var(--cyan));
      font-weight: 900;
    }
    .step-card strong { display: block; margin-bottom: 6px; }
    .step-card span {
      display: block;
      color: var(--muted);
      font-size: 0.88rem;
      line-height: 1.35;
      margin-bottom: 10px;
    }
    .step-card a {
      width: fit-content;
      min-height: 36px;
      padding: 8px 12px;
      font-size: 0.82rem;
    }
    .operator-console {
      display: grid;
      gap: 10px;
      border-color: rgba(93, 184, 255, 0.36);
    }
    .live-proof {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }
    .proof-card {
      border: 1px solid rgba(143, 166, 190, 0.2);
      border-radius: 8px;
      background: rgba(5, 10, 15, 0.76);
      padding: 12px;
      min-height: 94px;
      color: var(--text);
      text-align: left;
      text-decoration: none;
      display: block;
    }
    .proof-card:hover { border-color: rgba(93, 184, 255, 0.72); }
    .proof-card.ok { border-color: rgba(86, 227, 159, 0.48); }
    .proof-card.warn { border-color: rgba(255, 209, 102, 0.54); }
    .proof-card.bad { border-color: rgba(255, 107, 107, 0.58); }
    .proof-card span {
      display: block;
      color: var(--muted);
      font-size: 0.74rem;
      font-weight: 800;
      text-transform: uppercase;
      margin-bottom: 6px;
    }
    .proof-card strong {
      display: block;
      font-size: 1.05rem;
      line-height: 1.22;
      overflow-wrap: anywhere;
    }
    .proof-card small {
      display: block;
      color: var(--muted);
      line-height: 1.35;
      margin-top: 6px;
    }
    .proof-toolbar {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      margin-bottom: 10px;
    }
    .proof-toolbar p { margin: 0; }
    .console-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 8px;
    }
    .console-cell {
      border: 1px solid rgba(143, 166, 190, 0.18);
      border-radius: 8px;
      background: rgba(5, 10, 15, 0.72);
      padding: 10px;
      min-height: 86px;
    }
    .console-cell span {
      display: block;
      color: var(--muted);
      font-size: 0.75rem;
      font-weight: 800;
      text-transform: uppercase;
      margin-bottom: 5px;
    }
    .console-cell strong {
      display: block;
      line-height: 1.24;
      overflow-wrap: anywhere;
    }
    .console-actions { display: flex; flex-wrap: wrap; gap: 8px; }
    .demo-action {
      border-color: rgba(93, 184, 255, 0.42);
    }
    @media (max-width: 900px) {
      header { flex-direction: column; align-items: flex-start; }
      .span-4, .span-6 { grid-column: span 12; }
      .step-card { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div>
        <h1>AI Enterprise Demo Story</h1>
        <p>Show how a rough idea becomes a supervised, tested, business-ready project.</p>
      </div>
      <a href="/dashboard">Open Command Center</a>
    </header>

    <section class="hero">
      <h2>One sentence</h2>
      <p><strong>AI Enterprise is a factory for ideas.</strong> It listens, creates options, lets the human choose, assigns specialist crews, verifies quality, and prepares the result for production and market presentation.</p>
    </section>

    <section aria-live="polite">
      <div class="proof-toolbar">
        <p id="proofChecked">Live proof not checked yet.</p>
        <button id="refreshProof">Refresh Live Proof</button>
      </div>
      <div class="live-proof">
        <a id="proofHealthCard" class="proof-card" href="/dashboard"><span>API health</span><strong id="proofHealth">Checking</strong><small id="proofHealthDetail">Verifying the enterprise service.</small></a>
        <a id="proofProjectsCard" class="proof-card" href="/dashboard#projects"><span>Visible projects</span><strong id="proofProjects">Checking</strong><small id="proofProjectsDetail">Counting governed project records.</small></a>
        <a id="proofTelemetryCard" class="proof-card" href="/dashboard#metrics"><span>Telemetry</span><strong id="proofTelemetry">Checking</strong><small id="proofTelemetryDetail">Reading runtime proof signals.</small></a>
        <a id="proofNextCard" class="proof-card" href="/dashboard#factory"><span>Next live step</span><strong id="proofNext">Open Factory</strong><small id="proofNextDetail">Preview before creating records.</small></a>
      </div>
    </section>

    <section class="grid">
      <article class="panel span-12">
        <h2>Idea to Reality Map</h2>
        <div id="storyMap" class="story-map"></div>
      </article>
      <article class="panel span-12">
        <h2>Step-by-Step Live Demo</h2>
        <div class="walkthrough">
          <div class="step-card"><div class="step-number">1</div><div><strong>Understand the story</strong><span>Start here. Touch each phase in the map and explain how an idea becomes governed work.</span><button class="demo-action" data-demo-step="0">Explain</button></div></div>
          <div class="step-card"><div class="step-number">2</div><div><strong>Open the factory</strong><span>Go to the Manifesto Launcher. This is where a client document becomes a project.</span><button class="demo-action" data-demo-step="1">Explain Factory</button></div></div>
          <div class="step-card"><div class="step-number">3</div><div><strong>Preview a mock project</strong><span>Use Preview Mock Factory Test to see the prepared manifesto, project type, and launch path.</span><button class="demo-action" data-demo-step="2">Explain Preview</button></div></div>
          <div class="step-card"><div class="step-number">4</div><div><strong>Start the process</strong><span>Use Start Manifesto Batch when you want the factory to create and start governed work.</span><button class="demo-action" data-demo-step="3">Explain Start</button></div></div>
          <div class="step-card"><div class="step-number">5</div><div><strong>Watch execution</strong><span>Open the live graph to see projects, tasks, crews, events, and current movement.</span><button class="demo-action" data-demo-step="4">Explain Execution</button></div></div>
          <div class="step-card"><div class="step-number">6</div><div><strong>Inspect a project</strong><span>Open Projects to see phase status, artifacts, remaining work, proof, and risks.</span><button class="demo-action" data-demo-step="5">Explain Project</button></div></div>
          <div class="step-card"><div class="step-number">7</div><div><strong>Check telemetry</strong><span>Open Metrics to verify health, runtime signals, queue pressure, and evidence.</span><button class="demo-action" data-demo-step="6">Explain Metrics</button></div></div>
          <div class="step-card"><div class="step-number">8</div><div><strong>Save the proof</strong><span>Open the Documentation Hub to read, preview, and download the operating documents.</span><button class="demo-action" data-demo-step="7">Explain Docs</button></div></div>
        </div>
      </article>
      <article class="panel span-12 operator-console">
        <h2>Demo Operator Console</h2>
        <p id="consoleMessage">Start with the story map, then use the guided buttons. This console explains the next action before you open another dashboard.</p>
        <div class="console-grid">
          <div class="console-cell"><span>Where to go</span><strong id="consoleTarget">Stay on Demo Story</strong></div>
          <div class="console-cell"><span>What to verify</span><strong id="consoleProof">The idea-to-reality route is clear.</strong></div>
          <div class="console-cell"><span>Business meaning</span><strong id="consoleMeaning">The client can see how an idea becomes controlled work.</strong></div>
        </div>
        <div class="console-actions">
          <a id="consoleOpen" href="/dashboard/demo">Open Selected Step</a>
          <a href="/dashboard#factory">Open Factory</a>
          <a href="/dashboard#execution">Open Execution</a>
        </div>
      </article>
      <article class="panel span-6 output">
        <h2 id="storyTitle">Start with the idea</h2>
        <p id="storyText">A person can explain badly or incompletely. The system still listens and turns the idea into clear options.</p>
      </article>
      <article class="panel span-6">
        <h2>Supervision and Quality</h2>
        <div class="checklist">
          <div class="check"><strong>Human choice</strong><span>The client chooses practical, growth, or visionary direction.</span></div>
          <div class="check"><strong>Agent crew</strong><span>Specialists work by phase: requirements, architecture, build, test, security, and delivery.</span></div>
          <div class="check"><strong>Proof</strong><span>Every project shows telemetry, errors, economic value, and reusable blueprints.</span></div>
          <div class="check"><strong>Marketing platform</strong><span>The same proof becomes a story clients can understand and trust.</span></div>
        </div>
      </article>
      <article class="panel span-4"><h2>For Clients</h2><p>They see options, route, proof, and progress. That makes the idea easier to understand, trust, and buy.</p></article>
      <article class="panel span-4"><h2>For the Enterprise</h2><p>Each finished project becomes reusable knowledge. The brand improves module by module.</p></article>
      <article class="panel span-4"><h2>For Market Growth</h2><p>The platform turns delivery proof into a clear story for sales, consulting, and long-term partnerships.</p></article>
    </section>
  </main>

  <script>
    const steps = [
      ["Rough Idea", "Listen first. Even poor input can contain a real business signal.", "listen"],
      ["Three Options", "Show practical, growth, and visionary versions so the client can decide.", "choose"],
      ["Project Factory", "Create a governed project from the chosen direction.", "create"],
      ["AI Crew", "Specialist agents work under supervision and evidence.", "work"],
      ["Quality Gate", "Verify, debug, measure risk, and prevent repeated mistakes.", "verify"],
      ["Production Route", "Prepare the path from working result to release.", "release"],
      ["Market Story", "Turn proof into a clear offer that clients understand.", "sell"],
      ["Evolution", "Capture blueprints so the next project starts stronger.", "evolve"]
    ];
    const demoActions = [
      ["Stay on Demo Story", "Use the map to explain the factory concept before touching live work.", "The person understands the full route from idea to reusable proof.", "The demo is a business story, not only a technical screen.", "/dashboard/demo"],
      ["Open Factory", "Open Manifesto Launcher, then use Preview Launch before creating records.", "Launch Result shows readiness, missing data, and Project Readiness.", "The operator can start work without guessing what will happen.", "/dashboard#factory"],
      ["Preview Mock Factory", "Press Preview Mock Factory or Preview Launch for a no-risk check.", "No records are created during preview; readiness is visible first.", "Supervised launch prevents accidental or unclear project creation.", "/dashboard#factory"],
      ["Start Process", "Use Start Process for one project or Start Manifesto Batch for portfolio work.", "The Launch Result shows created, reused, blocked, failed, and inspect-first signals.", "The enterprise starts production work with a clear proof path.", "/dashboard#factory"],
      ["Open Execution", "Watch the live project graph, task counts, crew signals, events, and telemetry.", "Project movement appears as graph nodes and human-readable status.", "The factory proves it is working, not only storing records.", "/dashboard#execution"],
      ["Open Projects", "Select a project and inspect phases, evidence, remaining work, risks, and blueprints.", "Phase confidence, owner crew, completed work, and remaining work are visible.", "A client can understand where the product is and what comes next.", "/dashboard#projects"],
      ["Open Metrics", "Check Server Readiness, Real Infrastructure Choices, and telemetry health.", "Health, migration readiness, and operating signals are visible.", "The system can prepare for server migration and production operation.", "/dashboard#metrics"],
      ["Open Docs", "Open the Documentation Hub and preview or download the working documents.", "Operator guides, manifest templates, and proof documents are available.", "The result can be shared, repeated, and improved.", "/dashboard/documentation-hub"]
    ];
    const map = document.getElementById("storyMap");
    const title = document.getElementById("storyTitle");
    const text = document.getElementById("storyText");
    const consoleMessage = document.getElementById("consoleMessage");
    const consoleTarget = document.getElementById("consoleTarget");
    const consoleProof = document.getElementById("consoleProof");
    const consoleMeaning = document.getElementById("consoleMeaning");
    const consoleOpen = document.getElementById("consoleOpen");
    async function fetchText(url) {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`${response.status}`);
      return response.text();
    }
    async function fetchJson(url) {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`${response.status}`);
      return response.json();
    }
    function setProof(id, value, detail, state = "warn", href = "") {
      document.getElementById(id).textContent = value;
      document.getElementById(`${id}Detail`).textContent = detail;
      const card = document.getElementById(`${id}Card`);
      if (card) {
        card.classList.remove("ok", "warn", "bad");
        card.classList.add(state);
        if (href) card.href = href;
      }
    }
    async function loadLiveProof() {
      document.getElementById("proofChecked").textContent = "Checking live proof now...";
      try {
        const ready = await fetchJson("/health/ready");
        const ok = ready.status === "ok" && ready.database === "reachable";
        setProof("proofHealth", ok ? "Ready" : "Needs attention", ok ? "Database is reachable. Click to open Command Center." : "Database readiness is not confirmed. Click to inspect Command Center.", ok ? "ok" : "bad", "/dashboard");
      } catch (error) {
        setProof("proofHealth", "Not confirmed", "Refresh after the API finishes starting. If it stays unavailable, click to open Command Center.", "bad", "/dashboard");
      }
      try {
        const projects = await fetchJson("/api/v1/projects");
        setProof("proofProjects", `${projects.length} project(s)`, projects.length ? "Click to open Projects and inspect movement." : "Click to open Factory and create the first project.", projects.length ? "ok" : "warn", projects.length ? "/dashboard#projects" : "/dashboard#factory");
        setProof("proofNext", projects.length ? "Open Execution" : "Open Factory", projects.length ? "Click to watch live project movement." : "Click to preview before creating records.", "ok", projects.length ? "/dashboard#execution" : "/dashboard#factory");
      } catch (error) {
        setProof("proofProjects", "Not confirmed", "Project source is not reachable yet. Click to open Command Center if it remains unavailable.", "bad", "/dashboard");
        setProof("proofNext", "Open Command Center", "Click to check source freshness and API health before demonstrating project movement.", "warn", "/dashboard");
      }
      try {
        const metrics = await fetchText("/metrics");
        const count = metrics.split("\n").filter(line => line && !line.startsWith("#")).length;
        setProof("proofTelemetry", `${count} signal(s)`, count ? "Runtime telemetry is available. Click to open Metrics." : "No runtime signal has been emitted yet. Click to open Metrics.", count ? "ok" : "warn", "/dashboard#metrics");
      } catch (error) {
        setProof("proofTelemetry", "Not confirmed", "Metrics source is not reachable yet. Click to open Metrics after the API settles.", "bad", "/dashboard#metrics");
      }
      document.getElementById("proofChecked").textContent = `Live proof checked ${new Date().toLocaleTimeString()}.`;
    }
    function showDemoAction(index = 0) {
      const action = demoActions[index] || demoActions[0];
      consoleTarget.textContent = action[0];
      consoleMessage.textContent = action[1];
      consoleProof.textContent = action[2];
      consoleMeaning.textContent = action[3];
      consoleOpen.href = action[4];
      consoleOpen.textContent = action[0];
    }
    function render(selected = 0) {
      map.innerHTML = steps.map((step, index) => `
        <button class="node" aria-pressed="${index === selected}" data-index="${index}">
          <strong>${step[0]}</strong>
          <span>${step[1]}</span>
          <span class="pill">${step[2]}</span>
        </button>
      `).join("");
      title.textContent = steps[selected][0];
      text.textContent = steps[selected][1];
      document.querySelectorAll(".node").forEach(node => {
        node.addEventListener("click", () => render(Number(node.dataset.index)));
      });
    }
    document.querySelectorAll(".demo-action").forEach(button => {
      button.addEventListener("click", () => showDemoAction(Number(button.dataset.demoStep)));
    });
    document.getElementById("refreshProof").addEventListener("click", loadLiveProof);
    showDemoAction(0);
    loadLiveProof();
    render();
  </script>
</body>
</html>
"""
