import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.domain.enums import JobType
from ai_enterprise.domain.execution.enums import ExecutionStatus
from ai_enterprise.domain.execution.lineage import RevisionLineagePolicy
from ai_enterprise.domain.integration.enums import PatchStatus
from ai_enterprise.domain.integration.exceptions import RevisionLineageError
from ai_enterprise.infrastructure.database.models import (
    AuditEventModel,
    ExecutionRunModel,
    ExecutionRunRevisionFindingModel,
    PatchReviewFindingModel,
    PatchReviewRunModel,
)
from ai_enterprise.infrastructure.jobs.repository import JobRepository


class RevisionAttemptService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, *, review_id: uuid.UUID, idempotency_key: str, actor_id: str
    ) -> ExecutionRunModel:
        review = await self._session.scalar(
            select(PatchReviewRunModel).where(PatchReviewRunModel.id == review_id).with_for_update()
        )
        if review is None or review.status != "changes_requested":
            raise RevisionLineageError("A changes-requested review is required")
        existing = await self._session.scalar(
            select(ExecutionRunModel).where(
                ExecutionRunModel.idempotency_key == idempotency_key,
                ExecutionRunModel.project_id == review.project_id,
            )
        )
        if existing is not None:
            return existing
        parent = await self._session.get(ExecutionRunModel, review.execution_run_id)
        if parent is None or parent.work_package_id != review.work_package_id:
            raise RevisionLineageError("Review does not belong to its parent attempt")
        findings = (
            (
                await self._session.execute(
                    select(PatchReviewFindingModel).where(
                        PatchReviewFindingModel.patch_review_run_id == review.id,
                        PatchReviewFindingModel.status == "open",
                    )
                )
            )
            .scalars()
            .all()
        )
        if not findings:
            raise RevisionLineageError("Revision review has no open findings")
        lineage = RevisionLineagePolicy().derive(
            parent_id=parent.id,
            parent_root_id=parent.root_execution_run_id,
            parent_depth=parent.lineage_depth,
            source_review_id=review.id,
        )
        run = ExecutionRunModel(
            id=uuid.uuid4(),
            project_id=parent.project_id,
            work_package_id=parent.work_package_id,
            approval_id=parent.approval_id,
            status=ExecutionStatus.PENDING,
            base_commit=parent.base_commit,
            base_tree_sha=parent.base_tree_sha,
            patch_status=PatchStatus.GENERATED,
            parent_execution_run_id=lineage.parent_attempt_id,
            root_execution_run_id=lineage.root_attempt_id,
            revision_source_review_run_id=lineage.source_review_id,
            lineage_depth=lineage.lineage_depth,
            container_image=parent.container_image,
            timeout_seconds=parent.timeout_seconds,
            cpu_limit=parent.cpu_limit,
            memory_limit_bytes=parent.memory_limit_bytes,
            pids_limit=parent.pids_limit,
            network_disabled=parent.network_disabled,
            runtime_policy=parent.runtime_policy | {"revision_review_id": str(review.id)},
            idempotency_key=idempotency_key,
        )
        self._session.add(run)
        await self._session.flush()
        for finding in findings:
            self._session.add(
                ExecutionRunRevisionFindingModel(
                    execution_run_id=run.id, review_finding_id=finding.id
                )
            )
        parent.patch_status = PatchStatus.SUPERSEDED
        await JobRepository(self._session).enqueue(
            project_id=run.project_id,
            run_id=None,
            job_type=JobType.EXECUTE_WORK_PACKAGE,
            payload={
                "project_id": str(run.project_id),
                "execution_id": str(run.id),
                "work_package_id": str(run.work_package_id),
            },
            priority=100,
            max_attempts=1,
        )
        self._session.add(
            AuditEventModel(
                id=uuid.uuid4(),
                project_id=run.project_id,
                event_type="execution.revision_attempt_created",
                actor_type="human",
                actor_id=actor_id,
                payload={
                    "execution_run_id": str(run.id),
                    "parent_execution_run_id": str(parent.id),
                    "root_execution_run_id": str(lineage.root_attempt_id),
                    "review_id": str(review.id),
                    "finding_ids": [str(item.id) for item in findings],
                },
            )
        )
        await self._session.commit()
        await self._session.refresh(run)
        return run
