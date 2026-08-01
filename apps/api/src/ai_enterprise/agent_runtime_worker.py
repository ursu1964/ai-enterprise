import uuid
from typing import Protocol


class RuntimeSessionProcessor(Protocol):
    async def execute(self, session_id: uuid.UUID) -> None: ...


class AgentRuntimeWorker:
    """Durable-worker entry point; execution remains internal, never an API endpoint."""

    def __init__(self, processor: RuntimeSessionProcessor) -> None:
        self.processor = processor

    async def process(self, payload: dict[str, object]) -> None:
        raw_session_id = payload.get("runtime_session_id")
        if not isinstance(raw_session_id, str):
            raise ValueError("runtime_session_id is required")
        await self.processor.execute(uuid.UUID(raw_session_id))
