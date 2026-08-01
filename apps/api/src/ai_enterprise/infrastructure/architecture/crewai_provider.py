import asyncio

from crewai import LLM, Agent, Crew, Process, Task

from ai_enterprise.infrastructure.architecture.contracts import (
    ArchitectureExecutionContext,
    ModelInvocationResult,
)
from ai_enterprise.infrastructure.architecture.prompts import (
    SYSTEM_PROMPT,
    build_generation_prompt,
    build_repair_prompt,
    prompt_bundle_hash,
)


class CrewAIOllamaArchitectureProvider:
    name = "crewai-ollama"

    def __init__(
        self,
        *,
        model_name: str,
        base_url: str,
        temperature: float,
        timeout_seconds: int,
        max_tokens: int,
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

    async def generate(self, context: ArchitectureExecutionContext) -> ModelInvocationResult:
        prompt = build_generation_prompt(context)
        return await self._invoke(prompt)

    async def repair(
        self,
        context: ArchitectureExecutionContext,
        *,
        invalid_output: str,
        validation_report: tuple[dict[str, str], ...],
    ) -> ModelInvocationResult:
        return await self._invoke(build_repair_prompt(invalid_output, validation_report))

    async def _invoke(self, prompt: str) -> ModelInvocationResult:
        def run() -> str:
            agent = Agent(
                role="Trusted Architecture Generator",
                goal=(
                    "Produce only schema-valid architecture JSON grounded in approved requirements"
                ),
                backstory=SYSTEM_PROMPT,
                llm=self._llm,
                allow_delegation=False,
                tools=[],
                verbose=False,
            )
            task = Task(
                description=prompt,
                expected_output="Exactly one ArchitectureArtifactDocument 1.0 JSON object",
                agent=agent,
            )
            return str(
                Crew(
                    agents=[agent], tasks=[task], process=Process.sequential, verbose=False
                ).kickoff()
            )

        raw = await asyncio.to_thread(run)
        return ModelInvocationResult(
            raw_output=raw,
            model_name=self.model_name,
            prompt_bundle_hash=prompt_bundle_hash(SYSTEM_PROMPT, prompt),
            token_usage={},
        )
