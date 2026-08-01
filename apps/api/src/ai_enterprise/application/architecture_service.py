import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.api.architecture_schemas import FindingRequest
from ai_enterprise.api.dependencies import Actor
from ai_enterprise.application.architecture_operations.observability import (
    ArchitectureMetric,
    record_metric,
)
from ai_enterprise.domain.architecture.enums import (
    ArchitectureArtifactStatus,
    ArchitectureReviewDecision,
    ArchitectureReviewStatus,
    ArchitectureRevisionStatus,
    ArchitectureRunStatus,
)
from ai_enterprise.domain.enums import JobType
from ai_enterprise.domain.hashing import hash_json
from ai_enterprise.infrastructure.architecture.models import (
    ArchitectureApprovalModel,
    ArchitectureArtifactModel,
    ArchitectureReviewFindingModel,
    ArchitectureReviewModel,
    ArchitectureRevisionRequestModel,
    ArchitectureRunModel,
)
from ai_enterprise.infrastructure.database.models import (
    ApprovalModel,
    ArtifactModel,
    AuditEventModel,
)
from ai_enterprise.infrastructure.jobs.repository import JobRepository


class ArchitectureGovernanceError(RuntimeError):
    status_code = 409


class ArchitectureAuthorizationError(ArchitectureGovernanceError):
    status_code = 403


class ArchitectureNotFoundError(ArchitectureGovernanceError):
    status_code = 404


def _require(actor: Actor, role: str, capability: str, *, human: bool = True) -> None:
    if actor.role != role or (actor.capabilities and capability not in actor.capabilities):
        raise ArchitectureAuthorizationError(f"Missing capability: {capability}")
    if human and actor.actor_type != "human":
        raise ArchitectureAuthorizationError("A human principal is required")


class ArchitectureGovernanceService:
    REVIEW_POLICY = "architecture-review-policy-v1"
    APPROVAL_POLICY = "architecture-approval-policy-v1"

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_run(
        self, project_id: uuid.UUID, requirements_id: uuid.UUID
    ) -> ArchitectureRunModel:
        artifact = await self.session.get(ArtifactModel, requirements_id)
        if (
            artifact is None
            or artifact.project_id != project_id
            or artifact.artifact_type != "requirements_specification"
        ):
            raise ArchitectureGovernanceError("Approved requirements artifact not found")
        approval = await self.session.scalar(
            select(ApprovalModel).where(
                ApprovalModel.artifact_id == artifact.id, ApprovalModel.decision == "approved"
            )
        )
        if approval is None:
            raise ArchitectureGovernanceError("Architecture requires approved requirements")
        active = await self.session.scalar(
            select(ArchitectureRunModel).where(
                ArchitectureRunModel.project_id == project_id,
                ArchitectureRunModel.status.in_(
                    (ArchitectureRunStatus.READY, ArchitectureRunStatus.RUNNING)
                ),
            )
        )
        if active is not None:
            raise ArchitectureGovernanceError("Project already has an active architecture run")
        version = (
            int(
                await self.session.scalar(
                    select(func.count())
                    .select_from(ArchitectureRunModel)
                    .where(ArchitectureRunModel.project_id == project_id)
                )
                or 0
            )
            + 1
        )
        run = ArchitectureRunModel(
            id=uuid.uuid4(),
            project_id=project_id,
            requirements_artifact_id=artifact.id,
            requirements_checksum=artifact.content_hash,
            requirements_version=version,
            status=ArchitectureRunStatus.READY,
            crew_version="architecture-crew-v1",
            schema_version="1.0",
            model_name="server-controlled",
            temperature=0,
            prompt_bundle_hash=hash_json({"version": "architecture-v1"}),
            system_prompt_hash=hash_json({"system": "architecture-only"}),
            execution_manifest={"network": False, "repository_write": False},
        )
        self.session.add(run)
        await JobRepository(self.session).enqueue(
            project_id=project_id,
            run_id=None,
            job_type=JobType.RUN_ARCHITECTURE_CREW,
            payload={"run_id": str(run.id), "governed_architecture_run": True},
            max_attempts=2,
        )
        record_metric(ArchitectureMetric.RUNS)
        self._audit(project_id, "architecture.run.created", "system", {"run_id": str(run.id)})
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def complete_run(
        self, run_id: uuid.UUID, markdown: str, structured: dict[str, object], actor: Actor
    ) -> ArchitectureArtifactModel:
        _require(actor, "architecture_worker", "architecture.generate", human=False)
        run = await self._run(run_id, lock=True)
        if run.status not in {ArchitectureRunStatus.READY, ArchitectureRunStatus.RUNNING}:
            raise ArchitectureGovernanceError("Run is not completable")
        existing = await self.session.scalar(
            select(ArchitectureArtifactModel).where(ArchitectureArtifactModel.run_id == run.id)
        )
        checksum = hash_json(
            {"markdown": markdown, "structured": structured, "schema_version": run.schema_version}
        )
        if existing is not None:
            if existing.checksum != checksum:
                raise ArchitectureGovernanceError("Run already produced another immutable artifact")
            return existing
        version = (
            int(
                await self.session.scalar(
                    select(func.count())
                    .select_from(ArchitectureArtifactModel)
                    .where(ArchitectureArtifactModel.project_id == run.project_id)
                )
                or 0
            )
            + 1
        )
        artifact = ArchitectureArtifactModel(
            id=uuid.uuid4(),
            run_id=run.id,
            project_id=run.project_id,
            requirements_artifact_id=run.requirements_artifact_id,
            parent_artifact_id=run.parent_architecture_artifact_id,
            version=version,
            status=ArchitectureArtifactStatus.DRAFT,
            markdown_content=markdown,
            structured_content=structured,
            checksum=checksum,
            schema_version=run.schema_version,
        )
        run.status = ArchitectureRunStatus.COMPLETED
        run.finished_at = datetime.now(UTC)
        run.completed_by = actor.subject
        if run.revision_request_id is not None:
            revision = await self.session.get(
                ArchitectureRevisionRequestModel, run.revision_request_id
            )
            if revision is None or revision.revision_run_id != run.id:
                raise ArchitectureGovernanceError("Revision lineage is corrupt")
            revision.status = ArchitectureRevisionStatus.COMPLETED
            revision.completed_at = datetime.now(UTC)
        self.session.add(artifact)
        record_metric(ArchitectureMetric.RUNS_COMPLETED)
        record_metric(ArchitectureMetric.ARTIFACTS_CREATED)
        self._audit(
            run.project_id,
            "architecture.completed",
            actor.subject,
            {"artifact_id": str(artifact.id), "checksum": checksum},
        )
        await self.session.commit()
        await self.session.refresh(artifact)
        return artifact

    async def open_review(
        self, artifact_id: uuid.UUID, reviewer_id: str, actor: Actor
    ) -> ArchitectureReviewModel:
        _require(actor, "architecture_review_assigner", "architecture.review.assign")
        artifact = await self._artifact(artifact_id, lock=True)
        run = await self._run(artifact.run_id)
        if reviewer_id == run.completed_by:
            raise ArchitectureGovernanceError("Generator cannot review its architecture")
        count = int(
            await self.session.scalar(
                select(func.count())
                .select_from(ArchitectureReviewModel)
                .where(ArchitectureReviewModel.architecture_artifact_id == artifact.id)
            )
            or 0
        )
        review = ArchitectureReviewModel(
            id=uuid.uuid4(),
            architecture_artifact_id=artifact.id,
            review_round=count + 1,
            status=ArchitectureReviewStatus.OPEN,
            reviewer_id=reviewer_id,
            reviewer_role="architecture_reviewer",
            reviewer_subject_type="human",
            reviewed_checksum=artifact.checksum,
            policy_version=self.REVIEW_POLICY,
        )
        artifact.status = ArchitectureArtifactStatus.UNDER_REVIEW
        self.session.add(review)
        record_metric(ArchitectureMetric.REVIEWS_OPEN)
        self._audit(
            artifact.project_id,
            "architecture.review.opened",
            actor.subject,
            {"review_id": str(review.id)},
        )
        await self.session.commit()
        await self.session.refresh(review)
        return review

    async def complete_review(
        self,
        review_id: uuid.UUID,
        decision: ArchitectureReviewDecision,
        comments: str,
        findings: list[FindingRequest],
        actor: Actor,
    ) -> ArchitectureReviewModel:
        _require(actor, "architecture_reviewer", "architecture.review.complete")
        review = await self.session.get(ArchitectureReviewModel, review_id, with_for_update=True)
        if review is None or review.status != ArchitectureReviewStatus.OPEN:
            raise ArchitectureGovernanceError("Review is not open")
        if actor.subject != review.reviewer_id:
            raise ArchitectureGovernanceError("Only assigned reviewer may complete review")
        artifact = await self._artifact(review.architecture_artifact_id, lock=True)
        if artifact.checksum != review.reviewed_checksum:
            raise ArchitectureGovernanceError("Reviewed checksum changed")
        if decision is ArchitectureReviewDecision.RECOMMEND_APPROVAL and any(
            item.blocking for item in findings
        ):
            raise ArchitectureGovernanceError("Blocking findings prevent approval recommendation")
        if decision is ArchitectureReviewDecision.REQUEST_CHANGES and not findings:
            raise ArchitectureGovernanceError(
                "Changes-requested review requires at least one structured finding"
            )
        for item in findings:
            if item.blocking and not item.required_change:
                raise ArchitectureGovernanceError("Blocking finding requires a change")
            self.session.add(
                ArchitectureReviewFindingModel(
                    id=uuid.uuid4(), review_id=review.id, **item.model_dump()
                )
            )
        review.status = ArchitectureReviewStatus.COMPLETED
        review.decision = decision
        review.comments = comments
        review.completed_at = datetime.now(UTC)
        artifact.status = {
            ArchitectureReviewDecision.REQUEST_CHANGES: (
                ArchitectureArtifactStatus.CHANGES_REQUESTED
            ),
            ArchitectureReviewDecision.REJECT: ArchitectureArtifactStatus.REJECTED,
        }.get(decision, ArchitectureArtifactStatus.UNDER_REVIEW)
        record_metric(
            ArchitectureMetric.CHANGES_REQUESTED
            if decision is ArchitectureReviewDecision.REQUEST_CHANGES
            else ArchitectureMetric.REVIEWS_COMPLETED
        )
        self._audit(
            artifact.project_id,
            "architecture.review.completed",
            actor.subject,
            {"review_id": str(review.id), "decision": decision},
        )
        await self.session.commit()
        return review

    async def create_revision(
        self, review_id: uuid.UUID, instructions: str, actor: Actor
    ) -> tuple[ArchitectureRevisionRequestModel, ArchitectureRunModel]:
        _require(actor, "architecture_reviewer", "architecture.revision.create")
        review = await self.session.get(ArchitectureReviewModel, review_id, with_for_update=True)
        if review is None or review.decision != ArchitectureReviewDecision.REQUEST_CHANGES:
            raise ArchitectureGovernanceError("Revision requires changes-requested review")
        existing = await self.session.scalar(
            select(ArchitectureRevisionRequestModel).where(
                ArchitectureRevisionRequestModel.source_review_id == review.id
            )
        )
        if existing is not None:
            run = await self._run(existing.revision_run_id) if existing.revision_run_id else None
            if run is None:
                raise ArchitectureGovernanceError("Revision request is incomplete")
            return existing, run
        source = await self._artifact(review.architecture_artifact_id)
        active = await self.session.scalar(
            select(ArchitectureRunModel).where(
                ArchitectureRunModel.project_id == source.project_id,
                ArchitectureRunModel.status.in_(
                    (ArchitectureRunStatus.READY, ArchitectureRunStatus.RUNNING)
                ),
            )
        )
        if active is not None:
            raise ArchitectureGovernanceError("Project already has an active architecture run")
        findings = list(
            (
                await self.session.scalars(
                    select(ArchitectureReviewFindingModel).where(
                        ArchitectureReviewFindingModel.review_id == review.id
                    )
                )
            ).all()
        )
        request = ArchitectureRevisionRequestModel(
            id=uuid.uuid4(),
            project_id=source.project_id,
            source_artifact_id=source.id,
            source_review_id=review.id,
            source_artifact_version=source.version,
            source_artifact_checksum=source.checksum,
            requirements_artifact_id=source.requirements_artifact_id,
            status=ArchitectureRevisionStatus.REQUESTED,
            requested_by=actor.subject,
            requested_by_role=actor.role,
            revision_instructions=instructions,
            inherited_findings=[
                {
                    "key": f.finding_key,
                    "description": f.description,
                    "required_change": f.required_change,
                    "blocking": f.blocking,
                }
                for f in findings
            ],
        )
        requirements = await self.session.get(ArtifactModel, source.requirements_artifact_id)
        if requirements is None or requirements.content_hash == "":
            raise ArchitectureGovernanceError("Requirements lineage is corrupt")
        run = ArchitectureRunModel(
            id=uuid.uuid4(),
            project_id=source.project_id,
            requirements_artifact_id=source.requirements_artifact_id,
            requirements_checksum=requirements.content_hash,
            requirements_version=source.version + 1,
            status=ArchitectureRunStatus.READY,
            crew_version="architecture-crew-v1",
            schema_version=source.schema_version,
            model_name="server-controlled",
            temperature=0,
            prompt_bundle_hash=hash_json({"revision": str(request.id)}),
            system_prompt_hash=hash_json({"system": "architecture-revision"}),
            execution_manifest={"revision_request_id": str(request.id), "network": False},
            revision_request_id=request.id,
            parent_architecture_artifact_id=source.id,
        )
        request.revision_run_id = run.id
        request.status = ArchitectureRevisionStatus.RUN_CREATED
        review.status = ArchitectureReviewStatus.SUPERSEDED
        self.session.add_all([request, run])
        await JobRepository(self.session).enqueue(
            project_id=source.project_id,
            run_id=None,
            job_type=JobType.RUN_ARCHITECTURE_CREW,
            payload={"run_id": str(run.id), "governed_architecture_run": True},
            max_attempts=2,
        )
        record_metric(ArchitectureMetric.REVISIONS)
        self._audit(
            source.project_id,
            "architecture.revision.created",
            actor.subject,
            {"request_id": str(request.id), "run_id": str(run.id)},
        )
        await self.session.commit()
        return request, run

    async def approve(
        self, artifact_id: uuid.UUID, evidence: dict[str, object], actor: Actor
    ) -> ArchitectureApprovalModel:
        _require(actor, "architecture_approver", "architecture.approve")
        artifact = await self._artifact(artifact_id, lock=True)
        latest = await self.session.scalar(
            select(ArchitectureArtifactModel)
            .where(ArchitectureArtifactModel.project_id == artifact.project_id)
            .order_by(ArchitectureArtifactModel.version.desc())
            .limit(1)
        )
        if latest is None or latest.id != artifact.id:
            raise ArchitectureGovernanceError("Only latest architecture version may be approved")
        review = await self.session.scalar(
            select(ArchitectureReviewModel)
            .where(
                ArchitectureReviewModel.architecture_artifact_id == artifact.id,
                ArchitectureReviewModel.status == ArchitectureReviewStatus.COMPLETED,
                ArchitectureReviewModel.decision == ArchitectureReviewDecision.RECOMMEND_APPROVAL,
            )
            .order_by(ArchitectureReviewModel.review_round.desc())
            .limit(1)
        )
        if review is None or review.reviewed_checksum != artifact.checksum:
            raise ArchitectureGovernanceError("Exact checksum lacks approval recommendation")
        if review.reviewer_id == actor.subject:
            raise ArchitectureGovernanceError("Reviewer cannot approve the same architecture")
        existing = await self.session.scalar(
            select(ArchitectureApprovalModel).where(
                ArchitectureApprovalModel.architecture_artifact_id == artifact.id
            )
        )
        if existing is not None:
            return existing
        payload = {
            "artifact_id": str(artifact.id),
            "review_id": str(review.id),
            "checksum": artifact.checksum,
            "version": artifact.version,
            "approver": actor.subject,
            "policy": self.APPROVAL_POLICY,
            "evidence": evidence,
        }
        approval = ArchitectureApprovalModel(
            id=uuid.uuid4(),
            architecture_artifact_id=artifact.id,
            approving_review_id=review.id,
            approved=True,
            approved_by=actor.subject,
            approver_role=actor.role,
            approver_subject_type=actor.actor_type,
            approved_checksum=artifact.checksum,
            architecture_version=artifact.version,
            review_checksum=review.reviewed_checksum,
            policy_version=self.APPROVAL_POLICY,
            evidence=evidence,
            evidence_checksum=hash_json(payload),
        )
        artifact.status = ArchitectureArtifactStatus.APPROVED
        self.session.add(approval)
        record_metric(ArchitectureMetric.APPROVALS)
        self._audit(
            artifact.project_id,
            "architecture.approved",
            actor.subject,
            {"approval_id": str(approval.id), "evidence_checksum": approval.evidence_checksum},
        )
        await self.session.commit()
        await self.session.refresh(approval)
        return approval

    async def gate(
        self, artifact_id: uuid.UUID, approval_id: uuid.UUID
    ) -> ArchitectureApprovalModel:
        record_metric(ArchitectureMetric.ELIGIBILITY_CHECKS)
        artifact = await self._artifact(artifact_id)
        approval = await self.session.get(ArchitectureApprovalModel, approval_id)
        latest = await self.session.scalar(
            select(ArchitectureArtifactModel)
            .where(ArchitectureArtifactModel.project_id == artifact.project_id)
            .order_by(ArchitectureArtifactModel.version.desc())
            .limit(1)
        )
        if (
            approval is None
            or not approval.approved
            or approval.architecture_artifact_id != artifact.id
            or approval.approved_checksum != artifact.checksum
            or latest is None
            or latest.id != artifact.id
            or artifact.status != ArchitectureArtifactStatus.APPROVED
        ):
            record_metric(ArchitectureMetric.ELIGIBILITY_FAILURES)
            raise ArchitectureGovernanceError(
                "Architecture is not eligible for work-package generation"
            )
        return approval

    async def _run(self, id: uuid.UUID | None, lock: bool = False) -> ArchitectureRunModel:
        if id is None:
            raise ArchitectureNotFoundError("Run not found")
        row = await self.session.get(ArchitectureRunModel, id, with_for_update=lock)
        if row is None:
            raise ArchitectureNotFoundError("Run not found")
        return row

    async def _artifact(self, id: uuid.UUID, lock: bool = False) -> ArchitectureArtifactModel:
        row = await self.session.get(ArchitectureArtifactModel, id, with_for_update=lock)
        if row is None:
            raise ArchitectureNotFoundError("Architecture artifact not found")
        return row

    def _audit(
        self, project_id: uuid.UUID, event: str, actor: str, payload: dict[str, object]
    ) -> None:
        self.session.add(
            AuditEventModel(
                id=uuid.uuid4(),
                project_id=project_id,
                event_type=event,
                actor_type="system" if actor == "system" else "human",
                actor_id=actor,
                payload=payload,
            )
        )
