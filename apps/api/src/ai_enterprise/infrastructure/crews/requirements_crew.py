from __future__ import annotations

import json
from dataclasses import dataclass

from crewai import LLM, Agent, Crew, Process, Task

from ai_enterprise.config import Settings


@dataclass(frozen=True)
class RequirementsCrewResult:
    markdown: str
    raw_output: str


class RequirementsCrewRunner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def run(
        self,
        *,
        project_name: str,
        project_description: str,
        manifest_hash: str,
        previous_artifact: str | None = None,
        revision_cycle_number: int | None = None,
        revision_feedback_summary: str | None = None,
        revision_feedback: list[dict[str, object]] | None = None,
        revision_feedback_hash: str | None = None,
    ) -> RequirementsCrewResult:
        if self._settings.requirements_crew_adapter.strip().lower() == "deterministic":
            findings = revision_feedback or []
            revision_section = ""
            if revision_cycle_number is not None:
                requested = "\n".join(
                    f"- {item.get('requested_change', 'Address reviewer finding')}"
                    for item in findings
                )
                revision_section = (
                    f"\n## Revision cycle {revision_cycle_number}\n"
                    f"Feedback hash: {revision_feedback_hash}\n"
                    f"Summary: {revision_feedback_summary}\n{requested}\n"
                )
            markdown = (
                f"# Requirements — {project_name}\n\n"
                f"Manifest: `{manifest_hash}`\n\n"
                f"## Objective\n{project_description}\n"
                f"{revision_section}\n"
                "## Functional requirements\n"
                "- FR-001: The platform shall preserve immutable workflow evidence.\n"
                "  - Acceptance: Every decision and generated artifact has a stable hash.\n"
            )
            return RequirementsCrewResult(markdown=markdown, raw_output=markdown)
        if self._settings.requirements_crew_adapter.strip().lower() != "crewai":
            raise RuntimeError("Unsupported requirements Crew adapter")
        llm = LLM(
            model=self._settings.requirements_llm_model,
            base_url=self._settings.requirements_llm_base_url,
            temperature=self._settings.requirements_llm_temperature,
            timeout=self._settings.requirements_llm_timeout_seconds,
            max_tokens=self._settings.requirements_llm_max_tokens,
        )

        analyst = Agent(
            role="Senior Requirements Engineer",
            goal=(
                "Convert a software product request into precise, bounded, "
                "traceable and testable requirements."
            ),
            backstory=(
                "You specialize in enterprise software requirements, "
                "workflow systems, security boundaries, auditability, "
                "human approval controls and acceptance criteria."
            ),
            llm=llm,
            allow_delegation=False,
            verbose=True,
        )

        task = Task(
            description=(
                "Analyze this project.\n\n"
                "Project name: {project_name}\n"
                "Manifest hash: {manifest_hash}\n\n"
                "Project description:\n"
                "{project_description}\n\n"
                "Previous requirements artifact (preserve valid content):\n"
                "{previous_artifact}\n\n"
                "Immutable revision cycle: {revision_cycle_number}\n"
                "Immutable feedback summary: {revision_feedback_summary}\n"
                "Immutable actionable findings: {revision_feedback}\n"
                "Feedback integrity hash: {revision_feedback_hash}\n\n"
                "For revisions, address every finding without overwriting history.\n\n"
                "Produce a rigorous requirements specification containing:\n"
                "1. Executive summary\n"
                "2. Problem statement\n"
                "3. Goals\n"
                "4. Non-goals\n"
                "5. Actors and responsibilities\n"
                "6. Functional requirements with stable IDs such as FR-001\n"
                "7. Non-functional requirements with IDs such as NFR-001\n"
                "8. Security and isolation requirements\n"
                "9. Auditability requirements\n"
                "10. Data requirements\n"
                "11. Failure and recovery requirements\n"
                "12. Assumptions\n"
                "13. Constraints\n"
                "14. Risks\n"
                "15. Acceptance criteria\n"
                "16. Open questions\n\n"
                "Do not propose implementation details unless they are "
                "required constraints. Mark uncertain statements explicitly."
            ),
            expected_output=(
                "A complete Markdown requirements document containing "
                "stable requirement identifiers and verifiable acceptance criteria."
            ),
            agent=analyst,
        )

        crew = Crew(
            agents=[analyst],
            tasks=[task],
            process=Process.sequential,
            verbose=True,
        )

        output = crew.kickoff(
            inputs={
                "project_name": project_name,
                "project_description": project_description,
                "manifest_hash": manifest_hash,
                "previous_artifact": previous_artifact or "none (initial version)",
                "revision_cycle_number": revision_cycle_number or "none",
                "revision_feedback_summary": revision_feedback_summary or "none",
                "revision_feedback": json.dumps(revision_feedback or [], sort_keys=True),
                "revision_feedback_hash": revision_feedback_hash or "none",
            }
        )

        markdown = str(output).strip()

        if not markdown:
            raise RuntimeError("Requirements Crew returned an empty result")

        return RequirementsCrewResult(
            markdown=markdown,
            raw_output=str(output),
        )
