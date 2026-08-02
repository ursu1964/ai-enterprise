import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.requirements_revision.service import (
    RequirementsRevisionService,
)
from ai_enterprise.config import Settings
from ai_enterprise.domain.enums import (
    ApprovalDecision,
    ArtifactType,
    JobType,
    ProjectStatus,
    RunStatus,
    WorkPackageStatus,
)
from ai_enterprise.domain.hashing import canonical_json, hash_json, hash_text
from ai_enterprise.domain.json_parsing import parse_model_json
from ai_enterprise.domain.work_package import WorkPackageContract
from ai_enterprise.domain.work_package_validation import (
    validate_repository_boundaries,
)
from ai_enterprise.infrastructure.crews.architecture_crew import (
    ArchitectureCrewRunner,
)
from ai_enterprise.infrastructure.crews.requirements_crew import (
    RequirementsCrewRunner,
)
from ai_enterprise.infrastructure.crews.work_package_crew import (
    WorkPackageCrewRunner,
)
from ai_enterprise.infrastructure.database.models import (
    ApprovalModel,
    ArtifactModel,
    AuditEventModel,
    CrewRunModel,
    ProjectModel,
    WorkPackageModel,
)
from ai_enterprise.infrastructure.jobs.repository import JobRepository
from ai_enterprise.infrastructure.repositories.git_repository import (
    GitRepositoryInspector,
)
from ai_enterprise.infrastructure.repositories.preparation import (
    prepare_project_repository,
)


class ProjectNotFoundError(Exception):
    pass


class InvalidProjectStateError(Exception):
    pass


class ArtifactNotFoundError(Exception):
    pass


class ProjectWorkflowService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        self._session = session
        self._settings = settings

    async def create_project(
        self,
        *,
        name: str,
        description: str,
        repository_path: str,
        repository_url: str | None,
        default_branch: str,
        actor_id: str,
        manifest: dict[str, Any] | None = None,
        project_type: str | None = None,
    ) -> ProjectModel:
        project_id = uuid.uuid4()
        preparation = prepare_project_repository(
            repository_path,
            default_branch,
            allowed_root=self._settings.repository_allowed_root,
        )

        manifest_body = dict(manifest or {})
        manifest_body.setdefault("schema_version", "1.0")
        manifest_body["project_id"] = str(project_id)
        manifest_body["name"] = name
        manifest_body["description"] = description
        manifest_body["repository_path"] = repository_path
        manifest_body["repository_url"] = repository_url
        manifest_body["default_branch"] = default_branch
        manifest_body["repository"] = {
            "path": repository_path,
            "url": repository_url,
            "default_branch": default_branch,
        }
        if project_type:
            manifest_body["project_type"] = project_type
        manifest_body["created_by"] = actor_id
        manifest_body["repository_preparation"] = preparation

        manifest_hash = hash_json(manifest_body)

        project = ProjectModel(
            id=project_id,
            name=name,
            description=description,
            repository_path=repository_path,
            repository_url=repository_url,
            default_branch=default_branch,
            status=ProjectStatus.CREATED,
            manifest_hash=manifest_hash,
            manifest=manifest_body,
        )

        manifest_artifact = ArtifactModel(
            id=uuid.uuid4(),
            project_id=project_id,
            artifact_type=ArtifactType.PROJECT_MANIFEST,
            media_type="application/json",
            content=canonical_json(manifest_body),
            content_hash=manifest_hash,
        )

        audit_event = AuditEventModel(
            id=uuid.uuid4(),
            project_id=project_id,
            event_type="project.created",
            actor_type="human",
            actor_id=actor_id,
            payload={
                "project_id": str(project_id),
                "manifest_hash": manifest_hash,
            },
        )

        self._session.add(project)
        await self._session.flush()

        self._session.add_all(
            [
                manifest_artifact,
                audit_event,
            ]
        )

        await self._session.commit()
        await self._session.refresh(project)

        return project

    async def queue_requirements_run(
        self,
        *,
        project_id: uuid.UUID,
        actor_id: str,
    ) -> CrewRunModel:
        project = await self._get_project(project_id)

        if project.status not in {
            ProjectStatus.CREATED,
            ProjectStatus.REQUIREMENTS_FAILED,
            ProjectStatus.REQUIREMENTS_REJECTED,
        }:
            raise InvalidProjectStateError(f"Cannot start requirements from state {project.status}")

        run_id = uuid.uuid4()

        run = CrewRunModel(
            id=run_id,
            project_id=project.id,
            crew_name="requirements_crew",
            status=RunStatus.QUEUED,
            input_payload={
                "project_name": project.name,
                "project_description": project.description,
                "manifest_hash": project.manifest_hash,
            },
        )

        project.status = ProjectStatus.REQUIREMENTS_QUEUED

        self._session.add(run)
        await self._session.flush()

        jobs = JobRepository(self._session)

        job = await jobs.enqueue(
            project_id=project.id,
            run_id=run_id,
            job_type=JobType.RUN_REQUIREMENTS_CREW,
            payload={
                "project_id": str(project.id),
                "run_id": str(run_id),
            },
            priority=100,
            max_attempts=3,
        )

        self._session.add(
            AuditEventModel(
                id=uuid.uuid4(),
                project_id=project.id,
                event_type="requirements.run.queued",
                actor_type="human",
                actor_id=actor_id,
                payload={
                    "run_id": str(run_id),
                    "job_id": str(job.id),
                },
            )
        )

        await self._session.commit()
        await self._session.refresh(run)

        return run

    async def execute_requirements_run(
        self,
        *,
        run_id: uuid.UUID,
    ) -> None:
        result = await self._session.execute(select(CrewRunModel).where(CrewRunModel.id == run_id))
        run = result.scalar_one_or_none()

        if run is None:
            raise RuntimeError(f"Run {run_id} does not exist")

        if run.status not in {
            RunStatus.QUEUED,
            RunStatus.FAILED,
        }:
            raise InvalidProjectStateError(f"Requirements run cannot execute from {run.status}")

        project = await self._get_project(run.project_id)

        try:
            run.status = RunStatus.RUNNING
            run.started_at = datetime.now(UTC)
            run.error_message = None
            project.status = ProjectStatus.REQUIREMENTS_RUNNING

            self._session.add(
                AuditEventModel(
                    id=uuid.uuid4(),
                    project_id=project.id,
                    event_type="requirements.run.started",
                    actor_type="system",
                    actor_id="requirements-worker",
                    payload={"run_id": str(run.id)},
                )
            )

            await self._session.commit()

            runner = RequirementsCrewRunner(self._settings)

            previous_artifact_content = None
            previous_artifact_id = run.input_payload.get("previous_artifact_id")
            if previous_artifact_id:
                previous_artifact = await self._session.get(
                    ArtifactModel, uuid.UUID(str(previous_artifact_id))
                )
                if previous_artifact is None:
                    raise ArtifactNotFoundError(str(previous_artifact_id))
                previous_artifact_content = previous_artifact.content

            crew_result = await asyncio.to_thread(
                runner.run,
                project_name=project.name,
                project_description=project.description,
                manifest_hash=project.manifest_hash,
                previous_artifact=previous_artifact_content,
                revision_cycle_number=run.input_payload.get("revision_cycle_number"),
                revision_feedback_summary=run.input_payload.get("revision_feedback_summary"),
                revision_feedback=run.input_payload.get("revision_feedback"),
                revision_feedback_hash=run.input_payload.get("revision_feedback_hash"),
            )

            artifact = ArtifactModel(
                id=uuid.uuid4(),
                project_id=project.id,
                run_id=run.id,
                artifact_type=ArtifactType.REQUIREMENTS_SPECIFICATION,
                media_type="text/markdown",
                content=crew_result.markdown,
                content_hash=hash_text(crew_result.markdown),
            )
            self._session.add(artifact)
            await self._session.flush()
            revisions = RequirementsRevisionService(self._session)
            if run.input_payload.get("revision_cycle_id"):
                await revisions.complete_cycle(
                    execution_run_id=run.id,
                    artifact_id=artifact.id,
                    raw_output_hash=hash_text(crew_result.raw_output),
                    repair_attempted=False,
                    repair_succeeded=None,
                    validation_errors=None,
                )
            else:
                await revisions.record_initial_artifact(artifact.id)

            run.status = RunStatus.SUCCEEDED
            run.completed_at = datetime.now(UTC)
            run.output_payload = {
                "artifact_type": ArtifactType.REQUIREMENTS_SPECIFICATION,
                "content_hash": artifact.content_hash,
            }

            project.status = ProjectStatus.AWAITING_REQUIREMENTS_APPROVAL
            auto_approval = self._auto_approval(
                project=project,
                artifact=artifact,
                event_type="requirements.auto_approved",
            )
            if auto_approval is not None:
                project.status = ProjectStatus.REQUIREMENTS_APPROVED

            events: list[object] = [
                artifact,
                AuditEventModel(
                        id=uuid.uuid4(),
                        project_id=project.id,
                        event_type="requirements.run.succeeded",
                        actor_type="agent",
                        actor_id="requirements-crew",
                        payload={
                            "run_id": str(run.id),
                            "artifact_id": str(artifact.id),
                            "content_hash": artifact.content_hash,
                        },
                ),
                AuditEventModel(
                        id=uuid.uuid4(),
                        project_id=project.id,
                        event_type="requirements.approval.requested",
                        actor_type="system",
                        actor_id="workflow-engine",
                        payload={
                            "run_id": str(run.id),
                            "artifact_id": str(artifact.id),
                        },
                ),
            ]
            if auto_approval is not None:
                events.extend(auto_approval)
            self._session.add_all(events)

            await self._session.commit()

        except Exception as exc:
            await self._session.rollback()

            run = await self._session.get(CrewRunModel, run_id)
            if run is None:
                raise RuntimeError(f"Crew run {run_id} disappeared") from exc
            failed_project = await self._session.get(
                ProjectModel,
                run.project_id,
            )
            if failed_project is None:
                raise ProjectNotFoundError(str(run.project_id)) from exc
            project = failed_project

            run.status = RunStatus.FAILED
            run.completed_at = datetime.now(UTC)
            run.error_message = str(exc)

            project.status = ProjectStatus.REQUIREMENTS_FAILED

            self._session.add(
                AuditEventModel(
                    id=uuid.uuid4(),
                    project_id=project.id,
                    event_type="requirements.run.failed",
                    actor_type="system",
                    actor_id="requirements-worker",
                    payload={
                        "run_id": str(run.id),
                        "error": str(exc),
                    },
                )
            )

            await self._session.commit()
            raise

    async def approve_requirements(
        self,
        *,
        project_id: uuid.UUID,
        artifact_id: uuid.UUID,
        decision: ApprovalDecision,
        reviewer: str,
        comment: str | None,
    ) -> ProjectModel:
        project = await self._get_project(project_id)

        if project.status != ProjectStatus.AWAITING_REQUIREMENTS_APPROVAL:
            raise InvalidProjectStateError("Project is not awaiting requirements approval")

        result = await self._session.execute(
            select(ArtifactModel).where(
                ArtifactModel.id == artifact_id,
                ArtifactModel.project_id == project_id,
                ArtifactModel.artifact_type == ArtifactType.REQUIREMENTS_SPECIFICATION,
            )
        )

        artifact = result.scalar_one_or_none()

        if artifact is None:
            raise ArtifactNotFoundError(str(artifact_id))

        approval = ApprovalModel(
            id=uuid.uuid4(),
            project_id=project.id,
            artifact_id=artifact.id,
            decision=decision,
            reviewer=reviewer,
            comment=comment,
        )

        if decision == ApprovalDecision.APPROVED:
            project.status = ProjectStatus.REQUIREMENTS_APPROVED
            event_type = "requirements.approved"
        else:
            project.status = ProjectStatus.REQUIREMENTS_REJECTED
            event_type = "requirements.rejected"

        self._session.add_all(
            [
                approval,
                AuditEventModel(
                    id=uuid.uuid4(),
                    project_id=project.id,
                    event_type=event_type,
                    actor_type="human",
                    actor_id=reviewer,
                    payload={
                        "artifact_id": str(artifact.id),
                        "artifact_hash": artifact.content_hash,
                        "comment": comment,
                    },
                ),
            ]
        )

        await self._session.commit()
        await self._session.refresh(project)

        return project

    async def queue_architecture_run(
        self,
        *,
        project_id: uuid.UUID,
        actor_id: str,
    ) -> CrewRunModel:
        project = await self._get_project(project_id)

        if project.status not in {
            ProjectStatus.REQUIREMENTS_APPROVED,
            ProjectStatus.ARCHITECTURE_FAILED,
            ProjectStatus.ARCHITECTURE_REJECTED,
        }:
            raise InvalidProjectStateError(f"Cannot start architecture from state {project.status}")

        requirements_result = await self._session.execute(
            select(ArtifactModel)
            .where(
                ArtifactModel.project_id == project.id,
                ArtifactModel.artifact_type == ArtifactType.REQUIREMENTS_SPECIFICATION,
            )
            .order_by(ArtifactModel.created_at.desc())
            .limit(1)
        )

        requirements_artifact = requirements_result.scalar_one_or_none()

        if requirements_artifact is None:
            raise ArtifactNotFoundError("Approved requirements artifact not found")

        approval_result = await self._session.execute(
            select(ApprovalModel)
            .where(
                ApprovalModel.project_id == project.id,
                ApprovalModel.artifact_id == requirements_artifact.id,
                ApprovalModel.decision == ApprovalDecision.APPROVED,
            )
            .order_by(ApprovalModel.created_at.desc())
            .limit(1)
        )

        approval = approval_result.scalar_one_or_none()

        if approval is None:
            raise InvalidProjectStateError("The selected requirements artifact is not approved")

        run_id = uuid.uuid4()

        run = CrewRunModel(
            id=run_id,
            project_id=project.id,
            crew_name="architecture_crew",
            status=RunStatus.QUEUED,
            input_payload={
                "requirements_artifact_id": str(requirements_artifact.id),
                "requirements_artifact_hash": (requirements_artifact.content_hash),
            },
        )

        project.status = ProjectStatus.ARCHITECTURE_QUEUED
        self._session.add(run)
        await self._session.flush()

        jobs = JobRepository(self._session)

        job = await jobs.enqueue(
            project_id=project.id,
            run_id=run_id,
            job_type=JobType.RUN_ARCHITECTURE_CREW,
            payload={
                "project_id": str(project.id),
                "run_id": str(run_id),
                "requirements_artifact_id": str(requirements_artifact.id),
                "requirements_artifact_hash": (requirements_artifact.content_hash),
            },
            priority=100,
            max_attempts=3,
        )

        self._session.add(
            AuditEventModel(
                id=uuid.uuid4(),
                project_id=project.id,
                event_type="architecture.run.queued",
                actor_type="human",
                actor_id=actor_id,
                payload={
                    "run_id": str(run_id),
                    "job_id": str(job.id),
                    "requirements_artifact_id": str(requirements_artifact.id),
                    "requirements_artifact_hash": (requirements_artifact.content_hash),
                },
            )
        )

        await self._session.commit()
        await self._session.refresh(run)

        return run

    async def execute_architecture_run(
        self,
        *,
        run_id: uuid.UUID,
    ) -> None:
        result = await self._session.execute(select(CrewRunModel).where(CrewRunModel.id == run_id))

        run = result.scalar_one_or_none()

        if run is None:
            raise RuntimeError(f"Architecture run {run_id} does not exist")

        if run.status not in {
            RunStatus.QUEUED,
            RunStatus.FAILED,
        }:
            raise InvalidProjectStateError(f"Architecture run cannot execute from {run.status}")

        project = await self._get_project(run.project_id)

        try:
            artifact_id = uuid.UUID(run.input_payload["requirements_artifact_id"])

            artifact_result = await self._session.execute(
                select(ArtifactModel).where(
                    ArtifactModel.id == artifact_id,
                    ArtifactModel.project_id == project.id,
                    ArtifactModel.artifact_type == ArtifactType.REQUIREMENTS_SPECIFICATION,
                )
            )

            requirements_artifact = artifact_result.scalar_one_or_none()

            if requirements_artifact is None:
                raise ArtifactNotFoundError(str(artifact_id))

            expected_hash = run.input_payload["requirements_artifact_hash"]

            actual_hash = hash_text(requirements_artifact.content)

            if actual_hash != expected_hash:
                raise RuntimeError("Requirements artifact integrity check failed")

            approval_result = await self._session.execute(
                select(ApprovalModel).where(
                    ApprovalModel.project_id == project.id,
                    ApprovalModel.artifact_id == requirements_artifact.id,
                    ApprovalModel.decision == ApprovalDecision.APPROVED,
                )
            )

            if approval_result.scalar_one_or_none() is None:
                raise InvalidProjectStateError(
                    "Architecture cannot run without approved requirements"
                )

            run.status = RunStatus.RUNNING
            run.started_at = datetime.now(UTC)
            run.error_message = None
            project.status = ProjectStatus.ARCHITECTURE_RUNNING

            self._session.add(
                AuditEventModel(
                    id=uuid.uuid4(),
                    project_id=project.id,
                    event_type="architecture.run.started",
                    actor_type="system",
                    actor_id="architecture-worker",
                    payload={
                        "run_id": str(run.id),
                        "requirements_artifact_id": str(requirements_artifact.id),
                        "requirements_artifact_hash": (requirements_artifact.content_hash),
                    },
                )
            )

            await self._session.commit()

            runner = ArchitectureCrewRunner(self._settings)

            crew_result = await asyncio.to_thread(
                runner.run,
                project_name=project.name,
                project_description=project.description,
                project_manifest_hash=project.manifest_hash,
                requirements_markdown=requirements_artifact.content,
                requirements_artifact_hash=(requirements_artifact.content_hash),
            )

            architecture_artifact_id = uuid.uuid4()

            architecture_artifact = ArtifactModel(
                id=architecture_artifact_id,
                project_id=project.id,
                run_id=run.id,
                artifact_type=ArtifactType.ARCHITECTURE_SPECIFICATION,
                media_type="text/markdown",
                content=crew_result.markdown,
                content_hash=hash_text(crew_result.markdown),
            )

            run.status = RunStatus.SUCCEEDED
            run.completed_at = datetime.now(UTC)
            run.output_payload = {
                "artifact_id": str(architecture_artifact_id),
                "artifact_type": (ArtifactType.ARCHITECTURE_SPECIFICATION),
                "content_hash": architecture_artifact.content_hash,
                "source_requirements_artifact_id": str(requirements_artifact.id),
                "source_requirements_hash": (requirements_artifact.content_hash),
            }

            self._session.add(architecture_artifact)
            await self._session.flush()

            project.status = ProjectStatus.AWAITING_ARCHITECTURE_APPROVAL
            auto_approval = self._auto_approval(
                project=project,
                artifact=architecture_artifact,
                event_type="architecture.auto_approved",
            )
            if auto_approval is not None:
                project.status = ProjectStatus.ARCHITECTURE_APPROVED

            events: list[object] = [
                AuditEventModel(
                        id=uuid.uuid4(),
                        project_id=project.id,
                        event_type="architecture.run.succeeded",
                        actor_type="agent",
                        actor_id="architecture-crew",
                        payload={
                            "run_id": str(run.id),
                            "artifact_id": str(architecture_artifact_id),
                            "artifact_hash": (architecture_artifact.content_hash),
                            "requirements_artifact_id": str(requirements_artifact.id),
                            "requirements_artifact_hash": (requirements_artifact.content_hash),
                        },
                ),
                AuditEventModel(
                        id=uuid.uuid4(),
                        project_id=project.id,
                        event_type=("architecture.approval.requested"),
                        actor_type="system",
                        actor_id="workflow-engine",
                        payload={
                            "artifact_id": str(architecture_artifact_id),
                            "artifact_hash": (architecture_artifact.content_hash),
                        },
                ),
            ]
            if auto_approval is not None:
                events.extend(auto_approval)
            self._session.add_all(events)

            await self._session.commit()

        except Exception as exc:
            await self._session.rollback()

            run = await self._session.get(CrewRunModel, run_id)
            if run is None:
                raise RuntimeError(f"Crew run {run_id} disappeared") from exc
            failed_project = await self._session.get(
                ProjectModel,
                run.project_id,
            )
            if failed_project is None:
                raise ProjectNotFoundError(str(run.project_id)) from exc
            project = failed_project

            run.status = RunStatus.FAILED
            run.completed_at = datetime.now(UTC)
            run.error_message = str(exc)
            project.status = ProjectStatus.ARCHITECTURE_FAILED

            self._session.add(
                AuditEventModel(
                    id=uuid.uuid4(),
                    project_id=project.id,
                    event_type="architecture.run.failed",
                    actor_type="system",
                    actor_id="architecture-worker",
                    payload={
                        "run_id": str(run.id),
                        "error": str(exc),
                    },
                )
            )

            await self._session.commit()
            raise

    async def approve_architecture(
        self,
        *,
        project_id: uuid.UUID,
        artifact_id: uuid.UUID,
        decision: ApprovalDecision,
        reviewer: str,
        comment: str | None,
    ) -> ProjectModel:
        project = await self._get_project(project_id)

        if project.status != ProjectStatus.AWAITING_ARCHITECTURE_APPROVAL:
            raise InvalidProjectStateError("Project is not awaiting architecture approval")

        result = await self._session.execute(
            select(ArtifactModel).where(
                ArtifactModel.id == artifact_id,
                ArtifactModel.project_id == project_id,
                ArtifactModel.artifact_type == ArtifactType.ARCHITECTURE_SPECIFICATION,
            )
        )

        artifact = result.scalar_one_or_none()

        if artifact is None:
            raise ArtifactNotFoundError(str(artifact_id))

        approval = ApprovalModel(
            id=uuid.uuid4(),
            project_id=project.id,
            artifact_id=artifact.id,
            decision=decision,
            reviewer=reviewer,
            comment=comment,
        )

        if decision == ApprovalDecision.APPROVED:
            project.status = ProjectStatus.ARCHITECTURE_APPROVED
            event_type = "architecture.approved"
        else:
            project.status = ProjectStatus.ARCHITECTURE_REJECTED
            event_type = "architecture.rejected"

        self._session.add_all(
            [
                approval,
                AuditEventModel(
                    id=uuid.uuid4(),
                    project_id=project.id,
                    event_type=event_type,
                    actor_type="human",
                    actor_id=reviewer,
                    payload={
                        "artifact_id": str(artifact.id),
                        "artifact_hash": artifact.content_hash,
                        "comment": comment,
                    },
                ),
            ]
        )

        await self._session.commit()
        await self._session.refresh(project)

        return project

    async def queue_work_package_planning(
        self,
        *,
        project_id: uuid.UUID,
        actor_id: str,
    ) -> CrewRunModel:
        project = await self._get_project(project_id)

        if project.status not in {
            ProjectStatus.ARCHITECTURE_APPROVED,
            ProjectStatus.WORK_PACKAGE_FAILED,
            ProjectStatus.WORK_PACKAGE_REJECTED,
        }:
            raise InvalidProjectStateError(f"Cannot plan work package from state {project.status}")

        architecture_artifact = await self._get_latest_approved_artifact(
            project_id=project.id,
            artifact_type=ArtifactType.ARCHITECTURE_SPECIFICATION,
        )

        if architecture_artifact.run_id is None:
            raise InvalidProjectStateError("Architecture artifact has no source run")

        architecture_run = await self._session.get(
            CrewRunModel,
            architecture_artifact.run_id,
        )

        if architecture_run is None:
            raise InvalidProjectStateError("Architecture source run does not exist")

        if architecture_run.output_payload is None:
            raise InvalidProjectStateError("Architecture source run has no output payload")

        requirements_artifact_id = uuid.UUID(
            architecture_run.output_payload["source_requirements_artifact_id"]
        )

        requirements_artifact = await self._session.get(
            ArtifactModel,
            requirements_artifact_id,
        )

        if requirements_artifact is None:
            raise ArtifactNotFoundError(str(requirements_artifact_id))

        requirements_hash = hash_text(requirements_artifact.content)

        architecture_hash = hash_text(architecture_artifact.content)

        if requirements_hash != requirements_artifact.content_hash:
            raise RuntimeError("Requirements artifact integrity check failed")

        if architecture_hash != architecture_artifact.content_hash:
            raise RuntimeError("Architecture artifact integrity check failed")

        run_id = uuid.uuid4()

        run = CrewRunModel(
            id=run_id,
            project_id=project.id,
            crew_name="work_package_planner_crew",
            status=RunStatus.QUEUED,
            input_payload={
                "requirements_artifact_id": str(requirements_artifact.id),
                "requirements_artifact_hash": (requirements_artifact.content_hash),
                "architecture_artifact_id": str(architecture_artifact.id),
                "architecture_artifact_hash": (architecture_artifact.content_hash),
            },
        )

        project.status = ProjectStatus.WORK_PACKAGE_QUEUED
        self._session.add(run)
        await self._session.flush()

        jobs = JobRepository(self._session)

        job = await jobs.enqueue(
            project_id=project.id,
            run_id=run_id,
            job_type=JobType.PLAN_WORK_PACKAGE,
            payload={
                "project_id": str(project.id),
                "run_id": str(run_id),
            },
            priority=100,
            max_attempts=3,
        )

        self._session.add(
            AuditEventModel(
                id=uuid.uuid4(),
                project_id=project.id,
                event_type="work_package.planning.queued",
                actor_type="human",
                actor_id=actor_id,
                payload={
                    "run_id": str(run_id),
                    "job_id": str(job.id),
                    "requirements_artifact_id": str(requirements_artifact.id),
                    "requirements_artifact_hash": (requirements_artifact.content_hash),
                    "architecture_artifact_id": str(architecture_artifact.id),
                    "architecture_artifact_hash": (architecture_artifact.content_hash),
                },
            )
        )

        await self._session.commit()
        await self._session.refresh(run)

        return run

    async def execute_work_package_planning(
        self,
        *,
        run_id: uuid.UUID,
    ) -> None:
        run = await self._session.get(CrewRunModel, run_id)

        if run is None:
            raise RuntimeError(f"Work-package planning run {run_id} does not exist")

        if run.status not in {
            RunStatus.QUEUED,
            RunStatus.FAILED,
        }:
            raise InvalidProjectStateError(f"Planning run cannot execute from {run.status}")

        project = await self._get_project(run.project_id)

        try:
            requirements_artifact_id = uuid.UUID(run.input_payload["requirements_artifact_id"])

            architecture_artifact_id = uuid.UUID(run.input_payload["architecture_artifact_id"])

            requirements_artifact = await self._session.get(
                ArtifactModel,
                requirements_artifact_id,
            )

            architecture_artifact = await self._session.get(
                ArtifactModel,
                architecture_artifact_id,
            )

            if requirements_artifact is None:
                raise ArtifactNotFoundError(str(requirements_artifact_id))

            if architecture_artifact is None:
                raise ArtifactNotFoundError(str(architecture_artifact_id))

            expected_requirements_hash = run.input_payload["requirements_artifact_hash"]

            expected_architecture_hash = run.input_payload["architecture_artifact_hash"]

            if hash_text(requirements_artifact.content) != expected_requirements_hash:
                raise RuntimeError("Requirements artifact integrity check failed")

            if hash_text(architecture_artifact.content) != expected_architecture_hash:
                raise RuntimeError("Architecture artifact integrity check failed")

            inspector = GitRepositoryInspector(
                allowed_root=self._settings.repository_allowed_root,
            )

            repository = await inspector.inspect(project.repository_path)

            if not repository.is_clean:
                raise InvalidProjectStateError(
                    "Repository must be clean before work-package planning"
                )

            run.status = RunStatus.RUNNING
            run.started_at = datetime.now(UTC)
            run.error_message = None
            project.status = ProjectStatus.WORK_PACKAGE_PLANNING

            self._session.add(
                AuditEventModel(
                    id=uuid.uuid4(),
                    project_id=project.id,
                    event_type="work_package.planning.started",
                    actor_type="system",
                    actor_id="work-package-worker",
                    payload={
                        "run_id": str(run.id),
                        "base_commit_sha": repository.commit_sha,
                    },
                )
            )

            await self._session.commit()

            runner = WorkPackageCrewRunner(self._settings)

            result = await asyncio.to_thread(
                runner.run,
                project_id=str(project.id),
                project_name=project.name,
                project_description=project.description,
                base_commit_sha=repository.commit_sha,
                requirements_artifact_id=str(requirements_artifact.id),
                requirements_hash=(requirements_artifact.content_hash),
                requirements_markdown=(requirements_artifact.content),
                architecture_artifact_id=str(architecture_artifact.id),
                architecture_hash=(architecture_artifact.content_hash),
                architecture_markdown=(architecture_artifact.content),
                tracked_files=list(repository.tracked_files),
            )

            parsed = parse_model_json(result.raw_json)

            # Identity fields are assigned by the system of record. The
            # crew cannot redirect the work package to different artifacts.
            parsed["project_id"] = str(project.id)
            parsed["base_commit_sha"] = repository.commit_sha
            parsed["source_requirements_artifact_id"] = str(requirements_artifact.id)
            parsed["source_requirements_hash"] = requirements_artifact.content_hash
            parsed["source_architecture_artifact_id"] = str(architecture_artifact.id)
            parsed["source_architecture_hash"] = architecture_artifact.content_hash

            contract = WorkPackageContract.model_validate(parsed)

            if contract.project_id != str(project.id):
                raise RuntimeError("Work package changed the project ID")

            if contract.base_commit_sha != repository.commit_sha:
                raise RuntimeError("Work package changed the base commit SHA")

            if contract.source_requirements_artifact_id != str(requirements_artifact.id):
                raise RuntimeError("Work package changed requirements artifact ID")

            if contract.source_requirements_hash != requirements_artifact.content_hash:
                raise RuntimeError("Work package changed requirements hash")

            if contract.source_architecture_artifact_id != str(architecture_artifact.id):
                raise RuntimeError("Work package changed architecture artifact ID")

            if contract.source_architecture_hash != architecture_artifact.content_hash:
                raise RuntimeError("Work package changed architecture hash")

            validate_repository_boundaries(
                contract=contract,
                tracked_files=set(repository.tracked_files),
            )

            contract_data = contract.model_dump(mode="json")
            contract_content = canonical_json(contract_data)
            contract_hash = hash_json(contract_data)

            work_package_id = uuid.uuid4()
            artifact_id = uuid.uuid4()

            artifact = ArtifactModel(
                id=artifact_id,
                project_id=project.id,
                run_id=run.id,
                artifact_type=ArtifactType.WORK_PACKAGE,
                media_type="application/json",
                content=contract_content,
                content_hash=contract_hash,
            )

            work_package = WorkPackageModel(
                id=work_package_id,
                project_id=project.id,
                planning_run_id=run.id,
                artifact_id=artifact_id,
                status=WorkPackageStatus.AWAITING_APPROVAL,
                title=contract.title,
                objective=contract.objective,
                repository_url=project.repository_url,
                base_commit_sha=contract.base_commit_sha,
                source_requirements_artifact_id=(requirements_artifact.id),
                source_requirements_hash=(requirements_artifact.content_hash),
                source_architecture_artifact_id=(architecture_artifact.id),
                source_architecture_hash=(architecture_artifact.content_hash),
                contract=contract_data,
                contract_hash=contract_hash,
            )

            run.status = RunStatus.SUCCEEDED
            run.completed_at = datetime.now(UTC)
            run.output_payload = {
                "work_package_id": str(work_package_id),
                "artifact_id": str(artifact_id),
                "contract_hash": contract_hash,
                "base_commit_sha": contract.base_commit_sha,
            }

            project.status = ProjectStatus.AWAITING_WORK_PACKAGE_APPROVAL
            auto_approval = self._auto_approval(
                project=project,
                artifact=artifact,
                event_type="work_package.auto_approved",
            )
            if auto_approval is not None:
                work_package.status = WorkPackageStatus.APPROVED
                project.status = ProjectStatus.WORK_PACKAGE_APPROVED

            self._session.add(artifact)
            await self._session.flush()

            events: list[object] = [
                work_package,
                AuditEventModel(
                        id=uuid.uuid4(),
                        project_id=project.id,
                        event_type="work_package.planning.succeeded",
                        actor_type="agent",
                        actor_id="work-package-planner-crew",
                        payload={
                            "run_id": str(run.id),
                            "work_package_id": str(work_package_id),
                            "artifact_id": str(artifact_id),
                            "contract_hash": contract_hash,
                            "base_commit_sha": (contract.base_commit_sha),
                        },
                ),
                AuditEventModel(
                        id=uuid.uuid4(),
                        project_id=project.id,
                        event_type="work_package.approval.requested",
                        actor_type="system",
                        actor_id="workflow-engine",
                        payload={
                            "work_package_id": str(work_package_id),
                            "artifact_id": str(artifact_id),
                            "contract_hash": contract_hash,
                        },
                ),
            ]
            if auto_approval is not None:
                events.extend(auto_approval)
            self._session.add_all(events)

            await self._session.commit()

        except Exception as exc:
            await self._session.rollback()

            run = await self._session.get(CrewRunModel, run_id)
            if run is None:
                raise RuntimeError(f"Crew run {run_id} disappeared") from exc
            failed_project = await self._session.get(
                ProjectModel,
                run.project_id,
            )
            if failed_project is None:
                raise ProjectNotFoundError(str(run.project_id)) from exc
            project = failed_project

            run.status = RunStatus.FAILED
            run.completed_at = datetime.now(UTC)
            run.error_message = str(exc)
            project.status = ProjectStatus.WORK_PACKAGE_FAILED

            self._session.add(
                AuditEventModel(
                    id=uuid.uuid4(),
                    project_id=project.id,
                    event_type="work_package.planning.failed",
                    actor_type="system",
                    actor_id="work-package-worker",
                    payload={
                        "run_id": str(run.id),
                        "error": str(exc),
                    },
                )
            )

            await self._session.commit()
            raise

    async def approve_work_package(
        self,
        *,
        project_id: uuid.UUID,
        work_package_id: uuid.UUID,
        decision: ApprovalDecision,
        reviewer: str,
        comment: str | None,
    ) -> WorkPackageModel:
        project = await self._get_project(project_id)

        if project.status != ProjectStatus.AWAITING_WORK_PACKAGE_APPROVAL:
            raise InvalidProjectStateError("Project is not awaiting work-package approval")

        work_package = await self._session.get(
            WorkPackageModel,
            work_package_id,
        )

        if work_package is None or work_package.project_id != project.id:
            raise ArtifactNotFoundError(str(work_package_id))

        if work_package.artifact_id is None:
            raise InvalidProjectStateError("Work package has no immutable artifact")

        artifact = await self._session.get(
            ArtifactModel,
            work_package.artifact_id,
        )

        if artifact is None:
            raise ArtifactNotFoundError(str(work_package.artifact_id))

        recalculated_hash = hash_text(artifact.content)

        if recalculated_hash != work_package.contract_hash:
            raise RuntimeError("Work-package artifact integrity check failed")

        approval = ApprovalModel(
            id=uuid.uuid4(),
            project_id=project.id,
            artifact_id=artifact.id,
            decision=decision,
            reviewer=reviewer,
            comment=comment,
        )

        if decision == ApprovalDecision.APPROVED:
            work_package.status = WorkPackageStatus.APPROVED
            project.status = ProjectStatus.WORK_PACKAGE_APPROVED
            event_type = "work_package.approved"
        else:
            work_package.status = WorkPackageStatus.REJECTED
            project.status = ProjectStatus.WORK_PACKAGE_REJECTED
            event_type = "work_package.rejected"

        self._session.add_all(
            [
                approval,
                AuditEventModel(
                    id=uuid.uuid4(),
                    project_id=project.id,
                    event_type=event_type,
                    actor_type="human",
                    actor_id=reviewer,
                    payload={
                        "work_package_id": str(work_package.id),
                        "artifact_id": str(artifact.id),
                        "contract_hash": (work_package.contract_hash),
                        "base_commit_sha": (work_package.base_commit_sha),
                        "comment": comment,
                    },
                ),
            ]
        )

        await self._session.commit()
        await self._session.refresh(work_package)

        return work_package

    async def _get_project(
        self,
        project_id: uuid.UUID,
    ) -> ProjectModel:
        result = await self._session.execute(
            select(ProjectModel).where(ProjectModel.id == project_id)
        )

        project = result.scalar_one_or_none()

        if project is None:
            raise ProjectNotFoundError(str(project_id))

        return project

    def _auto_approval(
        self,
        *,
        project: ProjectModel,
        artifact: ArtifactModel,
        event_type: str,
    ) -> list[ApprovalModel | AuditEventModel] | None:
        policy = project.manifest.get("autonomous_execution")
        if not isinstance(policy, dict) or policy.get("enabled") is not True:
            return None
        if policy.get("authority") != "manifest_ingestion":
            return None
        phase_key = {
            "requirements.auto_approved": "auto_approve_requirements",
            "architecture.auto_approved": "auto_approve_architecture",
            "work_package.auto_approved": "auto_approve_work_package",
        }.get(event_type)
        if phase_key is None or policy.get(phase_key) is not True:
            return None
        return [
            ApprovalModel(
                id=uuid.uuid4(),
                project_id=project.id,
                artifact_id=artifact.id,
                decision=ApprovalDecision.APPROVED,
                reviewer="manifest-autonomy-policy",
                comment=(
                    "Approved automatically because the ingested manifesto enabled "
                    "controlled autonomous execution."
                ),
            ),
            AuditEventModel(
                id=uuid.uuid4(),
                project_id=project.id,
                event_type=event_type,
                actor_type="system",
                actor_id="manifest-autonomy-policy",
                payload={
                    "artifact_id": str(artifact.id),
                    "artifact_hash": artifact.content_hash,
                    "authority": "manifest_ingestion",
                    "mode": policy.get("mode", "controlled_demo"),
                },
            ),
        ]

    async def _get_latest_approved_artifact(
        self,
        *,
        project_id: uuid.UUID,
        artifact_type: ArtifactType,
    ) -> ArtifactModel:
        result = await self._session.execute(
            select(ArtifactModel)
            .join(
                ApprovalModel,
                ApprovalModel.artifact_id == ArtifactModel.id,
            )
            .where(
                ArtifactModel.project_id == project_id,
                ArtifactModel.artifact_type == artifact_type,
                ApprovalModel.decision == ApprovalDecision.APPROVED,
            )
            .order_by(ApprovalModel.created_at.desc())
            .limit(1)
        )

        artifact = result.scalar_one_or_none()

        if artifact is None:
            raise ArtifactNotFoundError(f"No approved {artifact_type} artifact found")

        return artifact
