from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.api.dependencies import Actor
from ai_enterprise.domain.decomposition.core import (
    DecompositionPolicy,
    DecompositionState,
    assert_transition,
    canonical_hash,
)
from ai_enterprise.domain.decomposition.determinism import (
    CandidateNormalizer,
    DeterministicGraphBuilder,
)
from ai_enterprise.domain.decomposition.validation import (
    DecompositionValidationService,
    FindingSeverity,
    ValidationContext,
)
from ai_enterprise.domain.enums import JobStatus, JobType
from ai_enterprise.infrastructure.architecture.models import (
    ArchitectureApprovalModel,
    ArchitectureArtifactModel,
)
from ai_enterprise.infrastructure.database.models import (
    ApprovalModel,
    ArtifactModel,
    AuditEventModel,
    JobModel,
    ProjectModel,
)
from ai_enterprise.infrastructure.decomposition.contracts import (
    DecompositionCrewContext,
    DecompositionCrewProvider,
)
from ai_enterprise.infrastructure.decomposition.models import (
    CandidateOutputModel,
    DecompositionApprovalModel,
    DecompositionArtifactModel,
    DecompositionReviewModel,
    DecompositionRunModel,
    RepositoryIndexModel,
    RepositorySnapshotModel,
    ValidationFindingModel,
    WorkPackageDependencyModel,
    WorkPackageModel,
)
from ai_enterprise.infrastructure.repository_index.git_snapshot import GitSnapshotService
from ai_enterprise.infrastructure.repository_index.index_builder import RepositoryIndexBuilder


class DecompositionError(RuntimeError):
    def __init__(self, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.status_code = status_code


class DecompositionService:
    def __init__(self, session: AsyncSession, *, snapshots_root: Path | None = None) -> None:
        self.session = session
        self.snapshots_root = snapshots_root or Path("./runtime-data/decomposition-snapshots")
        self.policy = DecompositionPolicy()

    async def start(
        self,
        project_id: uuid.UUID,
        architecture_id: uuid.UUID,
        repository_uri: str,
        commit: str,
        actor: Actor,
    ) -> DecompositionRunModel:
        project = await self.session.get(ProjectModel, project_id)
        architecture = await self.session.get(ArchitectureArtifactModel, architecture_id)
        if project is None or architecture is None:
            raise DecompositionError("Project or architecture artifact not found", 404)
        approval = await self.session.scalar(
            select(ArchitectureApprovalModel).where(
                ArchitectureApprovalModel.architecture_artifact_id == architecture.id,
                ArchitectureApprovalModel.approved.is_(True),
                ArchitectureApprovalModel.approved_checksum == architecture.checksum,
            )
        )
        requirement_approval = await self.session.scalar(
            select(ApprovalModel).where(
                ApprovalModel.project_id == project_id,
                ApprovalModel.artifact_id == architecture.requirements_artifact_id,
                ApprovalModel.decision == "approved",
            )
        )
        requirement = await self.session.get(ArtifactModel, architecture.requirements_artifact_id)
        if (
            approval is None
            or architecture.status != "approved"
            or requirement_approval is None
            or requirement is None
        ):
            raise DecompositionError(
                "Exact approved requirements and architecture inputs are required"
            )
        if architecture.project_id != project_id or requirement.project_id != project_id:
            raise DecompositionError("Input artifacts must belong to the same project")
        snapshot_value = GitSnapshotService(self.snapshots_root).create_readonly_snapshot(
            repository_uri=repository_uri, base_commit_sha=commit
        )
        index_value = RepositoryIndexBuilder().build(snapshot_value)
        snapshot = await self.session.scalar(
            select(RepositorySnapshotModel).where(
                RepositorySnapshotModel.project_id == project_id,
                RepositorySnapshotModel.repository_uri == repository_uri,
                RepositorySnapshotModel.base_commit_sha == commit,
            )
        )
        if snapshot is None:
            snapshot = RepositorySnapshotModel(
                id=uuid.uuid4(),
                project_id=project_id,
                repository_uri=repository_uri,
                base_commit_sha=commit,
                tree_hash=snapshot_value.tree_hash,
                content_hash=snapshot_value.content_hash,
            )
            self.session.add(snapshot)
            await self.session.flush()
        elif (
            snapshot.tree_hash != snapshot_value.tree_hash
            or snapshot.content_hash != snapshot_value.content_hash
        ):
            raise DecompositionError("Existing repository snapshot identity differs")
        index = await self.session.scalar(
            select(RepositoryIndexModel).where(
                RepositoryIndexModel.snapshot_id == snapshot.id,
                RepositoryIndexModel.index_hash == index_value.index_hash,
            )
        )
        if index is None:
            index = RepositoryIndexModel(
                id=uuid.uuid4(),
                snapshot_id=snapshot.id,
                schema_version=index_value.schema_version,
                index_hash=index_value.index_hash,
                index_document=index_value.document(include_hash=False),
            )
            self.session.add(index)
            await self.session.flush()
        run = DecompositionRunModel(
            id=uuid.uuid4(),
            project_id=project_id,
            requirements_artifact_id=requirement.id,
            architecture_artifact_id=architecture.id,
            repository_snapshot_id=snapshot.id,
            repository_index_id=index.id,
            status=DecompositionState.PENDING,
            policy_version=self.policy.version,
            crew_definition_version="decomposition-crew-v1",
            requested_by=actor.subject,
            correlation_id=uuid.uuid4(),
        )
        self.session.add(run)
        self.session.add(
            JobModel(
                id=uuid.uuid4(),
                project_id=project_id,
                run_id=None,
                job_type=JobType.RUN_WORK_PACKAGE_DECOMPOSITION,
                status=JobStatus.QUEUED,
                payload={"decomposition_run_id": str(run.id)},
                priority=80,
                max_attempts=3,
            )
        )
        self._audit(
            project_id,
            "WorkPackageDecompositionRequested",
            actor.subject,
            {
                "run_id": str(run.id),
                "architecture_hash": architecture.checksum,
                "tree_hash": snapshot.tree_hash,
            },
        )
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def execute(
        self, run_id: uuid.UUID, provider: DecompositionCrewProvider
    ) -> DecompositionArtifactModel:
        run = await self.session.scalar(
            select(DecompositionRunModel)
            .where(DecompositionRunModel.id == run_id)
            .with_for_update()
        )
        if run is None:
            raise DecompositionError("Decomposition run not found", 404)
        architecture = await self.session.get(
            ArchitectureArtifactModel, run.architecture_artifact_id
        )
        requirement = await self.session.get(ArtifactModel, run.requirements_artifact_id)
        snapshot = await self.session.get(RepositorySnapshotModel, run.repository_snapshot_id)
        index = await self.session.get(RepositoryIndexModel, run.repository_index_id)
        if not all((architecture, requirement, snapshot, index)):
            raise DecompositionError("Bound decomposition inputs are missing")
        assert (
            architecture is not None
            and requirement is not None
            and snapshot is not None
            and index is not None
        )
        try:
            for state in (
                DecompositionState.REPOSITORY_INDEXING,
                DecompositionState.REPOSITORY_INDEXED,
                DecompositionState.CREW_RUNNING,
            ):
                self._transition(run, state)
            run.started_at = datetime.now(UTC)
            requirements_document = self._json_document(requirement.content)
            candidate = await provider.decompose(
                DecompositionCrewContext(
                    index.index_document,
                    requirements_document,
                    architecture.structured_content,
                    run.revision_reason,
                )
            )
            attempt = (
                int(
                    await self.session.scalar(
                        select(func.count())
                        .select_from(CandidateOutputModel)
                        .where(CandidateOutputModel.decomposition_run_id == run.id)
                    )
                    or 0
                )
                + 1
            )
            raw = candidate.model_dump(mode="json")
            self.session.add(
                CandidateOutputModel(
                    id=uuid.uuid4(),
                    decomposition_run_id=run.id,
                    attempt_number=attempt,
                    raw_output=raw,
                    raw_output_hash=canonical_hash(raw),
                    model_metadata={"provider": provider.name, "model": provider.model_name},
                )
            )
            for state in (DecompositionState.CREW_COMPLETED, DecompositionState.NORMALIZING):
                self._transition(run, state)
            normalized = CandidateNormalizer().normalize(
                candidate,
                project_id=str(run.project_id),
                architecture_hash=architecture.checksum,
                repository_tree_hash=snapshot.tree_hash,
                policy=self.policy,
            )
            self._transition(run, DecompositionState.GRAPH_BUILDING)
            graph = DeterministicGraphBuilder().build(normalized)
            self._transition(run, DecompositionState.VALIDATING)
            req_ids = self._requirement_ids(requirements_document)
            arc_ids = self._architecture_ids(architecture.structured_content)
            context = ValidationContext(
                candidate=candidate,
                normalized=normalized,
                graph=graph,
                policy=self.policy,
                project_id=str(run.project_id),
                architecture_hash=architecture.checksum,
                repository_tree_hash=snapshot.tree_hash,
                approved_requirements=frozenset(req_ids),
                architecture_elements=frozenset(arc_ids),
                implementable_requirements=frozenset(req_ids),
                implementable_architecture_elements=frozenset(arc_ids),
                repository_paths=frozenset(
                    str(x["path"]) for x in index.index_document.get("files", [])
                ),
                module_roots=frozenset(
                    str(x["root_path"]) for x in index.index_document.get("modules", [])
                ),
                protected_paths=frozenset(
                    str(x) for x in index.index_document.get("protected_paths", [])
                ),
                requested_commit=snapshot.base_commit_sha,
                snapshot_commit=snapshot.base_commit_sha,
                snapshot_tree_hash=snapshot.tree_hash,
                index_snapshot_matches=index.snapshot_id == snapshot.id,
                repository_index=index.index_document,
                repository_index_hash=index.index_hash,
            )
            findings = DecompositionValidationService().validate(context)
            validation_status = (
                "invalid" if any(x.severity is FindingSeverity.ERROR for x in findings) else "valid"
            )
            document = {
                "schema_version": 1,
                "project_id": str(run.project_id),
                "requirements_artifact": {
                    "id": str(requirement.id),
                    "hash": requirement.content_hash,
                },
                "architecture_artifact": {
                    "id": str(architecture.id),
                    "hash": architecture.checksum,
                },
                "repository": {
                    "snapshot_id": str(snapshot.id),
                    "base_commit_sha": snapshot.base_commit_sha,
                    "tree_hash": snapshot.tree_hash,
                    "index_hash": index.index_hash,
                },
                "policy": {"version": self.policy.version},
                "packages": [asdict(x) for x in normalized.packages],
                "graph": asdict(graph),
                "coverage": {
                    "requirements": {
                        key: sorted(p.key for p in normalized.packages if key in p.requirement_refs)
                        for key in sorted(req_ids)
                    },
                    "architecture_elements": {
                        key: sorted(
                            p.key for p in normalized.packages if key in p.architecture_refs
                        )
                        for key in sorted(arc_ids)
                    },
                },
                "validation": {
                    "status": validation_status,
                    "findings": [asdict(x) for x in findings],
                },
            }
            artifact_hash = canonical_hash(document)
            artifact = DecompositionArtifactModel(
                id=uuid.uuid4(),
                decomposition_run_id=run.id,
                project_id=run.project_id,
                schema_version=1,
                artifact_document=document,
                artifact_hash=artifact_hash,
                graph_hash=graph.graph_hash,
                validation_status=validation_status,
                status="validation_failed" if validation_status == "invalid" else "awaiting_review",
            )
            self.session.add(artifact)
            await self.session.flush()
            self.session.add_all(
                [
                    ValidationFindingModel(
                        id=uuid.uuid4(),
                        decomposition_artifact_id=artifact.id,
                        validator_code=x.validator_code,
                        severity=x.severity,
                        package_key=x.package_key,
                        path=x.path,
                        message=x.message,
                        evidence=x.evidence or {},
                    )
                    for x in findings
                ]
            )
            self._transition(
                run,
                DecompositionState.VALIDATION_FAILED
                if artifact.validation_status == "invalid"
                else DecompositionState.AWAITING_REVIEW,
            )
            run.completed_at = datetime.now(UTC)
            self._audit(
                run.project_id,
                "WorkPackageDecompositionValidated",
                "system",
                {
                    "run_id": str(run.id),
                    "artifact_id": str(artifact.id),
                    "artifact_hash": artifact_hash,
                    "graph_hash": graph.graph_hash,
                    "status": artifact.validation_status,
                },
            )
            await self.session.commit()
            return artifact
        except Exception as exc:
            await self.session.rollback()
            failed = await self.session.get(DecompositionRunModel, run_id)
            if failed is not None and DecompositionState.FAILED in __import__(
                "ai_enterprise.domain.decomposition.core", fromlist=["TRANSITIONS"]
            ).TRANSITIONS.get(DecompositionState(failed.status), set()):
                failed.status = DecompositionState.FAILED
                failed.failure_code = type(exc).__name__[:100]
                failed.failure_detail = {"message": str(exc)[:2000]}
                await self.session.commit()
            raise

    async def review(
        self,
        artifact_id: uuid.UUID,
        decision: str,
        artifact_hash: str,
        comments: str | None,
        actor: Actor,
    ) -> DecompositionReviewModel:
        if actor.actor_type != "human":
            raise DecompositionError("Decomposition review requires a human actor", 403)
        artifact = await self.session.scalar(
            select(DecompositionArtifactModel)
            .where(DecompositionArtifactModel.id == artifact_id)
            .with_for_update()
        )
        if artifact is None:
            raise DecompositionError("Decomposition artifact not found", 404)
        if artifact.artifact_hash != artifact_hash:
            raise DecompositionError("Reviewed artifact hash differs")
        if artifact.status != "awaiting_review" or artifact.validation_status != "valid":
            raise DecompositionError("Only a valid awaiting-review artifact may be reviewed")
        if decision not in {"approved", "changes_requested", "rejected"}:
            raise DecompositionError("Unsupported review decision", 422)
        review = DecompositionReviewModel(
            id=uuid.uuid4(),
            decomposition_artifact_id=artifact.id,
            reviewer_id=actor.subject,
            decision=decision,
            artifact_hash=artifact_hash,
            comments=comments,
        )
        self.session.add(review)
        artifact.status = decision
        run = await self.session.get(DecompositionRunModel, artifact.decomposition_run_id)
        assert run is not None
        self._transition(run, DecompositionState(decision))
        if decision == "approved":
            self.session.add(
                DecompositionApprovalModel(
                    id=uuid.uuid4(),
                    decomposition_artifact_id=artifact.id,
                    review_id=review.id,
                    artifact_hash=artifact_hash,
                    approved_by=actor.subject,
                )
            )
            await self._materialize(artifact)
        self._audit(
            run.project_id,
            f"WorkPackageDecomposition{decision.title().replace('_', '')}",
            actor.subject,
            {"artifact_id": str(artifact.id), "artifact_hash": artifact_hash},
        )
        await self.session.commit()
        return review

    async def revision(
        self, artifact_id: uuid.UUID, artifact_hash: str, comments: str, actor: Actor
    ) -> DecompositionRunModel:
        review = await self.review(artifact_id, "changes_requested", artifact_hash, comments, actor)
        artifact = await self.session.get(DecompositionArtifactModel, artifact_id)
        assert artifact is not None
        parent = await self.session.get(DecompositionRunModel, artifact.decomposition_run_id)
        assert parent is not None
        self._transition(parent, DecompositionState.SUPERSEDED)
        artifact.status = "superseded"
        run = DecompositionRunModel(
            id=uuid.uuid4(),
            project_id=parent.project_id,
            requirements_artifact_id=parent.requirements_artifact_id,
            architecture_artifact_id=parent.architecture_artifact_id,
            repository_snapshot_id=parent.repository_snapshot_id,
            repository_index_id=parent.repository_index_id,
            status=DecompositionState.PENDING,
            policy_version=parent.policy_version,
            crew_definition_version=parent.crew_definition_version,
            requested_by=actor.subject,
            correlation_id=parent.correlation_id,
            parent_decomposition_run_id=parent.id,
            parent_artifact_id=artifact.id,
            revision_reason=comments,
            review_id=review.id,
        )
        self.session.add(run)
        self.session.add(
            JobModel(
                id=uuid.uuid4(),
                project_id=run.project_id,
                run_id=None,
                job_type=JobType.RUN_WORK_PACKAGE_DECOMPOSITION,
                status=JobStatus.QUEUED,
                payload={"decomposition_run_id": str(run.id)},
                priority=80,
                max_attempts=3,
            )
        )
        await self.session.commit()
        return run

    async def _materialize(self, artifact: DecompositionArtifactModel) -> None:
        document = artifact.artifact_document
        packages = {item["key"]: item for item in document["packages"]}
        ids: dict[str, uuid.UUID] = {}
        order = document["graph"]["topological_order"]
        predecessors = {edge[1] for edge in document["graph"]["edges"]}
        for sequence, key in enumerate(order, 1):
            item = packages[key]
            package_id = uuid.UUID(item["id"])
            ids[key] = package_id
            self.session.add(
                WorkPackageModel(
                    id=package_id,
                    project_id=artifact.project_id,
                    decomposition_artifact_id=artifact.id,
                    package_key=key,
                    sequence_number=sequence,
                    title=item["title"],
                    objective=item["objective"],
                    status="blocked" if key in predecessors else "ready",
                    package_document=item,
                    package_hash=item["package_hash"],
                )
            )
        await self.session.flush()
        for predecessor, successor, dependency_type, reason in document["graph"]["edges"]:
            self.session.add(
                WorkPackageDependencyModel(
                    decomposition_artifact_id=artifact.id,
                    predecessor_package_id=ids[predecessor],
                    successor_package_id=ids[successor],
                    dependency_type=dependency_type,
                    reason=reason,
                )
            )

    @staticmethod
    def _json_document(content: str) -> dict[str, Any]:
        try:
            value = json.loads(content)
            return value if isinstance(value, dict) else {"content": content}
        except json.JSONDecodeError:
            return {"content": content}

    @staticmethod
    def _requirement_ids(document: dict[str, Any]) -> set[str]:
        return {
            str(item["id"])
            for name in ("functional_requirements", "non_functional_requirements")
            for item in document.get(name, [])
            if isinstance(item, dict) and "id" in item
        }

    @staticmethod
    def _architecture_ids(document: dict[str, Any]) -> set[str]:
        return {
            str(item["id"])
            for name in ("functional_domains", "modules", "interfaces", "data_entities")
            for item in document.get(name, [])
            if isinstance(item, dict) and "id" in item
        }

    @staticmethod
    def _transition(run: DecompositionRunModel, state: DecompositionState) -> None:
        assert_transition(DecompositionState(run.status), state)
        run.status = state

    def _audit(
        self, project_id: uuid.UUID, event: str, actor: str, payload: dict[str, Any]
    ) -> None:
        self.session.add(
            AuditEventModel(
                id=uuid.uuid4(),
                project_id=project_id,
                event_type=event,
                actor_type="human" if actor != "system" else "system",
                actor_id=actor,
                payload=payload,
            )
        )
