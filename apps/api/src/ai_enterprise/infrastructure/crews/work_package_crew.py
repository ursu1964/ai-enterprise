from __future__ import annotations

import json
from dataclasses import dataclass

from crewai import LLM, Agent, Crew, Process, Task

from ai_enterprise.config import Settings


@dataclass(frozen=True)
class WorkPackageCrewResult:
    raw_json: str


class WorkPackageCrewRunner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def run(
        self,
        *,
        project_id: str,
        project_name: str,
        project_description: str,
        base_commit_sha: str,
        requirements_artifact_id: str,
        requirements_hash: str,
        requirements_markdown: str,
        architecture_artifact_id: str,
        architecture_hash: str,
        architecture_markdown: str,
        tracked_files: list[str],
    ) -> WorkPackageCrewResult:
        llm = LLM(
            model=self._settings.ollama_model,
            base_url=self._settings.ollama_base_url,
            temperature=0.0,
            timeout=900,
            additional_params={
                "num_ctx": 16384,
                "num_predict": 8192,
            },
        )

        planner = Agent(
            role="Senior Software Work Package Planner",
            goal=(
                "Select one small, coherent and independently testable "
                "implementation increment from the approved architecture."
            ),
            backstory=(
                "You divide enterprise software architecture into bounded "
                "changes suitable for isolated execution and rigorous review."
            ),
            llm=llm,
            allow_delegation=False,
            verbose=True,
        )

        boundary_reviewer = Agent(
            role="Work Package Boundary Reviewer",
            goal=(
                "Prevent broad, ambiguous, unsafe or non-verifiable "
                "implementation packages."
            ),
            backstory=(
                "You reject work that lacks precise file boundaries, "
                "test commands, resource limits or traceability."
            ),
            llm=llm,
            allow_delegation=False,
            verbose=True,
        )

        planning_task = Task(
            description=(
                "Create exactly one bounded work package.\n\n"
                "Project ID: {project_id}\n"
                "Project name: {project_name}\n"
                "Project description: {project_description}\n"
                "Base commit: {base_commit_sha}\n\n"
                "Requirements artifact ID: "
                "{requirements_artifact_id}\n"
                "Requirements hash: {requirements_hash}\n\n"
                "Architecture artifact ID: "
                "{architecture_artifact_id}\n"
                "Architecture hash: {architecture_hash}\n\n"
                "Tracked repository files:\n"
                "{tracked_files}\n\n"
                "Approved requirements:\n"
                "{requirements_markdown}\n\n"
                "Approved architecture:\n"
                "{architecture_markdown}\n\n"
                "Choose the smallest valuable implementation increment. "
                "Do not plan the entire platform. The package should normally "
                "modify no more than 12 files.\n\n"
                "Return only valid JSON matching this shape:\n"
                "{contract_schema}\n\n"
                "Rules:\n"
                "- Use only tracked paths or explicit new paths under an "
                "approved directory.\n"
                "- Every NEW file path in file_scope.allowed_files MUST have "
                "its parent directory listed in file_scope.allowed_directories. "
                "For example, a new file src/main.py requires "
                "allowed_directories = [\"src\"]. Never leave "
                "allowed_directories empty when any new file is proposed.\n"
                "- Never allow .git, .env, credentials, host configuration, "
                "Docker socket access or system directories.\n"
                "- Default network policy to none.\n"
                "- Use command arrays, not shell strings.\n"
                "- Include explicit test commands.\n"
                "- Include stable CHG-### and AC-### identifiers.\n"
                "- Every required change must reference approved requirement "
                "IDs.\n"
                "- Preserve the supplied artifact IDs and hashes exactly."
            ),
            expected_output=(
                "One valid JSON work-package contract and no Markdown."
            ),
            agent=planner,
        )

        review_task = Task(
            description=(
                "Review the proposed work-package contract. If any defect "
                "exists, FIX it inside the JSON contract.\n\n"
                "The contract must match this shape:\n"
                "{contract_schema}\n\n"
                "Check and correct:\n"
                "- excessive scope;\n"
                "- missing file boundaries (every NEW file's parent "
                "directory must be declared in file_scope.allowed_directories);\n"
                "- shell command strings;\n"
                "- privileged operations;\n"
                "- unnecessary network access;\n"
                "- missing tests;\n"
                "- vague acceptance criteria;\n"
                "- source artifact IDs or hashes that changed;\n"
                "- modifications to secrets, .git or host configuration.\n\n"
                "You must ALWAYS return the complete corrected contract as a "
                "single JSON object. Never return a rejection object, a "
                "\"status\" field, lists, Markdown, or any other shape."
            ),
            expected_output=(
                "The complete corrected JSON work-package contract only."
            ),
            agent=boundary_reviewer,
            context=[planning_task],
        )

        contract_schema = {
            "schema_version": "1.0",
            "project_id": project_id,
            "title": "Short bounded title",
            "objective": "Precise implementation objective",
            "base_commit_sha": base_commit_sha,
            "source_requirements_artifact_id": requirements_artifact_id,
            "source_requirements_hash": requirements_hash,
            "source_architecture_artifact_id": architecture_artifact_id,
            "source_architecture_hash": architecture_hash,
            "required_changes": [
                {
                    "id": "CHG-001",
                    "description": "Required change",
                    "related_requirements": ["FR-001"],
                    "target_paths": ["relative/path.py"],
                }
            ],
            "file_scope": {
                "allowed_files": ["src/main.py"],
                "allowed_directories": ["src"],
                "forbidden_files": [".env"],
                "forbidden_directories": [".git"],
                "maximum_changed_files": 12,
                "maximum_added_lines": 1000,
                "maximum_deleted_lines": 500,
            },
            "command_policy": {
                "setup_commands": [],
                "implementation_commands": [],
                "test_commands": [
                    ["pytest", "-q", "tests"]
                ],
                "forbidden_executables": [
                    "sudo",
                    "su",
                    "ssh",
                    "scp",
                    "mount",
                    "umount",
                    "systemctl",
                    "service",
                    "reboot",
                    "shutdown",
                    "docker",
                    "podman",
                    "kubectl",
                ],
            },
            "network": {
                "policy": "none",
                "allowed_hosts": [],
            },
            "resources": {
                "cpu_count": 2.0,
                "memory_mb": 4096,
                "disk_mb": 8192,
                "process_limit": 256,
                "execution_timeout_seconds": 1800,
            },
            "acceptance_criteria": [
                {
                    "id": "AC-001",
                    "description": "Observable outcome",
                    "verification": "Exact test or inspection",
                }
            ],
            "expected_artifacts": [
                "implementation.patch",
                "test-report.json",
                "execution-log.jsonl",
                "changed-files.json",
            ],
            "forbidden_actions": [
                "Modify files outside the approved checkout",
                "Access the Docker socket",
                "Use privileged container execution",
                "Mount host system directories",
                "Change host services",
                "Read host credentials",
                "Push commits or tags",
                "Contact unapproved network destinations",
            ],
        }

        crew = Crew(
            agents=[planner, boundary_reviewer],
            tasks=[planning_task, review_task],
            process=Process.sequential,
            verbose=True,
        )

        output = crew.kickoff(
            inputs={
                "project_id": project_id,
                "project_name": project_name,
                "project_description": project_description,
                "base_commit_sha": base_commit_sha,
                "requirements_artifact_id": requirements_artifact_id,
                "requirements_hash": requirements_hash,
                "requirements_markdown": requirements_markdown,
                "architecture_artifact_id": architecture_artifact_id,
                "architecture_hash": architecture_hash,
                "architecture_markdown": architecture_markdown,
                "tracked_files": "\n".join(tracked_files),
                "contract_schema": json.dumps(
                    contract_schema,
                    indent=2,
                ),
            }
        )

        raw_json = str(output).strip()

        if not raw_json:
            raise RuntimeError(
                "Work Package Crew returned an empty result"
            )

        return WorkPackageCrewResult(raw_json=raw_json)
