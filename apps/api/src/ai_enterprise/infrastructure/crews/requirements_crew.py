from __future__ import annotations

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
    ) -> RequirementsCrewResult:
        llm = LLM(
            model=self._settings.ollama_model,
            base_url=self._settings.ollama_base_url,
            temperature=0.1,
            timeout=600,
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
            }
        )

        markdown = str(output).strip()

        if not markdown:
            raise RuntimeError("Requirements Crew returned an empty result")

        return RequirementsCrewResult(
            markdown=markdown,
            raw_output=str(output),
        )
