import asyncio
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.audit.writer import AuditWriter
from ai_enterprise.application.execution_workflow import (
    ExecutionNotFoundError,
    InvalidExecutionStateError,
)
from ai_enterprise.application.review.dto import ReviewerAgentOutput
from ai_enterprise.config import Settings
from ai_enterprise.domain.enums import (
    ApprovalDecision,
    ArtifactType,
    JobType,
    WorkPackageStatus,
)
from ai_enterprise.domain.execution.enums import ExecutionStatus
from ai_enterprise.domain.execution.policies import (
    DEFAULT_FORBIDDEN_PATHS,
    ExecutionScope,
    RuntimeLimits,
)
from ai_enterprise.domain.hashing import hash_text
from ai_enterprise.domain.review.enums import (
    FindingSeverity,
    FindingStatus,
    PatchReviewStatus,
    ReviewDecision,
)
from ai_enterprise.domain.review.exceptions import (
    PatchArtifactMissingError,
    PatchReviewError,
)
from ai_enterprise.domain.review.policies import (
    ReviewDecisionPolicy,
    ReviewFinding,
    ReviewPolicy,
)
from ai_enterprise.infrastructure.database.models import (
    ApprovalModel,
    ArtifactModel,
    ExecutionRunModel,
    PatchReviewCheckModel,
    PatchReviewEventModel,
    PatchReviewFindingModel,
    PatchReviewRunModel,
    ProjectModel,
    WorkPackageModel,
)
from ai_enterprise.infrastructure.execution.patch_builder import PatchBuilder
from ai_enterprise.infrastructure.execution.repository_snapshot import (
    RepositorySnapshotService,
)
from ai_enterprise.infrastructure.execution.scope_validator import (
    ScopeValidator,
)
from ai_enterprise.infrastructure.execution_broker.application_runtime import BrokerReviewRuntime
from ai_enterprise.infrastructure.jobs.repository import JobRepository
from ai_enterprise.infrastructure.repositories.git_repository import (
    GitRepositoryInspector,
)
from ai_enterprise.infrastructure.review.deterministic_reviewer import (
    DeterministicReviewer,
)
from ai_enterprise.infrastructure.review.finding_normalizer import (
    FindingNormalizer,
)
from ai_enterprise.infrastructure.review.patch_applier import PatchApplier
from ai_enterprise.infrastructure.review.review_runtime import (
    DockerReviewRuntime,
)
from ai_enterprise.infrastructure.review.reviewer_agent import ReviewerAgent
from ai_enterprise.infrastructure.review.secret_scanner import SecretScanner

DEFAULT_REVIEW_POLICY: dict[str, Any] = {
    "decision": {
        "reject_on_critical": True,
        "reject_on_high_security": True,
        "request_changes_on_high": True,
        "request_changes_on_medium_count": 3,
        "require_all_approved_tests": True,
        "require_patch_reproducibility": True,
    },
    "review_checks": [],
}

MAXIMUM_DIFF_CHARS = 60_000


class ReviewNotFoundError(Exception):
    pass


class ReviewCandidatePatchService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        self._session = session
        self._settings = settings

    async def request_review(
        self,
        *,
        project_id: uuid.UUID,
        execution_id: uuid.UUID,
        idempotency_key: str,
        actor_id: str,
    ) -> PatchReviewRunModel:
        existing = await self._find_by_idempotency(
            project_id=project_id,
            idempotency_key=idempotency_key,
        )

        if existing is not None:
            return existing

        project = await self._get_project(project_id)
        execution = await self._get_execution(project_id, execution_id)

        if execution.status != ExecutionStatus.SUCCEEDED:
            raise InvalidExecutionStateError(f"Cannot review execution in state {execution.status}")

        if execution.patch_artifact_id is None:
            raise PatchArtifactMissingError("Execution has no candidate patch artifact")

        work_package = await self._get_approved_work_package(
            project_id=project.id,
            work_package_id=execution.work_package_id,
        )

        await self._get_approval(work_package)

        await self._verify_no_prior_final_review(execution_id)

        review_id = uuid.uuid4()

        review = PatchReviewRunModel(
            id=review_id,
            project_id=project.id,
            work_package_id=work_package.id,
            execution_run_id=execution.id,
            patch_artifact_id=execution.patch_artifact_id,
            status=PatchReviewStatus.PENDING,
            base_commit=execution.base_commit,
            expected_patch_sha256=execution.patch_sha256,
            review_image=self._settings.review_image,
            review_policy=DEFAULT_REVIEW_POLICY,
            idempotency_key=idempotency_key,
        )

        self._session.add(review)
        await self._session.flush()

        jobs = JobRepository(self._session)

        job = await jobs.enqueue(
            project_id=project.id,
            run_id=None,
            job_type=JobType.REVIEW_CANDIDATE_PATCH,
            payload={
                "project_id": str(project.id),
                "review_id": str(review_id),
            },
            priority=90,
            max_attempts=1,
        )

        await self._append_audit_event(
            project_id=project.id,
            event_type="patch_review.requested",
            actor_type="human",
            actor_id=actor_id,
            payload={
                "review_id": str(review_id),
                "execution_run_id": str(execution.id),
                "work_package_id": str(work_package.id),
                "patch_artifact_id": str(execution.patch_artifact_id),
                "job_id": str(job.id),
            },
        )

        await self._session.commit()
        await self._session.refresh(review)

        return review

    async def review_candidate_patch(
        self,
        *,
        review_id: uuid.UUID,
    ) -> None:
        review = await self._session.get(
            PatchReviewRunModel,
            review_id,
        )

        if review is None:
            raise ReviewNotFoundError(str(review_id))

        if review.status not in {
            PatchReviewStatus.PENDING,
            PatchReviewStatus.FAILED,
        }:
            raise InvalidExecutionStateError(f"Review cannot run from {review.status}")

        execution = await self._get_execution(
            review.project_id,
            review.execution_run_id,
        )
        work_package = await self._get_work_package(
            project_id=review.project_id,
            work_package_id=review.work_package_id,
        )
        project = await self._get_project(review.project_id)

        repository_path = project.repository_path
        snapshot_service = RepositorySnapshotService(
            source_repository=Path(repository_path),
            snapshots_root=self._settings.review_snapshots_root,
        )

        inspector = GitRepositoryInspector(
            allowed_root=self._settings.repository_allowed_root,
        )

        snapshot = None

        try:
            review.status = PatchReviewStatus.PREPARING
            review.started_at = datetime.now(UTC)
            review.failure_code = None
            review.failure_message = None

            self._add_event(
                review,
                "patch_review.preparing",
                {
                    "execution_run_id": str(execution.id),
                    "patch_artifact_id": str(execution.patch_artifact_id),
                    "base_commit": execution.base_commit,
                },
            )

            await self._session.commit()

            fingerprint_before = await inspector.fingerprint(repository_path)

            if fingerprint_before.head_sha != execution.base_commit:
                raise PatchReviewError(f"Base commit {execution.base_commit} is not host HEAD")

            snapshot = await asyncio.to_thread(
                snapshot_service.create,
                execution_id=f"review-{review_id}",
                expected_commit=execution.base_commit,
            )

            review.snapshot_path = str(snapshot.path)

            self._add_event(
                review,
                "patch_review.snapshot_created",
                {
                    "snapshot_sha256": snapshot.snapshot_sha256,
                    "base_commit": snapshot.base_commit,
                },
            )

            await self._session.commit()

            patch_artifact = await self._get_artifact(review.patch_artifact_id)

            patch_path = self._materialize_patch(
                review_id=review_id,
                patch_artifact=patch_artifact,
            )

            limits = self._runtime_limits(work_package.contract)

            applier = PatchApplier()

            applied_patch = await asyncio.to_thread(
                applier.verify_and_apply,
                repository=snapshot.path,
                patch_path=patch_path,
                expected_sha256=review.expected_patch_sha256,
                maximum_patch_bytes=(self._settings.review_maximum_patch_bytes),
            )

            review.actual_patch_sha256 = applied_patch.patch_sha256

            self._add_event(
                review,
                "patch_review.patch_verified",
                {
                    "patch_sha256": applied_patch.patch_sha256,
                    "patch_size_bytes": applied_patch.patch_size_bytes,
                },
            )

            await self._session.commit()

            deterministic = DeterministicReviewer()
            repository_state = await asyncio.to_thread(
                deterministic.inspect_repository,
                snapshot.path,
            )

            review.resulting_tree_hash = repository_state.tree_hash

            scope = self._build_scope(work_package.contract)
            maximum_changed_files = work_package.contract["file_scope"]["maximum_changed_files"]

            validator = ScopeValidator()

            statistics = await asyncio.to_thread(
                validator.inspect,
                repository=snapshot.path,
                scope=scope,
                maximum_changed_files=maximum_changed_files,
            )

            self._add_event(
                review,
                "patch_review.scope_verified",
                {
                    "changed_file_count": statistics.file_count,
                    "insertions": statistics.insertions,
                    "deletions": statistics.deletions,
                    "resulting_tree_hash": repository_state.tree_hash,
                },
            )

            await self._session.commit()

            findings: list[ReviewFinding] = []

            execution_files = tuple(sorted(execution.changed_files or []))

            patch_reproducible = execution_files == statistics.files

            if not patch_reproducible:
                findings.append(
                    ReviewFinding(
                        rule_id="PATCH-REPRO-001",
                        category="integrity",
                        severity=FindingSeverity.CRITICAL,
                        title="Candidate changed-file set differs",
                        description=(
                            "The independently applied patch changed "
                            "a different file set from the execution "
                            "record."
                        ),
                        blocking=True,
                        evidence={
                            "execution_files": list(execution_files),
                            "review_files": list(statistics.files),
                        },
                    )
                )

            scanner = SecretScanner()
            findings.extend(
                await asyncio.to_thread(
                    scanner.scan,
                    snapshot.path,
                )
            )

            review_configuration = {
                "schema_version": 1,
                "review_id": str(review_id),
                "execution_run_id": str(execution.id),
                "work_package_id": str(work_package.id),
                "base_commit": execution.base_commit,
                "patch_sha256": applied_patch.patch_sha256,
                "approved_tests": self._approved_tests(
                    work_package.contract,
                    limits,
                ),
                "review_checks": review.review_policy.get(
                    "review_checks",
                    [],
                ),
            }

            review.status = PatchReviewStatus.RUNNING

            self._add_event(
                review,
                "patch_review.container_started",
                {
                    "image": review.review_image,
                    "review_check_count": len(review_configuration["review_checks"]),
                },
            )

            await self._session.commit()

            runtime = self._review_runtime()

            runtime_result = await asyncio.to_thread(
                runtime.run,
                review_id=str(review_id),
                image=review.review_image,
                snapshot_path=snapshot.path,
                review_input=review_configuration,
                review_temp_root=self._settings.review_temp_root,
                limits=limits,
            )

            review.container_id = runtime_result.container_id
            review.review_image_digest = runtime_result.container_image_digest

            review.status = PatchReviewStatus.EVALUATING

            self._add_event(
                review,
                "patch_review.check_finished",
                {
                    "container_id": runtime_result.container_id,
                    "approved_test_count": len(runtime_result.approved_tests),
                    "review_check_count": len(runtime_result.review_checks),
                    "success": runtime_result.success,
                },
            )

            await self._session.commit()

            await self._record_checks_and_artifacts(
                review=review,
                runtime_result=runtime_result,
            )

            approved_tests_passed = runtime_result.success and all(
                not check.timed_out and check.exit_code == 0
                for check in runtime_result.approved_tests
                if check.required
            )

            reviewer = ReviewerAgent(self._settings)
            normalizer = FindingNormalizer()

            agent_result: ReviewerAgentOutput | None = None

            try:
                agent_result = await asyncio.to_thread(
                    reviewer.review,
                    work_package_contract=work_package.contract,
                    repository=snapshot.path,
                    changed_files=statistics.files,
                    deterministic_findings=tuple(findings),
                    check_results=runtime_result.approved_tests + runtime_result.review_checks,
                )

                findings.extend(
                    normalizer.from_review_container(
                        findings=[item.model_dump() for item in agent_result.findings]
                    )
                )
            except PatchReviewError as exc:
                self._add_event(
                    review,
                    "patch_review.agent_failed",
                    {"error": str(exc)},
                )
                await self._session.commit()

            decision_policy = ReviewDecisionPolicy()
            policy = ReviewPolicy(**review.review_policy["decision"])

            decision = decision_policy.decide(
                findings=tuple(findings),
                approved_tests_passed=approved_tests_passed,
                patch_reproducible=patch_reproducible,
                policy=policy,
            )

            summary = (
                agent_result.summary
                if agent_result is not None
                else ("Independent review completed. Reviewer agent analysis was unavailable.")
            )

            report = self._build_report(
                review=review,
                execution=execution,
                work_package=work_package,
                applied_patch_sha256=applied_patch.patch_sha256,
                repository_state=repository_state,
                statistics=statistics,
                required_checks_passed=approved_tests_passed,
                decision=decision,
                summary=summary,
                findings=findings,
            )

            report_artifact = ArtifactModel(
                id=uuid.uuid4(),
                project_id=review.project_id,
                artifact_type=ArtifactType.PATCH_REVIEW_REPORT,
                media_type="application/json",
                content=json.dumps(
                    report,
                    indent=2,
                    sort_keys=True,
                ),
                content_hash=hash_text(json.dumps(report, sort_keys=True)),
            )

            self._session.add(report_artifact)
            await self._session.flush()

            review.review_report_artifact_id = report_artifact.id
            review.decision_summary = summary

            for finding in findings:
                self._session.add(
                    PatchReviewFindingModel(
                        id=uuid.uuid4(),
                        patch_review_run_id=review.id,
                        rule_id=finding.rule_id,
                        category=finding.category,
                        severity=finding.severity.value,
                        status=FindingStatus.OPEN,
                        title=finding.title,
                        description=finding.description,
                        file_path=finding.file_path,
                        line_start=finding.line_start,
                        line_end=finding.line_end,
                        evidence=finding.evidence,
                        blocking=finding.blocking,
                    )
                )

            review.status = self._decision_to_status(decision)
            review.finished_at = datetime.now(UTC)

            self._add_event(
                review,
                f"patch_review.{decision.value}",
                {
                    "decision": decision.value,
                    "report_artifact_id": str(report_artifact.id),
                    "resulting_tree_hash": repository_state.tree_hash,
                    "finding_count": len(findings),
                },
            )

            fingerprint_after = await inspector.fingerprint(repository_path)

            if fingerprint_after != fingerprint_before:
                raise PatchReviewError("Host repository fingerprint changed during review")

            await self._append_audit_event(
                project_id=project.id,
                event_type=f"patch_review.{decision.value}",
                actor_type="system",
                actor_id="review-worker",
                payload={
                    "review_id": str(review.id),
                    "execution_run_id": str(execution.id),
                    "patch_sha256": applied_patch.patch_sha256,
                    "resulting_tree_hash": repository_state.tree_hash,
                    "finding_count": len(findings),
                },
            )

            await self._session.commit()

            snapshot_service.delete(f"review-{review_id}")

        except Exception as exc:
            await self._session.rollback()

            review = await self._session.get(
                PatchReviewRunModel,
                review_id,
            )

            if review is not None:
                review.status = PatchReviewStatus.FAILED
                review.finished_at = datetime.now(UTC)
                review.failure_code = getattr(
                    exc,
                    "code",
                    "patch_review_error",
                )
                review.failure_message = str(exc)

                self._session.add(
                    PatchReviewEventModel(
                        id=uuid.uuid4(),
                        patch_review_run_id=review.id,
                        event_type="patch_review.failed",
                        payload={
                            "failure_code": review.failure_code,
                            "error": str(exc),
                        },
                    )
                )

                failed_project = await self._session.get(
                    ProjectModel,
                    review.project_id,
                )

                if failed_project is not None:
                    await self._append_audit_event(
                        project_id=failed_project.id,
                        event_type="patch_review.failed",
                        actor_type="system",
                        actor_id="review-worker",
                        payload={
                            "review_id": str(review.id),
                            "failure_code": review.failure_code,
                            "error": str(exc),
                        },
                    )

                await self._session.commit()

            if snapshot is not None:
                snapshot_service.delete(f"review-{review_id}")

            raise

    async def _record_checks_and_artifacts(
        self,
        *,
        review: PatchReviewRunModel,
        runtime_result: Any,
    ) -> None:
        checks = list(runtime_result.approved_tests)
        checks.extend(runtime_result.review_checks)

        for sequence, check in enumerate(checks):
            stdout_artifact = ArtifactModel(
                id=uuid.uuid4(),
                project_id=review.project_id,
                artifact_type=ArtifactType.REVIEW_CHECK_STDOUT,
                media_type="text/plain",
                content=check.stdout,
                content_hash=hash_text(check.stdout),
            )

            stderr_artifact = ArtifactModel(
                id=uuid.uuid4(),
                project_id=review.project_id,
                artifact_type=ArtifactType.REVIEW_CHECK_STDERR,
                media_type="text/plain",
                content=check.stderr,
                content_hash=hash_text(check.stderr),
            )

            self._session.add_all([stdout_artifact, stderr_artifact])
            await self._session.flush()

            if check.timed_out:
                check_status = "timed_out"
            elif check.exit_code == 0:
                check_status = "passed"
            else:
                check_status = "failed"

            check_type = (
                "approved_test" if sequence < len(runtime_result.approved_tests) else "review_check"
            )

            self._session.add(
                PatchReviewCheckModel(
                    id=uuid.uuid4(),
                    patch_review_run_id=review.id,
                    sequence=sequence,
                    check_type=check_type,
                    name=check.name,
                    command=list(check.argv),
                    status=check_status,
                    exit_code=check.exit_code,
                    duration_ms=check.duration_ms,
                    stdout_artifact_id=stdout_artifact.id,
                    stderr_artifact_id=stderr_artifact.id,
                )
            )

        await self._session.commit()

    def _add_event(
        self,
        review: PatchReviewRunModel,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        self._session.add(
            PatchReviewEventModel(
                id=uuid.uuid4(),
                patch_review_run_id=review.id,
                event_type=event_type,
                payload=payload,
            )
        )

    def _ensure_review_runtime_dispatch_wired(self) -> None:
        if self._settings.execution_container_provider.strip().lower() == "restricted-local-docker":
            BrokerReviewRuntime.from_settings(
                self._settings,
                owner_worker_id=f"worker:{self._settings.worker_profile}",
            )

    def _review_runtime(self) -> Any:
        if self._settings.execution_container_provider.strip().lower() == "restricted-local-docker":
            return BrokerReviewRuntime.from_settings(
                self._settings,
                owner_worker_id=f"worker:{self._settings.worker_profile}",
            )
        return DockerReviewRuntime()

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

    def _materialize_patch(
        self,
        *,
        review_id: uuid.UUID,
        patch_artifact: ArtifactModel,
    ) -> Path:
        builder = PatchBuilder(self._settings.review_artifacts_root)

        return builder.materialize(
            artifact_content=patch_artifact.content,
            base_name=f"review-{review_id}",
        )

    def _approved_tests(
        self,
        contract: dict[str, Any],
        limits: RuntimeLimits,
    ) -> list[dict[str, Any]]:
        test_commands = contract["command_policy"]["test_commands"]

        return [
            {
                "argv": command,
                "timeout_seconds": limits.test_timeout_seconds,
                "required": True,
            }
            for command in test_commands
        ]

    def _build_report(
        self,
        *,
        review: PatchReviewRunModel,
        execution: ExecutionRunModel,
        work_package: WorkPackageModel,
        applied_patch_sha256: str,
        repository_state: Any,
        statistics: Any,
        required_checks_passed: bool,
        decision: ReviewDecision,
        summary: str,
        findings: list[ReviewFinding],
    ) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "review_id": str(review.id),
            "execution_run_id": str(execution.id),
            "work_package_id": str(work_package.id),
            "base_commit": execution.base_commit,
            "patch_sha256": applied_patch_sha256,
            "resulting_tree_hash": repository_state.tree_hash,
            "changed_files": list(statistics.files),
            "insertions": statistics.insertions,
            "deletions": statistics.deletions,
            "required_checks_passed": required_checks_passed,
            "decision": decision.value,
            "summary": summary,
            "findings": [
                {
                    "rule_id": finding.rule_id,
                    "category": finding.category,
                    "severity": finding.severity.value,
                    "title": finding.title,
                    "description": finding.description,
                    "blocking": finding.blocking,
                    "file_path": finding.file_path,
                    "line_start": finding.line_start,
                    "line_end": finding.line_end,
                    "evidence": finding.evidence,
                }
                for finding in findings
            ],
        }

    @staticmethod
    def _decision_to_status(decision: ReviewDecision) -> PatchReviewStatus:
        if decision == ReviewDecision.ACCEPT:
            return PatchReviewStatus.ACCEPTED
        if decision == ReviewDecision.CHANGES_REQUESTED:
            return PatchReviewStatus.CHANGES_REQUESTED
        return PatchReviewStatus.REJECTED

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
            test_timeout_seconds=(self._settings.review_default_check_timeout_seconds),
            nano_cpus=int(float(resources["cpu_count"]) * 1_000_000_000),
            memory_bytes=memory_bytes,
            memory_swap_bytes=memory_bytes,
            pids_limit=int(resources["process_limit"]),
        )

    async def _get_project(
        self,
        project_id: uuid.UUID,
    ) -> ProjectModel:
        project = await self._session.get(ProjectModel, project_id)

        if project is None:
            raise ReviewNotFoundError(f"Project {project_id} does not exist")

        return project

    async def _get_execution(
        self,
        project_id: uuid.UUID,
        execution_id: uuid.UUID,
    ) -> ExecutionRunModel:
        execution = await self._session.get(
            ExecutionRunModel,
            execution_id,
        )

        if execution is None or execution.project_id != project_id:
            raise ExecutionNotFoundError(f"Execution {execution_id} does not exist")

        return execution

    async def _get_artifact(
        self,
        artifact_id: uuid.UUID,
    ) -> ArtifactModel:
        artifact = await self._session.get(ArtifactModel, artifact_id)

        if artifact is None:
            raise PatchArtifactMissingError(f"Artifact {artifact_id} does not exist")

        return artifact

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
            raise ReviewNotFoundError(f"Work package {work_package_id} does not exist")

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
            raise PatchReviewError(f"Work package {work_package_id} is not approved")

        return work_package

    async def _get_approval(
        self,
        work_package: WorkPackageModel,
    ) -> ApprovalModel:
        if work_package.artifact_id is None:
            raise PatchReviewError("Work package has no immutable artifact")

        result = await self._session.execute(
            select(ApprovalModel).where(
                ApprovalModel.project_id == work_package.project_id,
                ApprovalModel.artifact_id == work_package.artifact_id,
                ApprovalModel.decision == ApprovalDecision.APPROVED,
            )
        )

        approval = result.scalar_one_or_none()

        if approval is None:
            raise PatchReviewError(f"Work package {work_package.id} has no valid approval")

        return approval

    async def _verify_no_prior_final_review(
        self,
        execution_id: uuid.UUID,
    ) -> None:
        result = await self._session.execute(
            select(PatchReviewRunModel).where(
                PatchReviewRunModel.execution_run_id == execution_id,
                PatchReviewRunModel.status.in_(
                    {
                        PatchReviewStatus.ACCEPTED,
                        PatchReviewStatus.CHANGES_REQUESTED,
                        PatchReviewStatus.REJECTED,
                    }
                ),
            )
        )

        if result.scalars().first() is not None:
            raise PatchReviewError(f"Execution {execution_id} already has a final review")

    async def _find_by_idempotency(
        self,
        *,
        project_id: uuid.UUID,
        idempotency_key: str,
    ) -> PatchReviewRunModel | None:
        result = await self._session.execute(
            select(PatchReviewRunModel).where(
                PatchReviewRunModel.project_id == project_id,
                PatchReviewRunModel.idempotency_key == idempotency_key,
            )
        )

        return result.scalar_one_or_none()
