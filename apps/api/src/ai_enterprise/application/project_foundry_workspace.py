from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.api.project_formation_schemas import (
    FoundryWorkspaceRequest,
    FoundryWorkspaceResponse,
)
from ai_enterprise.application.audit.writer import AuditWriter
from ai_enterprise.config import Settings
from ai_enterprise.domain.hashing import hash_json
from ai_enterprise.infrastructure.database.models import ProjectModel


class ProjectFoundryWorkspaceError(Exception):
    def __init__(self, message: str, *, missing_information: list[str] | None = None) -> None:
        super().__init__(message)
        self.missing_information = missing_information or []


@dataclass(frozen=True, slots=True)
class FoundryFile:
    relative_path: str
    content: str


class ProjectFoundryWorkspaceService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def generate_workspace(
        self,
        project_id: uuid.UUID,
        request: FoundryWorkspaceRequest,
        *,
        actor_id: str,
    ) -> FoundryWorkspaceResponse:
        project = await self._session.get(ProjectModel, project_id)
        if project is None:
            raise ProjectFoundryWorkspaceError("Project not found")

        intake = self._normalize_intake(project, request.intake)
        missing = self._missing_information(intake)
        if missing:
            raise ProjectFoundryWorkspaceError(
                "Foundry intake needs more information before a workspace can be created.",
                missing_information=missing,
            )

        workspace = self._workspace_path(project, request.workspace_path)
        project.repository_path = str(workspace)
        if request.github_repository_url:
            project.repository_url = request.github_repository_url
        project.updated_at = datetime.now(UTC)

        created_directories = self._create_directories(workspace)
        files = self._files(project, intake)
        created_files: list[str] = []
        reused_files: list[str] = []
        for item in files:
            target = workspace / item.relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and not request.overwrite_existing:
                reused_files.append(item.relative_path)
                continue
            target.write_text(item.content, encoding="utf-8")
            created_files.append(item.relative_path)

        template_root = self._repo_root() / "templates" / "project-foundry"
        self._copy_template_file(
            template_root / "ROOT_AGENTS.md",
            workspace / "AGENTS.md",
            "AGENTS.md",
            created_files=created_files,
            reused_files=reused_files,
            overwrite=request.overwrite_existing,
        )
        self._copy_template_file(
            template_root / "prompts" / "README.md",
            workspace / "prompts" / "README.md",
            "prompts/README.md",
            created_files=created_files,
            reused_files=reused_files,
            overwrite=request.overwrite_existing,
        )

        proof = {
            "workspace_path": str(workspace),
            "intake_hash": hash_json(intake),
            "created_file_count": len(created_files),
            "reused_file_count": len(reused_files),
            "schema": "aeos.project_intake.v1",
            "source": "project-foundry-workspace-runtime-v1",
        }
        await AuditWriter(self._session).append_project_event(
            project_id=project.id,
            event_type="project_foundry.workspace_generated",
            actor_type="human",
            actor_id=actor_id,
            payload={
                "workspace_path": str(workspace),
                "github_repository_url": request.github_repository_url,
                "created_files": created_files,
                "reused_files": reused_files,
                "proof": proof,
            },
        )
        await self._session.commit()

        return FoundryWorkspaceResponse(
            project_id=project.id,
            status="workspace_ready",
            workspace_path=str(workspace),
            github_repository_url=project.repository_url,
            created_files=created_files,
            reused_files=reused_files,
            created_directories=created_directories,
            missing_information=[],
            next_action=(
                "Open the workspace, review PROJECT.yaml and intake/project-intake.yaml, "
                "then create or connect the GitHub repository before execution starts."
            ),
            proof=proof,
        )

    def _workspace_path(self, project: ProjectModel, requested: str | None) -> Path:
        raw = Path(requested or project.repository_path).expanduser()
        workspace = raw.resolve()
        allowed_root = self._settings.repository_allowed_root.expanduser().resolve()
        try:
            workspace.relative_to(allowed_root)
        except ValueError as exc:
            raise ProjectFoundryWorkspaceError(
                f"Workspace must be inside the allowed repository root: {allowed_root}"
            ) from exc
        return workspace

    def _normalize_intake(self, project: ProjectModel, intake: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(intake)
        project_section = dict(normalized.get("project") or {})
        project_section.setdefault("name", project.name)
        project_section.setdefault("description", project.description)
        project_section.setdefault(
            "business_objective",
            project.manifest.get("expected_outcome", project.description)
            if isinstance(project.manifest, dict)
            else project.description,
        )
        project_section.setdefault(
            "project_type",
            project.manifest.get("project_type", "enterprise_project")
            if isinstance(project.manifest, dict)
            else "enterprise_project",
        )
        normalized["project"] = project_section
        return normalized

    def _missing_information(self, intake: dict[str, Any]) -> list[str]:
        required_sections = (
            "project",
            "scope",
            "functional_requirements",
            "non_functional_requirements",
            "technical_constraints",
            "delivery",
            "authority",
        )
        missing: list[str] = []
        for section in required_sections:
            if not intake.get(section):
                missing.append(f"{section} section")

        project = self._dict_section(intake, "project")
        for field in (
            "name",
            "description",
            "business_objective",
            "target_users",
            "project_type",
            "expected_outcomes",
        ):
            if not project.get(field):
                missing.append(f"project.{field}")

        if not isinstance(intake.get("functional_requirements"), list):
            missing.append("functional_requirements list")
        return list(dict.fromkeys(missing))

    def _create_directories(self, workspace: Path) -> list[str]:
        directories = (
            "governance",
            "intake",
            "requirements",
            "architecture/decisions",
            "architecture/diagrams",
            "architecture/api-contracts",
            "architecture/data-model",
            "planning",
            "agents/orchestrator",
            "agents/architect",
            "agents/backend",
            "agents/frontend",
            "agents/security",
            "agents/testing",
            "agents/release",
            "prompts/intake",
            "prompts/architecture",
            "prompts/implementation",
            "prompts/review",
            "prompts/release",
            "src",
            "tests/unit",
            "tests/integration",
            "tests/contract",
            "tests/security",
            "tests/acceptance",
            "infrastructure",
            "deployment",
            "operations/runbooks",
            "operations/monitoring",
            "operations/incident-response",
            "reports/agent-runs",
            "reports/reviews",
            "reports/release",
            "artifacts",
        )
        created: list[str] = []
        workspace.mkdir(parents=True, exist_ok=True)
        for relative in directories:
            path = workspace / relative
            existed = path.exists()
            path.mkdir(parents=True, exist_ok=True)
            if not existed:
                created.append(relative)
        return created

    def _files(self, project: ProjectModel, intake: dict[str, Any]) -> list[FoundryFile]:
        requirements = intake.get("functional_requirements") or []
        scope = self._dict_section(intake, "scope")
        delivery = self._dict_section(intake, "delivery")
        authority = self._dict_section(intake, "authority")
        constraints = intake.get("technical_constraints")
        non_functional = intake.get("non_functional_requirements")
        return [
            FoundryFile("README.md", self._readme(project, intake)),
            FoundryFile("PROJECT.yaml", self._yaml(self._project_contract(project, intake))),
            FoundryFile("intake/project-intake.yaml", self._yaml(intake)),
            FoundryFile(
                "intake/assumptions.md",
                self._markdown_list("Assumptions", scope.get("assumptions", [])),
            ),
            FoundryFile(
                "intake/constraints.md",
                self._markdown_list("Constraints", scope.get("included", [])),
            ),
            FoundryFile(
                "requirements/requirements.yaml",
                self._yaml({"requirements": requirements}),
            ),
            FoundryFile(
                "requirements/requirements.md",
                self._requirements_markdown(requirements),
            ),
            FoundryFile("requirements/traceability.csv", self._traceability_csv(requirements)),
            FoundryFile(
                "governance/authority-policy.yaml",
                self._yaml(
                    {
                        "allowed_actions": authority.get("allowed_actions", []),
                        "approval_required": authority.get("approval_required", []),
                        "prohibited_actions": authority.get("prohibited_actions", []),
                        "secret_access_policy": authority.get(
                            "secret_access_policy", "not specified"
                        ),
                        "production_access_policy": authority.get(
                            "production_access_policy", "human approval required"
                        ),
                    }
                ),
            ),
            FoundryFile(
                "governance/approval-matrix.yaml",
                self._yaml(
                    {
                        "production_deployment": {
                            "creator_may_approve": False,
                            "required_roles": ["human_owner", "security_reviewer"],
                        },
                        "repository_write": {
                            "creator_may_approve": False,
                            "required_roles": ["human_owner"],
                        },
                    }
                ),
            ),
            FoundryFile(
                "governance/risk-policy.yaml",
                self._yaml({"risks": self._risks(intake)}),
            ),
            FoundryFile("governance/definition-of-done.md", self._definition_of_done()),
            FoundryFile(
                "planning/execution-plan.yaml",
                self._yaml(
                    {
                        "phases": [
                            "intake",
                            "requirements",
                            "architecture",
                            "implementation",
                            "verification",
                            "release",
                        ],
                        "milestones": delivery.get("milestones", []),
                        "deployment_method": delivery.get(
                            "deployment_method", "not specified"
                        ),
                    }
                ),
            ),
            FoundryFile(
                "planning/dependency-graph.yaml",
                self._yaml(
                    {
                        "nodes": [
                            "intake",
                            "requirements",
                            "architecture",
                            "implementation",
                            "verification",
                            "release",
                        ],
                        "edges": [
                            ["intake", "requirements"],
                            ["requirements", "architecture"],
                            ["architecture", "implementation"],
                            ["implementation", "verification"],
                            ["verification", "release"],
                        ],
                    }
                ),
            ),
            FoundryFile(
                "planning/milestones.yaml",
                self._yaml({"milestones": delivery.get("milestones", [])}),
            ),
            FoundryFile(
                "planning/risk-register.yaml",
                self._yaml({"risks": self._risks(intake)}),
            ),
            FoundryFile(
                "architecture/architecture.md",
                self._architecture_markdown(constraints, non_functional),
            ),
        ]

    def _dict_section(self, intake: dict[str, Any], name: str) -> dict[str, Any]:
        value = intake.get(name)
        return value if isinstance(value, dict) else {}

    def _project_contract(self, project: ProjectModel, intake: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema": "aeos.project.v1",
            "project_id": str(project.id),
            "name": intake["project"]["name"],
            "description": intake["project"]["description"],
            "repository_path": project.repository_path,
            "repository_url": project.repository_url,
            "manifest_hash": project.manifest_hash,
            "intake_hash": hash_json(intake),
            "source_of_truth": [
                "governance/authority-policy.yaml",
                "requirements/requirements.yaml",
                "architecture/",
                "planning/execution-plan.yaml",
            ],
        }

    def _readme(self, project: ProjectModel, intake: dict[str, Any]) -> str:
        return (
            f"# {intake['project']['name']}\n\n"
            f"{intake['project']['description']}\n\n"
            "## Operating Contract\n\n"
            "This repository was generated by AI Enterprise Project Foundry. "
            "Work starts from the intake, requirements, architecture, planning, "
            "and governance files.\n\n"
            f"- Project ID: `{project.id}`\n"
            f"- Project type: `{intake['project']['project_type']}`\n"
            f"- Manifest hash: `{project.manifest_hash}`\n"
        )

    def _requirements_markdown(self, requirements: list[Any]) -> str:
        lines = ["# Requirements", ""]
        for item in requirements:
            if not isinstance(item, dict):
                continue
            lines.append(f"## {item.get('id', 'REQ')}: {item.get('description', 'Requirement')}")
            lines.append("")
            lines.append(f"- Priority: {item.get('priority', 'medium')}")
            lines.append("- Acceptance criteria:")
            for criterion in item.get("acceptance_criteria", []):
                lines.append(f"  - {criterion}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _traceability_csv(self, requirements: list[Any]) -> str:
        rows = ["requirement_id,source,status,acceptance_criteria_count"]
        for item in requirements:
            if isinstance(item, dict):
                rows.append(
                    ",".join(
                        [
                            str(item.get("id", "")),
                            "project-intake",
                            "planned",
                            str(len(item.get("acceptance_criteria", []))),
                        ]
                    )
                )
        return "\n".join(rows) + "\n"

    def _architecture_markdown(self, constraints: Any, non_functional: Any) -> str:
        return (
            "# Architecture\n\n"
            "## Technical Constraints\n\n"
            f"```yaml\n{self._json_like(constraints)}\n```\n\n"
            "## Non-Functional Requirements\n\n"
            f"```yaml\n{self._json_like(non_functional)}\n```\n"
        )

    def _definition_of_done(self) -> str:
        return (
            "# Definition of Done\n\n"
            "- Requirements are traceable to implementation and tests.\n"
            "- Human approval is recorded for protected actions.\n"
            "- Verification commands pass and proof is attached.\n"
            "- Documentation and reusable blueprint notes are updated.\n"
            "- Release risk is reviewed before production deployment.\n"
        )

    def _markdown_list(self, title: str, values: Any) -> str:
        lines = [f"# {title}", ""]
        for value in values if isinstance(values, list) else []:
            lines.append(f"- {value}")
        if len(lines) == 2:
            lines.append("- To be confirmed")
        return "\n".join(lines) + "\n"

    def _risks(self, intake: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {
                "risk": "scope drift",
                "mitigation": "keep changes tied to approved requirements and acceptance criteria",
            },
            {
                "risk": "unapproved production action",
                "mitigation": "require human approval for protected actions",
            },
            {
                "risk": "integration uncertainty",
                "mitigation": "verify existing systems before architecture approval",
            },
        ]

    def _copy_template_file(
        self,
        source: Path,
        target: Path,
        relative_path: str,
        *,
        created_files: list[str],
        reused_files: list[str],
        overwrite: bool,
    ) -> None:
        if target.exists() and not overwrite:
            reused_files.append(relative_path)
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        created_files.append(relative_path)

    def _repo_root(self) -> Path:
        for candidate in Path(__file__).resolve().parents:
            if (candidate / "templates" / "project-foundry").is_dir():
                return candidate
        return Path.cwd()

    def _yaml(self, value: Any, indent: int = 0) -> str:
        prefix = " " * indent
        if isinstance(value, dict):
            lines: list[str] = []
            for key, item in value.items():
                if isinstance(item, dict | list):
                    lines.append(f"{prefix}{key}:")
                    lines.append(self._yaml(item, indent + 2).rstrip())
                else:
                    lines.append(f"{prefix}{key}: {self._scalar(item)}")
            return "\n".join(lines) + "\n"
        if isinstance(value, list):
            lines = []
            for item in value:
                if isinstance(item, dict):
                    lines.append(f"{prefix}-")
                    lines.append(self._yaml(item, indent + 2).rstrip())
                else:
                    lines.append(f"{prefix}- {self._scalar(item)}")
            return "\n".join(lines) + "\n"
        return f"{prefix}{self._scalar(value)}\n"

    def _scalar(self, value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        text = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{text}"'

    def _json_like(self, value: Any) -> str:
        return self._yaml(value).rstrip()
