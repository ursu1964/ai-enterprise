from __future__ import annotations

import asyncio
import json

from crewai import Agent, Crew, Process, Task

from ai_enterprise.domain.requirements_revision.models import RequirementsArtifactDocument

from .provider import CrewLLMProvider, RequirementsProviderError


class CrewAIRequirementsExecutor:
    """Optional CrewAI execution; it receives only the already-bounded prompt."""

    def __init__(self, provider: CrewLLMProvider) -> None:
        self._provider = provider

    async def __call__(self, prompt: str) -> str:
        try:
            return await asyncio.to_thread(self._execute_sync, prompt)
        except (TimeoutError, ConnectionError) as exc:
            raise RequirementsProviderError("Requirements model is unavailable") from exc

    def _execute_sync(self, prompt: str) -> str:
        llm = self._provider.create_llm()
        analyst = Agent(
            role="Senior Business Analyst",
            goal="Identify bounded, testable business requirements and revision impacts",
            backstory="Enterprise requirements specialist",
            llm=llm,
            verbose=False,
            allow_delegation=False,
        )
        engineer = Agent(
            role="Senior Requirements Engineer",
            goal="Produce atomic requirements with stable identifiers and acceptance criteria",
            backstory="Structured requirements author",
            llm=llm,
            verbose=False,
            allow_delegation=False,
        )
        reviewer = Agent(
            role="Independent Requirements Reviewer",
            goal="Return exactly one corrected schema-valid JSON artifact",
            backstory="Independent quality reviewer; human approval remains external",
            llm=llm,
            verbose=False,
            allow_delegation=False,
        )
        analysis = Task(
            description=f"Analyze the following bounded requirements input:\n{prompt}",
            expected_output="A bounded analysis addressing every revision finding",
            agent=analyst,
        )
        draft = Task(
            description="Draft complete atomic requirements from the analysis",
            expected_output="A draft requirements artifact",
            agent=engineer,
            context=[analysis],
        )
        final = Task(
            description=(
                "Return only one JSON object matching this schema, without fences or commentary:\n"
                + json.dumps(
                    RequirementsArtifactDocument.model_json_schema(), separators=(",", ":")
                )
            ),
            expected_output="One schema-valid JSON object",
            agent=reviewer,
            context=[analysis, draft],
        )
        result = Crew(
            agents=[analyst, engineer, reviewer],
            tasks=[analysis, draft, final],
            process=Process.sequential,
            verbose=False,
            memory=False,
            cache=False,
        ).kickoff()
        raw = getattr(result, "raw", None)
        value = raw if isinstance(raw, str) else str(result)
        if not value.strip():
            raise RequirementsProviderError("CrewAI returned an empty requirements result")
        return value
