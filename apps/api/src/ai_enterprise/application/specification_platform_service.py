from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.audit.writer import AuditWriter
from ai_enterprise.application.organization_persistence_service import canonical_hash
from ai_enterprise.domain.specification.kernel import (
    Provenance,
    SpecificationArtifact,
    SpecificationIdentity,
    semantic_version,
)
from ai_enterprise.infrastructure.specification.models import (
    DriftDecisionModel,
    DriftDetectionRunModel,
    DriftFindingModel,
    EngineeringEvidenceEdgeModel,
    EngineeringEvidenceNodeModel,
    EngineeringSpecificationModel,
    GeneratedEngineeringArtifactModel,
    SpecificationApprovalModel,
    SpecificationGenerationRunModel,
    SpecificationValidationRunModel,
)
from ai_enterprise.observability import increment_metric

DRIFT_CATEGORIES = {
    "api",
    "database",
    "configuration",
    "event",
    "infrastructure",
    "security_policy",
    "dependency",
    "documentation",
}
MAX_SPECIFICATION_BYTES = 1_048_576


class SpecificationPlatformError(ValueError):
    def __init__(self, detail: str, status_code: int = 409) -> None:
        super().__init__(detail)
        self.status_code = status_code


class DeterministicSpecificationGenerator(Protocol):
    def generate(
        self, specification: dict[str, Any], parameters: dict[str, Any]
    ) -> tuple[dict[str, str], ...]: ...


class SpecificationPlatformService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _audit(
        self, event: str, actor: str, project_id: uuid.UUID, payload: dict[str, Any]
    ) -> None:
        await AuditWriter(self.session).append_project_event(
            project_id=project_id,
            event_type=event,
            actor_type="specification-platform",
            actor_id=actor,
            payload=payload,
        )

    async def create_specification(
        self,
        *,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        specification_key: str,
        specification_type: str,
        version: str,
        document: dict[str, Any],
        requirements_hash: str,
        architecture_hash: str,
        work_package_hash: str,
        created_by: str,
        parent_specification_id: uuid.UUID | None = None,
    ) -> EngineeringSpecificationModel:
        artifact = SpecificationArtifact.build(
            identity=SpecificationIdentity(
                specification_key=specification_key,
                version=version,
                provenance=Provenance(
                    requirements_hash=requirements_hash,
                    architecture_hash=architecture_hash,
                    package_hash=work_package_hash,
                ),
            ),
            kind=specification_type,
            document=document,
        )
        if len(json.dumps(document, sort_keys=True).encode()) > MAX_SPECIFICATION_BYTES:
            raise SpecificationPlatformError("SPEC-004 SPECIFICATION-TOO-LARGE", 413)
        existing = await self.session.scalar(
            select(EngineeringSpecificationModel).where(
                EngineeringSpecificationModel.specification_hash == artifact.spec_hash
            )
        )
        if existing is not None:
            return existing
        if parent_specification_id is not None:
            parent = await self.session.get(EngineeringSpecificationModel, parent_specification_id)
            if parent is None or parent.project_id != project_id:
                raise SpecificationPlatformError("SPEC-001 INVALID-PARENT", 422)
            if (
                parent.organization_id != organization_id
                or parent.specification_key != specification_key
                or parent.specification_type != specification_type
                or semantic_version(version) <= semantic_version(parent.version)
            ):
                raise SpecificationPlatformError("SPEC-005 INVALID-REVISION-LINEAGE", 422)
        row = EngineeringSpecificationModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            project_id=project_id,
            specification_key=specification_key,
            specification_type=specification_type,
            version=version,
            specification_document=artifact.document,
            specification_hash=artifact.spec_hash,
            requirements_hash=requirements_hash,
            architecture_hash=architecture_hash,
            work_package_hash=work_package_hash,
            parent_specification_id=parent_specification_id,
            created_by=created_by,
            created_at=datetime.now(UTC),
        )
        self.session.add(row)
        await self._audit(
            "EngineeringSpecificationCreated",
            created_by,
            project_id,
            {"specification_id": str(row.id), "specification_hash": row.specification_hash},
        )
        increment_metric(f"specification.created.{specification_type}")
        await self.session.commit()
        return row

    async def approve(
        self,
        specification: EngineeringSpecificationModel,
        *,
        specification_hash: str,
        decision: str,
        decided_by: str,
        rationale: str,
    ) -> SpecificationApprovalModel:
        if specification.specification_hash != specification_hash:
            raise SpecificationPlatformError("SPEC-002 HASH-MISMATCH")
        if decision not in {"approve", "reject"} or not rationale.strip():
            raise SpecificationPlatformError("SPEC-003 INVALID-DECISION", 422)
        if specification.created_by == decided_by:
            raise SpecificationPlatformError("SPEC-006 INDEPENDENT-APPROVER-REQUIRED", 403)
        existing = await self.session.scalar(
            select(SpecificationApprovalModel).where(
                SpecificationApprovalModel.specification_id == specification.id,
                SpecificationApprovalModel.specification_hash == specification_hash,
                SpecificationApprovalModel.decision == decision,
            )
        )
        if existing is not None:
            return existing
        row = SpecificationApprovalModel(
            id=uuid.uuid4(),
            specification_id=specification.id,
            specification_hash=specification_hash,
            decision=decision,
            decided_by=decided_by,
            rationale=rationale,
            decided_at=datetime.now(UTC),
        )
        self.session.add(row)
        await self._audit(
            "EngineeringSpecificationDecision",
            decided_by,
            specification.project_id,
            {"specification_id": str(specification.id), "decision": decision},
        )
        await self.session.commit()
        return row

    async def validate(
        self,
        specification: EngineeringSpecificationModel,
        *,
        validator_version: str,
        findings: list[dict[str, Any]],
        actor: str,
    ) -> SpecificationValidationRunModel:
        document = {
            "specification_hash": specification.specification_hash,
            "validator_version": validator_version,
            "findings": findings,
        }
        evidence_hash = canonical_hash(document)
        existing = await self.session.scalar(
            select(SpecificationValidationRunModel).where(
                SpecificationValidationRunModel.evidence_hash == evidence_hash
            )
        )
        if existing is not None:
            return existing
        row = SpecificationValidationRunModel(
            id=uuid.uuid4(),
            specification_id=specification.id,
            specification_hash=specification.specification_hash,
            validator_version=validator_version,
            status="passed" if not findings else "failed",
            findings=findings,
            evidence_hash=evidence_hash,
            validated_at=datetime.now(UTC),
        )
        self.session.add(row)
        await self._audit(
            "EngineeringSpecificationValidated",
            actor,
            specification.project_id,
            {"validation_id": str(row.id), "status": row.status, "evidence_hash": evidence_hash},
        )
        increment_metric(f"specification.validation.{row.status}")
        await self.session.commit()
        return row

    async def request_generation(
        self,
        specification: EngineeringSpecificationModel,
        *,
        generator_key: str,
        generator_version: str,
        parameters: dict[str, Any],
        actor: str,
    ) -> SpecificationGenerationRunModel:
        approval = await self.session.scalar(
            select(SpecificationApprovalModel.id).where(
                SpecificationApprovalModel.specification_id == specification.id,
                SpecificationApprovalModel.specification_hash == specification.specification_hash,
                SpecificationApprovalModel.decision == "approve",
            )
        )
        validation = await self.session.scalar(
            select(SpecificationValidationRunModel.id).where(
                SpecificationValidationRunModel.specification_id == specification.id,
                SpecificationValidationRunModel.specification_hash
                == specification.specification_hash,
                SpecificationValidationRunModel.status == "passed",
            )
        )
        if approval is None or validation is None:
            raise SpecificationPlatformError("SPEC-010 APPROVAL-AND-VALIDATION-REQUIRED", 403)
        request_document = {
            "specification_hash": specification.specification_hash,
            "generator_key": generator_key,
            "generator_version": generator_version,
            "parameters": parameters,
        }
        input_hash = canonical_hash(request_document)
        existing = await self.session.scalar(
            select(SpecificationGenerationRunModel).where(
                SpecificationGenerationRunModel.input_hash == input_hash,
                SpecificationGenerationRunModel.status.in_(["pending", "running", "completed"]),
            )
        )
        if existing is not None:
            return existing
        row = SpecificationGenerationRunModel(
            id=uuid.uuid4(),
            specification_id=specification.id,
            specification_hash=specification.specification_hash,
            generator_key=generator_key,
            generator_version=generator_version,
            input_hash=input_hash,
            status="pending",
            request_document=request_document,
            output_manifest=None,
            output_manifest_hash=None,
            failure_document=None,
            requested_by=actor,
            started_at=None,
            completed_at=None,
        )
        self.session.add(row)
        await self._audit(
            "SpecificationGenerationRequested",
            actor,
            specification.project_id,
            {"generation_run_id": str(row.id), "input_hash": input_hash},
        )
        await self.session.commit()
        return row

    async def add_evidence_node(
        self,
        *,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        node_type: str,
        reference_id: uuid.UUID,
        reference_hash: str,
        classification: str,
        document: dict[str, Any],
        actor: str,
    ) -> EngineeringEvidenceNodeModel:
        bound = {
            "node_type": node_type,
            "reference_id": str(reference_id),
            "reference_hash": reference_hash,
            "document": document,
        }
        node_hash = canonical_hash(bound)
        existing = await self.session.scalar(
            select(EngineeringEvidenceNodeModel).where(
                EngineeringEvidenceNodeModel.node_hash == node_hash
            )
        )
        if existing is not None:
            return existing
        row = EngineeringEvidenceNodeModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            project_id=project_id,
            node_type=node_type,
            reference_id=reference_id,
            reference_hash=reference_hash,
            classification=classification,
            node_document=document,
            node_hash=node_hash,
            recorded_at=datetime.now(UTC),
        )
        self.session.add(row)
        await self._audit(
            "EngineeringEvidenceNodeRecorded",
            actor,
            project_id,
            {"node_id": str(row.id), "node_hash": node_hash},
        )
        increment_metric(f"engineering_evidence.node.{node_type}")
        await self.session.commit()
        return row

    async def add_evidence_edge(
        self,
        source: EngineeringEvidenceNodeModel,
        target: EngineeringEvidenceNodeModel,
        *,
        relationship: str,
        document: dict[str, Any],
        actor: str,
    ) -> EngineeringEvidenceEdgeModel:
        if (
            source.organization_id != target.organization_id
            or source.project_id != target.project_id
        ):
            raise SpecificationPlatformError("SPEC-020 CROSS-SCOPE-EDGE-DENIED", 403)
        if source.id == target.id:
            raise SpecificationPlatformError("SPEC-021 SELF-EDGE-DENIED", 422)
        project_nodes = list(
            (
                await self.session.scalars(
                    select(EngineeringEvidenceNodeModel.id).where(
                        EngineeringEvidenceNodeModel.organization_id == source.organization_id,
                        EngineeringEvidenceNodeModel.project_id == source.project_id,
                    )
                )
            ).all()
        )
        edges = list(
            (
                await self.session.scalars(
                    select(EngineeringEvidenceEdgeModel).where(
                        EngineeringEvidenceEdgeModel.source_node_id.in_(project_nodes)
                    )
                )
            ).all()
        )
        adjacency: dict[uuid.UUID, set[uuid.UUID]] = {}
        for edge in edges:
            adjacency.setdefault(edge.source_node_id, set()).add(edge.target_node_id)
        pending, visited = [target.id], set()
        while pending:
            current = pending.pop()
            if current == source.id:
                raise SpecificationPlatformError("SPEC-022 EVIDENCE-CYCLE-DENIED", 422)
            if current not in visited:
                visited.add(current)
                pending.extend(adjacency.get(current, ()))
        bound = {
            "source_hash": source.node_hash,
            "target_hash": target.node_hash,
            "relationship": relationship,
            "document": document,
        }
        edge_hash = canonical_hash(bound)
        existing = await self.session.scalar(
            select(EngineeringEvidenceEdgeModel).where(
                EngineeringEvidenceEdgeModel.edge_hash == edge_hash
            )
        )
        if existing is not None:
            return existing
        row = EngineeringEvidenceEdgeModel(
            id=uuid.uuid4(),
            source_node_id=source.id,
            target_node_id=target.id,
            relationship=relationship,
            edge_document=document,
            edge_hash=edge_hash,
            recorded_at=datetime.now(UTC),
        )
        self.session.add(row)
        await self._audit(
            "EngineeringEvidenceEdgeRecorded",
            actor,
            source.project_id,
            {"edge_id": str(row.id), "edge_hash": edge_hash},
        )
        await self.session.commit()
        return row

    async def handle(
        self, run_id: uuid.UUID, generator: DeterministicSpecificationGenerator
    ) -> SpecificationGenerationRunModel:
        run = await self.session.scalar(
            select(SpecificationGenerationRunModel)
            .where(SpecificationGenerationRunModel.id == run_id)
            .with_for_update()
        )
        if run is None:
            raise SpecificationPlatformError("SPEC-011 GENERATION-RUN-NOT-FOUND", 404)
        if run.status == "completed":
            return run
        if run.status != "pending":
            raise SpecificationPlatformError("SPEC-012 GENERATION-RUN-NOT-PENDING")
        specification = await self.session.get(EngineeringSpecificationModel, run.specification_id)
        if specification is None or specification.specification_hash != run.specification_hash:
            raise SpecificationPlatformError("SPEC-013 SPECIFICATION-HASH-CHANGED")
        run.status = "running"
        run.started_at = datetime.now(UTC)
        await self.session.flush()
        outputs = generator.generate(
            specification.specification_document, run.request_document.get("parameters", {})
        )
        artifacts = []
        for output in outputs:
            path = output["repository_path"]
            if path.startswith("/") or ".." in path.split("/"):
                raise SpecificationPlatformError("SPEC-014 UNSAFE-GENERATED-PATH", 422)
            content_hash = output["content_hash"]
            provenance = canonical_hash(
                {
                    "specification_hash": run.specification_hash,
                    "generator_version": run.generator_version,
                    "artifact_type": output["artifact_type"],
                    "repository_path": path,
                    "content_hash": content_hash,
                }
            )
            artifact = GeneratedEngineeringArtifactModel(
                id=uuid.uuid4(),
                generation_run_id=run.id,
                artifact_type=output["artifact_type"],
                repository_path=path,
                content_hash=content_hash,
                specification_hash=run.specification_hash,
                generator_version=run.generator_version,
                provenance_hash=provenance,
                created_at=datetime.now(UTC),
            )
            self.session.add(artifact)
            artifacts.append(artifact)
        manifest = {
            "generation_run_id": str(run.id),
            "specification_hash": run.specification_hash,
            "generator_version": run.generator_version,
            "artifacts": [
                {
                    "id": str(row.id),
                    "path": row.repository_path,
                    "content_hash": row.content_hash,
                    "provenance_hash": row.provenance_hash,
                }
                for row in artifacts
            ],
        }
        run.output_manifest = manifest
        run.output_manifest_hash = canonical_hash(manifest)
        run.status = "completed"
        run.completed_at = datetime.now(UTC)
        await AuditWriter(self.session).append_project_event(
            project_id=specification.project_id,
            event_type="SpecificationGenerationCompleted",
            actor_type="specification-worker",
            actor_id=run.generator_key,
            payload={
                "generation_run_id": str(run.id),
                "output_manifest_hash": run.output_manifest_hash,
                "specification_hash": run.specification_hash,
            },
        )
        increment_metric(f"specification.generation.{run.generator_key}.completed")
        await self.session.commit()
        return run

    async def detect_drift(
        self,
        specification: EngineeringSpecificationModel,
        *,
        repository_commit_hash: str,
        runtime_deployment_hash: str | None,
        detector_version: str,
        observations: list[dict[str, Any]],
        actor: str,
    ) -> tuple[DriftDetectionRunModel, list[DriftFindingModel]]:
        approved = await self.session.scalar(
            select(SpecificationApprovalModel.id).where(
                SpecificationApprovalModel.specification_id == specification.id,
                SpecificationApprovalModel.specification_hash == specification.specification_hash,
                SpecificationApprovalModel.decision == "approve",
            )
        )
        if approved is None:
            raise SpecificationPlatformError("SPEC-030 APPROVED-SPECIFICATION-REQUIRED", 403)
        manifest = {
            "specification_hash": specification.specification_hash,
            "repository_commit_hash": repository_commit_hash,
            "runtime_deployment_hash": runtime_deployment_hash,
            "detector_version": detector_version,
            "observations": observations,
        }
        comparison_hash = canonical_hash(manifest)
        existing = await self.session.scalar(
            select(DriftDetectionRunModel).where(
                DriftDetectionRunModel.comparison_hash == comparison_hash
            )
        )
        if existing is not None:
            rows = list(
                (
                    await self.session.scalars(
                        select(DriftFindingModel).where(
                            DriftFindingModel.drift_run_id == existing.id
                        )
                    )
                ).all()
            )
            return existing, rows
        now = datetime.now(UTC)
        run = DriftDetectionRunModel(
            id=uuid.uuid4(),
            organization_id=specification.organization_id,
            project_id=specification.project_id,
            specification_id=specification.id,
            specification_hash=specification.specification_hash,
            repository_commit_hash=repository_commit_hash,
            runtime_deployment_hash=runtime_deployment_hash,
            detector_version=detector_version,
            status="completed",
            comparison_manifest=manifest,
            comparison_hash=comparison_hash,
            requested_by=actor,
            started_at=now,
            completed_at=now,
        )
        self.session.add(run)
        findings = []
        for observation in observations:
            category = observation.get("category")
            if category not in DRIFT_CATEGORIES:
                raise SpecificationPlatformError("SPEC-031 INVALID-DRIFT-CATEGORY", 422)
            expected, actual = observation.get("expected_hash"), observation.get("actual_hash")
            if expected == actual:
                continue
            finding_document = {**observation, "comparison_hash": comparison_hash}
            row = DriftFindingModel(
                id=uuid.uuid4(),
                drift_run_id=run.id,
                category=category,
                severity=observation.get("severity", "high"),
                expected_hash=expected,
                actual_hash=actual,
                evidence_document=finding_document,
                finding_hash=canonical_hash(finding_document),
                promotion_blocking=observation.get("promotion_blocking", True),
                detected_at=now,
            )
            self.session.add(row)
            findings.append(row)
        await self._audit(
            "EngineeringDriftDetected",
            actor,
            specification.project_id,
            {
                "drift_run_id": str(run.id),
                "finding_count": len(findings),
                "promotion_blocked": any(row.promotion_blocking for row in findings),
            },
        )
        increment_metric("engineering_drift.runs")
        increment_metric("engineering_drift.findings", len(findings))
        await self.session.commit()
        return run, findings

    async def decide_drift(
        self,
        finding: DriftFindingModel,
        *,
        finding_hash: str,
        decision: str,
        decided_by: str,
        rationale: str,
        expires_at: datetime | None,
    ) -> DriftDecisionModel:
        if finding.finding_hash != finding_hash:
            raise SpecificationPlatformError("SPEC-032 FINDING-HASH-MISMATCH")
        if decision not in {"reconciled", "approved_exception"} or not rationale.strip():
            raise SpecificationPlatformError("SPEC-033 INVALID-DRIFT-DECISION", 422)
        if decision == "approved_exception" and expires_at is None:
            raise SpecificationPlatformError("SPEC-034 EXCEPTION-EXPIRY-REQUIRED", 422)
        if (
            decision == "approved_exception"
            and expires_at is not None
            and expires_at <= datetime.now(UTC)
        ):
            raise SpecificationPlatformError("SPEC-036 EXCEPTION-MUST-EXPIRE-IN-FUTURE", 422)
        run = await self.session.get(DriftDetectionRunModel, finding.drift_run_id)
        if run is None:
            raise SpecificationPlatformError("SPEC-035 DRIFT-RUN-MISSING")
        existing = await self.session.scalar(
            select(DriftDecisionModel).where(
                DriftDecisionModel.finding_id == finding.id,
                DriftDecisionModel.finding_hash == finding_hash,
                DriftDecisionModel.decision == decision,
            )
        )
        if existing is not None:
            return existing
        row = DriftDecisionModel(
            id=uuid.uuid4(),
            finding_id=finding.id,
            finding_hash=finding_hash,
            decision=decision,
            decided_by=decided_by,
            rationale=rationale,
            expires_at=expires_at,
            decided_at=datetime.now(UTC),
        )
        self.session.add(row)
        await self._audit(
            "EngineeringDriftDecision",
            decided_by,
            run.project_id,
            {"finding_id": str(finding.id), "decision": decision},
        )
        await self.session.commit()
        return row

    async def promotion_eligibility(
        self, *, organization_id: uuid.UUID, project_id: uuid.UUID, now: datetime
    ) -> tuple[bool, tuple[uuid.UUID, ...]]:
        runs = list(
            (
                await self.session.scalars(
                    select(DriftDetectionRunModel.id).where(
                        DriftDetectionRunModel.organization_id == organization_id,
                        DriftDetectionRunModel.project_id == project_id,
                        DriftDetectionRunModel.status == "completed",
                    )
                )
            ).all()
        )
        findings = list(
            (
                await self.session.scalars(
                    select(DriftFindingModel).where(
                        DriftFindingModel.drift_run_id.in_(runs),
                        DriftFindingModel.promotion_blocking.is_(True),
                    )
                )
            ).all()
        )
        unresolved: list[uuid.UUID] = []
        for finding in findings:
            decisions = list(
                (
                    await self.session.scalars(
                        select(DriftDecisionModel).where(
                            DriftDecisionModel.finding_id == finding.id,
                            DriftDecisionModel.finding_hash == finding.finding_hash,
                        )
                    )
                ).all()
            )
            resolved = any(row.decision == "reconciled" for row in decisions)
            exception = any(
                row.decision == "approved_exception"
                and row.expires_at is not None
                and row.expires_at > now
                for row in decisions
            )
            if not resolved and not exception:
                unresolved.append(finding.id)
        return not unresolved, tuple(unresolved)


class SpecificationGenerationWorker(SpecificationPlatformService):
    """Crash-retry-safe worker entry for deterministic generation runs."""
