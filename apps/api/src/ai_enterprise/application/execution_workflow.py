import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.audit.writer import AuditWriter
from ai_enterprise.config import Settings
from ai_enterprise.domain.enums import (
    ApprovalDecision,
    ArtifactType,
    JobType,
    ProjectStatus,
    WorkPackageStatus,
)
from ai_enterprise.domain.execution.enums import ExecutionStatus, TestStatus
from ai_enterprise.domain.execution.exceptions import (
    ApprovalInvalidError,
    BaseCommitMismatchError,
    ExecutionTimeoutError,
    IdempotencyConflictError,
    ScopeViolationError,
    WorkPackageNotApprovedError,
)
from ai_enterprise.domain.execution.policies import (
    DEFAULT_FORBIDDEN_PATHS,
    ExecutionScope,
    RuntimeLimits,
)
from ai_enterprise.domain.hashing import hash_json, hash_text
from ai_enterprise.infrastructure.database.models import (
    ApprovalModel,
    ArtifactModel,
    ExecutionEventModel,
    ExecutionRunModel,
    ExecutionTestResultModel,
    ProjectModel,
    WorkPackageModel,
)
from ai_enterprise.infrastructure.execution.docker_runtime import (
    DockerExecutionRuntime,
)
from ai_enterprise.infrastructure.execution.implementation_planner import (
    ImplementationPlanner,
)
from ai_enterprise.infrastructure.execution.patch_builder import PatchBuilder
from ai_enterprise.infrastructure.execution.repository_snapshot import (
    RepositorySnapshotService,
)
from ai_enterprise.infrastructure.execution.scope_validator import (
    ScopeValidator,
)
from ai_enterprise.infrastructure.execution_broker.application_runtime import (
    BrokerExecutionRuntime,
)
from ai_enterprise.infrastructure.jobs.repository import JobRepository
from ai_enterprise.infrastructure.repositories.git_repository import (
    GitRepositoryInspector,
)


class ExecutionNotFoundError(Exception):
    pass


class InvalidExecutionStateError(Exception):
    pass


class ExecutionApplicationService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        self._session = session
        self._settings = settings

    async def request_execution(
        self,
        *,
        project_id: uuid.UUID,
        work_package_id: uuid.UUID,
        idempotency_key: str,
        actor_id: str,
    ) -> ExecutionRunModel:
        existing = await self._find_by_idempotency(
            project_id=project_id,
            idempotency_key=idempotency_key,
        )

        if existing is not None:
            if existing.work_package_id != work_package_id:
                raise IdempotencyConflictError(
                    f"Idempotency key {idempotency_key} is already bound "
                    f"to work package {existing.work_package_id}"
                )

            return existing

        project = await self._get_project(project_id)

        if project.status != ProjectStatus.WORK_PACKAGE_APPROVED:
            raise InvalidExecutionStateError(f"Cannot execute from state {project.status}")

        work_package = await self._get_approved_work_package(
            project_id=project.id,
            work_package_id=work_package_id,
        )

        if hash_json(project.manifest) != project.manifest_hash:
            raise ApprovalInvalidError("Project manifest is not immutable")

        if hash_json(work_package.contract) != work_package.contract_hash:
            raise ApprovalInvalidError("Work-package contract is not immutable")

        approval = await self._get_approval(work_package)

        self._verify_base_commit(
            work_package,
            repository_path=project.repository_path,
        )

        run_id = uuid.uuid4()

        limits = self._runtime_limits(work_package.contract)

        run = ExecutionRunModel(
            id=run_id,
            project_id=project.id,
            work_package_id=work_package.id,
            approval_id=approval.id,
            status=ExecutionStatus.PENDING,
            base_commit=work_package.base_commit_sha,
            container_image=self._settings.execution_image,
            timeout_seconds=limits.timeout_seconds,
            cpu_limit=limits.nano_cpus / 1_000_000_000,
            memory_limit_bytes=limits.memory_bytes,
            pids_limit=limits.pids_limit,
            network_disabled=True,
            runtime_policy={
                "schema_version": 1,
                "execution_timeout_seconds": limits.timeout_seconds,
                "implementation_timeout_seconds": (limits.implementation_timeout_seconds),
                "test_timeout_seconds": limits.test_timeout_seconds,
                "maximum_patch_bytes": (self._settings.execution_maximum_patch_bytes),
                "network": work_package.contract.get("network", {}),
            },
            idempotency_key=idempotency_key,
        )

        self._session.add(run)
        await self._session.flush()

        jobs = JobRepository(self._session)

        job = await jobs.enqueue(
            project_id=project.id,
            run_id=None,
            job_type=JobType.EXECUTE_WORK_PACKAGE,
            payload={
                "project_id": str(project.id),
                "execution_id": str(run_id),
                "work_package_id": str(work_package.id),
            },
            priority=100,
            max_attempts=1,
        )

        await self._append_audit_event(
            project_id=project.id,
            event_type="execution.requested",
            actor_type="human",
            actor_id=actor_id,
            payload={
                "execution_id": str(run_id),
                "work_package_id": str(work_package.id),
                "contract_hash": work_package.contract_hash,
                "base_commit_sha": work_package.base_commit_sha,
                "job_id": str(job.id),
            },
        )

        await self._session.commit()
        await self._session.refresh(run)

        return run

    async def execute_work_package(
        self,
        *,
        execution_id: uuid.UUID,
    ) -> None:
        run = await self._session.get(ExecutionRunModel, execution_id)

        if run is None:
            raise ExecutionNotFoundError(str(execution_id))

        if run.status != ExecutionStatus.PENDING:
            raise InvalidExecutionStateError(f"Execution cannot run from {run.status}")

        project = await self._get_project(run.project_id)
        work_package = await self._get_work_package(
            project_id=project.id,
            work_package_id=run.work_package_id,
        )

        repository_path = project.repository_path
        snapshot_service = RepositorySnapshotService(
            source_repository=Path(repository_path),
            snapshots_root=self._settings.execution_snapshots_root,
        )

        inspector = GitRepositoryInspector(
            allowed_root=self._settings.repository_allowed_root,
        )

        try:
            run.status = ExecutionStatus.PREPARING
            run.started_at = datetime.now(UTC)
            run.failure_code = None
            run.failure_message = None

            self._session.add(
                ExecutionEventModel(
                    id=uuid.uuid4(),
                    execution_run_id=run.id,
                    event_type="execution.started",
                    payload={
                        "work_package_id": str(work_package.id),
                        "base_commit": run.base_commit,
                    },
                )
            )

            await self._session.commit()

            await self._validate_execution_invariants(
                run=run,
                project=project,
                work_package=work_package,
            )

            fingerprint_before = await inspector.fingerprint(repository_path)

            if fingerprint_before.head_sha != run.base_commit:
                raise BaseCommitMismatchError(
                    f"Expected base commit {run.base_commit}, "
                    f"host HEAD is {fingerprint_before.head_sha}"
                )

            run.base_tree_sha = fingerprint_before.tree_sha

            snapshot = await asyncio.to_thread(
                snapshot_service.create,
                execution_id=str(execution_id),
                expected_commit=run.base_commit,
            )

            run.snapshot_path = str(snapshot.path)

            self._session.add(
                ExecutionEventModel(
                    id=uuid.uuid4(),
                    execution_run_id=run.id,
                    event_type="execution.snapshot.created",
                    payload={
                        "snapshot_sha256": snapshot.snapshot_sha256,
                        "base_commit": snapshot.base_commit,
                    },
                )
            )

            await self._session.commit()

            planner = ImplementationPlanner(self._settings)

            tracked_files = await asyncio.to_thread(
                list_snapshot_tracked_files,
                snapshot.path,
            )

            plan = await asyncio.to_thread(
                planner.plan,
                contract=work_package.contract,
                tracked_files=tracked_files,
            )

            edits = [
                {
                    "path": edit.path,
                    "mode": edit.mode,
                    "content": edit.content,
                }
                for edit in plan.edits
            ]

            runtime_input = self._build_runtime_input(
                execution_id=execution_id,
                work_package=work_package,
                edits_count=len(edits),
            )

            run.status = ExecutionStatus.RUNNING

            self._session.add(
                ExecutionEventModel(
                    id=uuid.uuid4(),
                    execution_run_id=run.id,
                    event_type="execution.implementation.planned",
                    payload={
                        "edit_count": len(edits),
                        "plan_sha256": hash_text(plan.raw_json),
                    },
                )
            )

            await self._session.commit()

            runtime = self._execution_runtime()

            limits = self._runtime_limits(work_package.contract)

            result = await asyncio.to_thread(
                runtime.run,
                execution_id=str(execution_id),
                image=self._settings.execution_image,
                snapshot_path=snapshot.path,
                runtime_input=runtime_input,
                runtime_temp_root=self._settings.execution_temp_root,
                limits=limits,
                edits=edits,
            )

            run.container_id = result.container_id
            run.container_image_digest = result.container_image_digest
            run.implementation_exit_code = result.implementation.get("exit_code")

            expected_test_count = len(work_package.contract["command_policy"]["test_commands"])
            if len(result.tests) != expected_test_count:
                raise RuntimeError(
                    "Not every approved test command was attempted: "
                    f"expected {expected_test_count}, got {len(result.tests)}"
                )

            if not result.success:
                await self._record_artifacts_and_results(
                    run=run,
                    container_result=result,
                )
                run.status = ExecutionStatus.FAILED
                run.failure_code = (
                    "implementation_failed"
                    if run.implementation_exit_code not in {None, 0}
                    else "tests_failed"
                )
                run.failure_message = "Implementation or one or more required tests failed"
                run.finished_at = datetime.now(UTC)
                await self._add_terminal_events(
                    run=run,
                    project=project,
                    work_package=work_package,
                    event_type="execution.failed",
                    test_summary=self._test_summary(result),
                )
                await self._session.commit()
                snapshot_service.delete(str(execution_id))
                return

            run.status = ExecutionStatus.VALIDATING

            scope = self._build_scope(work_package.contract)
            maximum_changed_files = work_package.contract["file_scope"]["maximum_changed_files"]

            validator = ScopeValidator()

            change_statistics = await asyncio.to_thread(
                validator.inspect,
                repository=snapshot.path,
                scope=scope,
                maximum_changed_files=maximum_changed_files,
            )

            run.changed_files = list(change_statistics.files)
            run.changed_file_count = change_statistics.file_count
            run.insertions = change_statistics.insertions
            run.deletions = change_statistics.deletions

            self._session.add(
                ExecutionEventModel(
                    id=uuid.uuid4(),
                    execution_run_id=run.id,
                    event_type="execution.scope.validated",
                    payload={
                        "changed_file_count": change_statistics.file_count,
                        "insertions": change_statistics.insertions,
                        "deletions": change_statistics.deletions,
                        "files": list(change_statistics.files),
                    },
                )
            )

            await self._session.commit()

            patch_builder = PatchBuilder(self._settings.execution_artifacts_root)

            patch = await asyncio.to_thread(
                patch_builder.build,
                execution_id=str(execution_id),
                repository=snapshot.path,
                maximum_patch_bytes=(self._settings.execution_maximum_patch_bytes),
            )

            fingerprint_after = await inspector.fingerprint(repository_path)

            if fingerprint_after != fingerprint_before:
                raise RuntimeError("Host repository fingerprint changed during execution")

            await self._record_artifacts_and_results(
                run=run,
                container_result=result,
                patch_bytes=patch.path.read_bytes(),
                patch_sha256=patch.sha256,
            )

            self._session.add(
                ExecutionEventModel(
                    id=uuid.uuid4(),
                    execution_run_id=run.id,
                    event_type="execution.patch.generated",
                    payload={
                        "patch_sha256": patch.sha256,
                        "patch_size_bytes": patch.size_bytes,
                    },
                )
            )

            if result.success:
                run.status = ExecutionStatus.SUCCEEDED
                event_type = "execution.succeeded"
            else:
                run.status = ExecutionStatus.FAILED
                run.failure_code = "tests_failed"
                run.failure_message = "One or more required tests failed"
                event_type = "execution.failed"

            run.finished_at = datetime.now(UTC)

            await self._append_audit_event(
                project_id=project.id,
                event_type=event_type,
                actor_type="system",
                actor_id="execution-worker",
                payload={
                    "execution_id": str(run.id),
                    "work_package_id": str(work_package.id),
                    "patch_sha256": patch.sha256,
                    "test_summary": self._test_summary(result),
                },
            )

            self._session.add(
                ExecutionEventModel(
                    id=uuid.uuid4(),
                    execution_run_id=run.id,
                    event_type="execution.finished",
                    payload={
                        "status": str(run.status),
                        "failure_code": run.failure_code,
                    },
                )
            )

            await self._session.commit()

            snapshot_service.delete(str(execution_id))

        except Exception as exc:
            await self._session.rollback()

            run = await self._session.get(
                ExecutionRunModel,
                execution_id,
            )

            if run is not None:
                if isinstance(exc, ScopeViolationError):
                    run.status = ExecutionStatus.REJECTED
                elif isinstance(exc, ExecutionTimeoutError):
                    run.status = ExecutionStatus.TIMED_OUT
                else:
                    run.status = ExecutionStatus.FAILED
                run.finished_at = datetime.now(UTC)
                run.failure_code = getattr(exc, "code", "execution_failed")
                run.failure_message = str(exc)

                self._session.add(
                    ExecutionEventModel(
                        id=uuid.uuid4(),
                        execution_run_id=run.id,
                        event_type="execution.failed",
                        payload={
                            "failure_code": run.failure_code,
                            "error": str(exc),
                        },
                    )
                )

                failed_project = await self._session.get(
                    ProjectModel,
                    run.project_id,
                )

                if failed_project is not None:
                    await self._append_audit_event(
                        project_id=failed_project.id,
                        event_type="execution.failed",
                        actor_type="system",
                        actor_id="execution-worker",
                        payload={
                            "execution_id": str(run.id),
                            "failure_code": run.failure_code,
                            "error": str(exc),
                        },
                    )

                await self._session.commit()

            snapshot_service.delete(str(execution_id))

            raise

    async def _record_artifacts_and_results(
        self,
        *,
        run: ExecutionRunModel,
        container_result: Any,
        patch_bytes: bytes | None = None,
        patch_sha256: str | None = None,
    ) -> None:
        log_artifact = ArtifactModel(
            id=uuid.uuid4(),
            project_id=run.project_id,
            artifact_type=ArtifactType.EXECUTION_LOG,
            media_type="application/x-jsonlines",
            content=container_result.runtime_log,
            content_hash=hash_text(container_result.runtime_log),
        )

        artifacts = [log_artifact]
        patch_artifact: ArtifactModel | None = None
        if patch_bytes is not None and patch_sha256 is not None:
            patch_artifact = ArtifactModel(
                id=uuid.uuid4(),
                project_id=run.project_id,
                artifact_type=ArtifactType.CANDIDATE_PATCH,
                media_type="text/x-patch",
                content=patch_bytes.decode("utf-8", errors="replace"),
                content_hash=patch_sha256,
            )
            artifacts.append(patch_artifact)

        self._session.add_all(artifacts)
        await self._session.flush()

        run.log_artifact_id = log_artifact.id
        if patch_artifact is not None:
            run.patch_artifact_id = patch_artifact.id
            run.patch_sha256 = patch_sha256

        for sequence, test in enumerate(container_result.tests):
            stdout_artifact = ArtifactModel(
                id=uuid.uuid4(),
                project_id=run.project_id,
                artifact_type=ArtifactType.TEST_STDOUT,
                media_type="text/plain",
                content=test.stdout,
                content_hash=hash_text(test.stdout),
            )

            stderr_artifact = ArtifactModel(
                id=uuid.uuid4(),
                project_id=run.project_id,
                artifact_type=ArtifactType.TEST_STDERR,
                media_type="text/plain",
                content=test.stderr,
                content_hash=hash_text(test.stderr),
            )

            self._session.add_all([stdout_artifact, stderr_artifact])
            await self._session.flush()

            if test.timed_out:
                test_status = TestStatus.TIMED_OUT
            elif test.exit_code == 0:
                test_status = TestStatus.PASSED
            else:
                test_status = TestStatus.FAILED

            self._session.add(
                ExecutionTestResultModel(
                    id=uuid.uuid4(),
                    execution_run_id=run.id,
                    sequence=sequence,
                    command=list(test.argv),
                    exit_code=test.exit_code,
                    status=test_status,
                    duration_ms=test.duration_ms,
                    stdout_artifact_id=stdout_artifact.id,
                    stderr_artifact_id=stderr_artifact.id,
                )
            )

    async def _validate_execution_invariants(
        self,
        *,
        run: ExecutionRunModel,
        project: ProjectModel,
        work_package: WorkPackageModel,
    ) -> None:
        if work_package.status != WorkPackageStatus.APPROVED:
            raise WorkPackageNotApprovedError(f"Work package {work_package.id} is not approved")

        approval = await self._get_approval(work_package)
        if approval.id != run.approval_id:
            raise ApprovalInvalidError(
                "Execution approval is no longer the approved artifact approval"
            )

        if hash_json(project.manifest) != project.manifest_hash:
            raise ApprovalInvalidError("Project manifest is not immutable")

        if hash_json(work_package.contract) != work_package.contract_hash:
            raise ApprovalInvalidError("Work-package contract is not immutable")

        command_policy = work_package.contract.get("command_policy", {})
        if not command_policy.get("test_commands"):
            raise ApprovalInvalidError("Approved test commands are required")

        file_scope = work_package.contract.get("file_scope", {})
        if not (file_scope.get("allowed_files") or file_scope.get("allowed_directories")):
            raise ApprovalInvalidError("Allowed changed paths are required")

        if not (
            file_scope.get("forbidden_files") is not None
            and file_scope.get("forbidden_directories") is not None
        ):
            raise ApprovalInvalidError("Forbidden paths must be defined")

        if run.container_image != self._settings.execution_image:
            raise ApprovalInvalidError("Execution image is not permitted by current runtime policy")

        if work_package.contract.get("network", {}).get("policy") != "none":
            raise ApprovalInvalidError("Execution network must be disabled")

    async def _add_terminal_events(
        self,
        *,
        run: ExecutionRunModel,
        project: ProjectModel,
        work_package: WorkPackageModel,
        event_type: str,
        test_summary: dict[str, Any],
    ) -> None:
        payload = {
            "execution_id": str(run.id),
            "work_package_id": str(work_package.id),
            "failure_code": run.failure_code,
            "test_summary": test_summary,
        }
        await self._append_audit_event(
            project_id=project.id,
            event_type=event_type,
            actor_type="system",
            actor_id="execution-worker",
            payload=payload,
        )
        self._session.add(
            ExecutionEventModel(
                id=uuid.uuid4(),
                execution_run_id=run.id,
                event_type="execution.finished",
                payload={
                    "status": str(run.status),
                    "failure_code": run.failure_code,
                },
            )
        )

    async def _append_audit_event(
        self,
        *,
        project_id: uuid.UUID,
        event_type: str,
        actor_type: str,
        actor_id: str,
        payload: dict[str, Any],
    ) -> None:
        await AuditWriter(self._session).append_project_event(
            project_id=project_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            payload=payload,
        )

    def _build_runtime_input(
        self,
        *,
        execution_id: uuid.UUID,
        work_package: WorkPackageModel,
        edits_count: int,
    ) -> dict[str, Any]:
        limits = self._runtime_limits(work_package.contract)

        test_commands = work_package.contract["command_policy"]["test_commands"]

        tests = [
            {
                "argv": command,
                "timeout_seconds": limits.test_timeout_seconds,
                "required": True,
            }
            for command in test_commands
        ]

        return {
            "schema_version": 1,
            "execution_id": str(execution_id),
            "work_package_id": str(work_package.id),
            "base_commit": work_package.base_commit_sha,
            "implementation": {
                "argv": [
                    "python",
                    "/opt/runtime/apply_edits.py",
                    "--input",
                    "/runtime-input/edits.json",
                ],
                "timeout_seconds": limits.implementation_timeout_seconds,
            },
            "edits_count": edits_count,
            "tests": tests,
        }

    def _execution_runtime(self) -> Any:
        if self._settings.execution_container_provider.strip().lower() == "restricted-local-docker":
            return BrokerExecutionRuntime.from_settings(
                self._settings,
                owner_worker_id=f"worker:{self._settings.worker_profile}",
            )
        return DockerExecutionRuntime()

    def _runtime_limits(
        self,
        contract: dict[str, Any],
    ) -> RuntimeLimits:
        resources = contract["resources"]

        memory_bytes = int(resources["memory_mb"]) * 1024 * 1024

        return RuntimeLimits(
            timeout_seconds=int(resources["execution_timeout_seconds"]),
            implementation_timeout_seconds=(
                self._settings.execution_implementation_timeout_seconds
            ),
            test_timeout_seconds=(self._settings.execution_default_test_timeout_seconds),
            nano_cpus=int(float(resources["cpu_count"]) * 1_000_000_000),
            memory_bytes=memory_bytes,
            memory_swap_bytes=memory_bytes,
            pids_limit=int(resources["process_limit"]),
        )

    def _build_scope(
        self,
        contract: dict[str, Any],
    ) -> ExecutionScope:
        file_scope = contract["file_scope"]

        allowed_paths = list(file_scope["allowed_files"])
        allowed_paths.extend(file_scope.get("allowed_directories", []))

        forbidden_paths = list(file_scope.get("forbidden_files", []))
        forbidden_paths.extend(file_scope.get("forbidden_directories", []))
        forbidden_paths.extend(DEFAULT_FORBIDDEN_PATHS)

        return ExecutionScope(
            allowed_paths=tuple(allowed_paths),
            forbidden_paths=tuple(forbidden_paths),
        )

    async def _get_project(
        self,
        project_id: uuid.UUID,
    ) -> ProjectModel:
        project = await self._session.get(ProjectModel, project_id)

        if project is None:
            raise ExecutionNotFoundError(f"Project {project_id} does not exist")

        return project

    async def _get_work_package(
        self,
        *,
        project_id: uuid.UUID,
        work_package_id: uuid.UUID,
    ) -> WorkPackageModel:
        work_package = await self._session.get(
            WorkPackageModel,
            work_package_id,
        )

        if work_package is None or work_package.project_id != project_id:
            raise ExecutionNotFoundError(f"Work package {work_package_id} does not exist")

        return work_package

    async def _get_approved_work_package(
        self,
        *,
        project_id: uuid.UUID,
        work_package_id: uuid.UUID,
    ) -> WorkPackageModel:
        work_package = await self._get_work_package(
            project_id=project_id,
            work_package_id=work_package_id,
        )

        if work_package.status != WorkPackageStatus.APPROVED:
            raise WorkPackageNotApprovedError(f"Work package {work_package_id} is not approved")

        return work_package

    async def _get_approval(
        self,
        work_package: WorkPackageModel,
    ) -> ApprovalModel:
        if work_package.artifact_id is None:
            raise ApprovalInvalidError("Work package has no immutable artifact")

        result = await self._session.execute(
            select(ApprovalModel).where(
                ApprovalModel.project_id == work_package.project_id,
                ApprovalModel.artifact_id == work_package.artifact_id,
                ApprovalModel.decision == ApprovalDecision.APPROVED,
            )
        )

        approval = result.scalar_one_or_none()

        if approval is None:
            raise ApprovalInvalidError(f"Work package {work_package.id} has no valid approval")

        return approval

    async def _find_by_idempotency(
        self,
        *,
        project_id: uuid.UUID,
        idempotency_key: str,
    ) -> ExecutionRunModel | None:
        result = await self._session.execute(
            select(ExecutionRunModel).where(
                ExecutionRunModel.project_id == project_id,
                ExecutionRunModel.idempotency_key == idempotency_key,
            )
        )

        return result.scalar_one_or_none()

    def _verify_base_commit(
        self,
        work_package: WorkPackageModel,
        *,
        repository_path: str,
    ) -> None:
        service = RepositorySnapshotService(
            source_repository=Path(repository_path),
            snapshots_root=self._settings.execution_snapshots_root,
        )

        resolved = service.verify_commit(work_package.base_commit_sha)

        if resolved != work_package.base_commit_sha:
            raise BaseCommitMismatchError(
                f"Base commit {work_package.base_commit_sha} resolved to {resolved}"
            )

    @staticmethod
    def _test_summary(container_result: Any) -> dict[str, Any]:
        total = len(container_result.tests)
        passed = sum(
            1 for test in container_result.tests if test.exit_code == 0 and not test.timed_out
        )

        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "success": container_result.success,
        }


def list_snapshot_tracked_files(repository: Path) -> list[str]:
    import subprocess

    result = subprocess.run(
        ["git", "-C", str(repository), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]
