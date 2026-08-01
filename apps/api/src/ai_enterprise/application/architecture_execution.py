import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.api.dependencies import Actor
from ai_enterprise.application.architecture_service import (
    ArchitectureGovernanceError,
    ArchitectureGovernanceService,
)
from ai_enterprise.config import Settings
from ai_enterprise.domain.architecture.enums import ArchitectureRunStatus
from ai_enterprise.domain.architecture.renderer import render_architecture_markdown
from ai_enterprise.domain.architecture.validation import ArchitectureValidationError
from ai_enterprise.infrastructure.architecture.contracts import ArchitectureExecutionContext
from ai_enterprise.infrastructure.architecture.evidence import SqlArchitectureAttemptEvidenceWriter
from ai_enterprise.infrastructure.architecture.executor import TrustedArchitectureExecutor
from ai_enterprise.infrastructure.architecture.models import (
    ArchitectureArtifactModel,
    ArchitectureExecutionAttemptModel,
    ArchitectureRunModel,
)
from ai_enterprise.infrastructure.architecture.parser import parse_architecture_json
from ai_enterprise.infrastructure.architecture.provider_factory import (
    ArchitectureProviderConfig,
    create_architecture_provider,
)
from ai_enterprise.infrastructure.database.models import ArtifactModel, ProjectModel
from ai_enterprise.infrastructure.database.session import SessionFactory


class ArchitectureWorkerEntry:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def handle(self, run_id: uuid.UUID) -> ArchitectureArtifactModel:
        run = await self._session.get(ArchitectureRunModel, run_id, with_for_update=True)
        if run is None:
            raise ArchitectureGovernanceError("Architecture run not found")
        existing = await self._session.scalar(
            select(ArchitectureArtifactModel).where(ArchitectureArtifactModel.run_id == run.id)
        )
        if existing is not None:
            return existing
        context = await self._context(run)
        recovered = await self._recover_success(context)
        if recovered is not None:
            return recovered
        run.status = ArchitectureRunStatus.RUNNING
        run.started_at = run.started_at or datetime.now(UTC)
        await self._session.commit()
        executor = TrustedArchitectureExecutor(
            provider=create_architecture_provider(
                ArchitectureProviderConfig(
                    provider=self._settings.architecture_provider,
                    model_name=self._settings.architecture_model_name,
                    base_url=self._settings.architecture_model_base_url,
                    temperature=self._settings.architecture_temperature,
                    timeout_seconds=self._settings.architecture_timeout_seconds,
                    max_tokens=self._settings.architecture_max_tokens,
                )
            ),
            evidence_writer=SqlArchitectureAttemptEvidenceWriter(SessionFactory),
            maximum_raw_output_bytes=self._settings.architecture_max_raw_output_bytes,
            maximum_repair_attempts=self._settings.architecture_max_repair_attempts,
        )
        try:
            result = await executor.execute(context)
        except ArchitectureValidationError:
            await self._fail(run, ArchitectureRunStatus.FAILED_VALIDATION)
            raise
        except Exception:
            await self._fail(run, ArchitectureRunStatus.FAILED)
            raise
        actor = Actor(
            subject="architecture-worker",
            actor_type="service",
            role="architecture_worker",
            capabilities=frozenset({"architecture.generate"}),
            trusted=True,
        )
        return await ArchitectureGovernanceService(self._session).complete_run(
            run.id,
            result.markdown,
            result.document.model_dump(mode="json"),
            actor,
        )

    async def _context(self, run: ArchitectureRunModel) -> ArchitectureExecutionContext:
        project = await self._session.get(ProjectModel, run.project_id)
        requirements = await self._session.get(ArtifactModel, run.requirements_artifact_id)
        if project is None or requirements is None:
            raise ArchitectureGovernanceError("Architecture input lineage is missing")
        if requirements.content_hash != run.requirements_checksum:
            raise ArchitectureGovernanceError("Architecture requirements checksum mismatch")
        ids = frozenset(re.findall(r"\bREQ-[A-Z0-9_-]+\b", requirements.content))
        if not ids:
            raise ArchitectureGovernanceError("Approved requirements contain no requirement IDs")
        attempt_offset = int(
            await self._session.scalar(
                select(
                    func.coalesce(func.max(ArchitectureExecutionAttemptModel.attempt_number), 0)
                ).where(ArchitectureExecutionAttemptModel.run_id == run.id)
            )
            or 0
        )
        return ArchitectureExecutionContext(
            run_id=run.id,
            project_id=project.id,
            project_name=project.name,
            project_description=project.description,
            project_manifest_checksum=project.manifest_hash,
            requirements_artifact_id=requirements.id,
            requirements_version=run.requirements_version,
            requirements_checksum=requirements.content_hash,
            requirements_markdown=requirements.content,
            approved_requirement_ids=ids,
            schema_version=run.schema_version,
            crew_version=run.crew_version,
            deadline_at=datetime.now(UTC)
            + timedelta(seconds=self._settings.architecture_timeout_seconds),
            attempt_number_offset=attempt_offset,
        )

    async def _recover_success(
        self, context: ArchitectureExecutionContext
    ) -> ArchitectureArtifactModel | None:
        attempt = await self._session.scalar(
            select(ArchitectureExecutionAttemptModel)
            .where(
                ArchitectureExecutionAttemptModel.run_id == context.run_id,
                ArchitectureExecutionAttemptModel.status == "succeeded",
            )
            .order_by(ArchitectureExecutionAttemptModel.attempt_number.desc())
            .limit(1)
        )
        if attempt is None or attempt.raw_output is None:
            return None
        document = parse_architecture_json(
            attempt.raw_output,
            maximum_bytes=self._settings.architecture_max_raw_output_bytes,
        )
        from ai_enterprise.domain.architecture.validation import validate_architecture

        validate_architecture(document, approved_requirement_ids=context.approved_requirement_ids)
        actor = Actor(
            subject="architecture-worker",
            actor_type="service",
            role="architecture_worker",
            capabilities=frozenset({"architecture.generate"}),
            trusted=True,
        )
        return await ArchitectureGovernanceService(self._session).complete_run(
            context.run_id,
            render_architecture_markdown(document),
            document.model_dump(mode="json"),
            actor,
        )

    async def _fail(self, run: ArchitectureRunModel, status: ArchitectureRunStatus) -> None:
        run.status = status
        run.finished_at = datetime.now(UTC)
        await self._session.commit()
