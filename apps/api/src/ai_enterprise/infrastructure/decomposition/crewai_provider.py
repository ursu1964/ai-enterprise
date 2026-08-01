import asyncio
from typing import cast

from crewai import LLM, Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent

from ai_enterprise.domain.decomposition.schema import CandidateDecomposition

from .contracts import DecompositionCrewContext
from .prompts import SYSTEM_PROMPT, build_decomposition_prompt


class CrewAIDecompositionProvider:
    name = "crewai-ollama"

    def __init__(
        self,
        *,
        model_name: str,
        base_url: str,
        temperature: float = 0.0,
        timeout_seconds: int = 900,
        max_tokens: int = 16384,
    ) -> None:
        self.model_name = model_name
        self._llm = LLM(
            model=model_name,
            base_url=base_url,
            api_key="ollama",
            temperature=temperature,
            timeout=timeout_seconds,
            max_tokens=max_tokens,
        )

    async def decompose(self, context: DecompositionCrewContext) -> CandidateDecomposition:
        prompt = build_decomposition_prompt(context)

        def invoke() -> str:
            roles = (
                ("Repository Structure Analyst", "Identify repository-aware boundaries"),
                ("Decomposition Architect", "Propose cohesive implementation outcomes"),
                ("Dependency Analyst", "Explain prerequisite relationships"),
                ("Verification Planner", "Define deterministic verification"),
            )
            agents = [
                Agent(
                    role=role,
                    goal=goal,
                    backstory=SYSTEM_PROMPT,
                    llm=self._llm,
                    allow_delegation=False,
                    tools=[],
                    verbose=False,
                )
                for role, goal in roles
            ]
            tasks = [
                Task(
                    description=prompt,
                    expected_output="Exactly one CandidateDecomposition JSON object",
                    agent=agents[-1],
                )
            ]
            return str(
                Crew(
                    agents=cast(list[BaseAgent], agents),
                    tasks=tasks,
                    process=Process.sequential,
                ).kickoff()
            )

        raw = await asyncio.to_thread(invoke)
        return CandidateDecomposition.model_validate_json(raw)
