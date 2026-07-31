from __future__ import annotations

from dataclasses import dataclass

from crewai import LLM, Agent, Crew, Process, Task

from ai_enterprise.config import Settings


@dataclass(frozen=True)
class ArchitectureCrewResult:
    markdown: str
    raw_output: str


class ArchitectureCrewRunner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def run(
        self,
        *,
        project_name: str,
        project_description: str,
        project_manifest_hash: str,
        requirements_markdown: str,
        requirements_artifact_hash: str,
    ) -> ArchitectureCrewResult:
        llm = LLM(
            model=self._settings.ollama_model,
            base_url=self._settings.ollama_base_url,
            temperature=0.1,
            timeout=900,
        )

        architect = Agent(
            role="Principal Software Architect",
            goal=(
                "Transform approved requirements into a bounded, secure, "
                "modular and auditable software architecture."
            ),
            backstory=(
                "You design enterprise platforms with explicit trust "
                "boundaries, reproducible execution, human approval gates, "
                "immutable artifacts and controlled infrastructure access."
            ),
            llm=llm,
            allow_delegation=False,
            verbose=True,
        )

        reviewer = Agent(
            role="Independent Architecture Reviewer",
            goal=(
                "Identify omissions, unsafe assumptions, uncontrolled host "
                "access, weak boundaries and requirements that are not "
                "covered by the proposed architecture."
            ),
            backstory=(
                "You perform adversarial architecture reviews for secure "
                "software delivery platforms."
            ),
            llm=llm,
            allow_delegation=False,
            verbose=True,
        )

        design_task = Task(
            description=(
                "Create an architecture specification for this project.\n\n"
                "Project: {project_name}\n"
                "Description: {project_description}\n"
                "Manifest hash: {project_manifest_hash}\n"
                "Approved requirements hash: {requirements_artifact_hash}\n\n"
                "Approved requirements:\n"
                "{requirements_markdown}\n\n"
                "The architecture must contain:\n"
                "1. Architecture objectives\n"
                "2. Scope and non-scope\n"
                "3. System context\n"
                "4. Trust boundaries\n"
                "5. Components and responsibilities\n"
                "6. Dependency direction\n"
                "7. Domain aggregates\n"
                "8. Commands and domain events\n"
                "9. Persistent data model\n"
                "10. API boundaries\n"
                "11. Worker and job execution model\n"
                "12. Agent and crew execution model\n"
                "13. Artifact and provenance model\n"
                "14. Approval gates\n"
                "15. Disposable execution environment\n"
                "16. Host protection controls\n"
                "17. Failure recovery and idempotency\n"
                "18. Observability and audit trail\n"
                "19. Security model\n"
                "20. Deployment topology\n"
                "21. Architecture decisions\n"
                "22. Requirement traceability matrix\n"
                "23. Risks and unresolved questions\n\n"
                "Every major design decision must reference the requirement "
                "IDs it satisfies. Do not silently invent requirements."
            ),
            expected_output=(
                "A complete Markdown architecture specification with "
                "component boundaries, trust boundaries, data flows, "
                "architecture decisions and requirements traceability."
            ),
            agent=architect,
        )

        review_task = Task(
            description=(
                "Review the proposed architecture independently.\n\n"
                "Verify:\n"
                "- coverage of approved requirements;\n"
                "- protection of the Ubuntu host;\n"
                "- strict human approval gates;\n"
                "- immutable artifact provenance;\n"
                "- retry and idempotency behavior;\n"
                "- database transaction boundaries;\n"
                "- container isolation;\n"
                "- absence of uncontrolled code execution.\n\n"
                "Return a corrected final architecture document. Include a "
                "review findings section describing material changes made."
            ),
            expected_output=(
                "A reviewed and corrected Markdown architecture document "
                "suitable for human approval."
            ),
            agent=reviewer,
            context=[design_task],
        )

        crew = Crew(
            agents=[architect, reviewer],
            tasks=[design_task, review_task],
            process=Process.sequential,
            verbose=True,
        )

        output = crew.kickoff(
            inputs={
                "project_name": project_name,
                "project_description": project_description,
                "project_manifest_hash": project_manifest_hash,
                "requirements_markdown": requirements_markdown,
                "requirements_artifact_hash": requirements_artifact_hash,
            }
        )

        markdown = str(output).strip()

        if not markdown:
            raise RuntimeError("Architecture Crew returned an empty result")

        return ArchitectureCrewResult(
            markdown=markdown,
            raw_output=str(output),
        )
