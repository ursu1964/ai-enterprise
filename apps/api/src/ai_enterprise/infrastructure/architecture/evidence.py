import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_enterprise.infrastructure.architecture.contracts import (
    ArchitectureAttemptEvidenceWriter,
    AttemptEvidence,
)
from ai_enterprise.infrastructure.architecture.models import ArchitectureExecutionAttemptModel


class SqlArchitectureAttemptEvidenceWriter(ArchitectureAttemptEvidenceWriter):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def record(self, evidence: AttemptEvidence) -> None:
        async with self._session_factory() as session, session.begin():
            session.add(
                ArchitectureExecutionAttemptModel(
                    id=uuid.uuid4(),
                    run_id=evidence.run_id,
                    attempt_number=evidence.attempt_number,
                    idempotency_key=f"{evidence.run_id}:{evidence.attempt_number}",
                    operation=evidence.operation,
                    status=evidence.status,
                    provider_name=evidence.provider_name,
                    model_name=evidence.model_name,
                    prompt_bundle_hash=evidence.prompt_bundle_hash,
                    raw_output=evidence.raw_output,
                    raw_output_hash=evidence.raw_output_hash,
                    validation_report=list(evidence.validation_report),
                    token_usage=evidence.token_usage,
                    failure_code=evidence.failure_code,
                    started_at=evidence.started_at,
                    completed_at=evidence.completed_at,
                )
            )
