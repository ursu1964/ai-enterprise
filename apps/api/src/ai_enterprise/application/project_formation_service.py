from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import yaml
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.api.project_formation_schemas import (
    ClientBlueprintArtifactResponse,
    ClientBlueprintClarificationAnswerRequest,
    ClientBlueprintImportRequest,
    ClientBlueprintResponse,
    ClientBlueprintReviewRequest,
    FormationArtifactResponse,
    FormationRequest,
    FormationResponse,
)
from ai_enterprise.application.audit.writer import AuditWriter
from ai_enterprise.config import get_settings
from ai_enterprise.domain.aeir import (
    AeirProjectModel,
    AeirProjectSnapshot,
    ApprovalStatus,
    TruthStatus,
    compile_aepm,
    compile_project_snapshot,
)
from ai_enterprise.domain.aepm import AepmManifest
from ai_enterprise.domain.aepm_interpretation import (
    InterpretationBatch,
    finalize_interpretation,
    interpretation_output_validator,
)
from ai_enterprise.domain.aepm_validation import (
    AepmValidationEngine,
    AepmValidationReport,
    ValidationSeverity,
)
from ai_enterprise.domain.artifact_compilers import (
    ArtifactBundle,
    ArtifactValidationReport,
    compile_artifact_bundle,
    validate_artifact_bundle,
)
from ai_enterprise.domain.clarification import (
    ClarificationAnswer,
    ClarificationReport,
    apply_answer_batch,
    build_answer_batch,
    generate_clarification_report,
)
from ai_enterprise.domain.enums import ApprovalDecision, ArtifactType, ProjectStatus
from ai_enterprise.domain.hashing import canonical_json, hash_json
from ai_enterprise.domain.traceability import (
    ArtifactTraceabilityManifest,
    compile_traceability_manifest,
    render_traceable_artifact_markdown,
)
from ai_enterprise.infrastructure.database.models import (
    ApprovalModel,
    ArtifactModel,
    ProjectModel,
)
from ai_enterprise.infrastructure.knowledge.aeir_repository import (
    AeirSnapshotWriteSet,
    AeirWriteSet,
    build_aeir_snapshot_write_set,
    build_aeir_write_set,
)
from ai_enterprise.infrastructure.knowledge.models import (
    AeirArtifactVersionModel,
    AeirChangeEventModel,
    AeirModelVersionModel,
    AeirProjectSnapshotModel,
)
from ai_enterprise.infrastructure.knowledge.object_store import (
    LocalContentAddressedObjectStore,
    StoredObject,
)


class ProjectFormationError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class FormationDocument:
    artifact_type: ArtifactType
    title: str
    body: dict[str, Any]
    human_summary: str


class ProjectFormationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_formation_pack(
        self, request: FormationRequest, *, actor_id: str
    ) -> FormationResponse:
        project = await self._session.get(ProjectModel, request.project_id)
        if project is None:
            raise ProjectFormationError("Project not found")
        missing = self._missing_information(request)
        status = "draft_needs_clarification" if missing else "ready_for_approval"
        generated_at = datetime.now(UTC)
        traceability = {
            "project_id": str(project.id),
            "manifest_hash": project.manifest_hash,
            "idea_hash": hash_json({"idea": request.idea}),
            "formation_status": status,
            "source": "deterministic-project-formation-v1",
        }
        documents = self._documents(project, request, missing, status, traceability)
        artifacts: list[ArtifactModel] = []
        responses: list[FormationArtifactResponse] = []
        for document in documents:
            body = {
                "schema_version": "1.0",
                "title": document.title,
                "artifact_type": document.artifact_type.value,
                "project_id": str(project.id),
                "generated_at": generated_at.isoformat(),
                "traceability": traceability,
                "content": document.body,
            }
            digest = hash_json(body)
            artifact = ArtifactModel(
                id=uuid.uuid4(),
                project_id=project.id,
                run_id=None,
                artifact_type=document.artifact_type,
                media_type="application/json",
                content=canonical_json(body),
                content_hash=digest,
            )
            artifacts.append(artifact)
            responses.append(
                FormationArtifactResponse(
                    artifact_id=artifact.id,
                    artifact_type=document.artifact_type.value,
                    content_hash=digest,
                    title=document.title,
                    human_summary=document.human_summary,
                )
            )
        self._session.add_all(artifacts)
        await AuditWriter(self._session).append_project_event(
            project_id=project.id,
            event_type="project_formation.pack_created",
            actor_type="human",
            actor_id=actor_id,
            payload={
                "status": status,
                "artifact_ids": [str(item.id) for item in artifacts],
                "missing_information": missing,
            },
        )
        await self._session.commit()
        return FormationResponse(
            project_id=project.id,
            status=status,
            correction_attempt=request.correction_attempt,
            missing_information=missing,
            next_action=self._next_action(missing),
            generated_at=generated_at,
            artifacts=responses,
            traceability=traceability,
        )

    async def import_client_blueprint_manifest(
        self, request: ClientBlueprintImportRequest, *, actor_id: str
    ) -> ClientBlueprintResponse:
        document = self._manifest_document(request)
        validation, manifest = self._validated_manifest(document)
        interpretation = self._interpretation_batch(
            document=document,
            interpretation_output=request.interpretation_output,
            ai_operation=request.ai_operation,
        )
        clarification = generate_clarification_report(validation, interpretation)
        project_id = uuid.uuid4()
        project = ProjectModel(
            id=project_id,
            name=manifest.project_intent.name,
            description=manifest.project_intent.summary,
            repository_path=request.repository_path or f"/virtual/client-intake/{project_id}",
            repository_url=request.repository_url,
            default_branch=request.default_branch,
            status=ProjectStatus.CREATED,
            manifest_hash=hash_json(document),
            manifest=document,
        )
        source_object = await self._store_source_manifest(project.id, document)
        model, snapshot, bundle, artifact_validation, traceability, artifacts = (
            self._compile_client_blueprint(
                project=project,
                manifest=manifest,
                validation=validation,
                snapshot_id=await self._next_snapshot_id(project.id),
                snapshot_status="draft",
            )
        )
        aeir_write = await self._append_aeir_projection(
            project_id=project.id,
            model=model,
            actor_id=actor_id,
            source_object=source_object,
            source_metadata={"stage": "client_blueprint_import"},
            snapshot=snapshot,
            validation=validation,
            interpretation=interpretation,
            clarification=clarification,
            bundle=bundle,
            traceability=traceability,
        )
        self._session.add_all([project, *artifacts])
        await AuditWriter(self._session).append_project_event(
            project_id=project.id,
            event_type="client_blueprint.manifest_imported",
            actor_type="human",
            actor_id=actor_id,
            payload={
                "source_manifest_sha256": model.source_manifest_sha256,
                "validation_report_sha256": validation.report_sha256,
                "source_object": source_object.__dict__,
                "aeir_model_version_id": str(aeir_write.version.id),
                "aeir_change_event_hash": aeir_write.event.event_hash,
                "interpretation_batch_sha256": (
                    None if interpretation is None else interpretation.batch_sha256
                ),
                "ai_operation_sha256": (
                    None if interpretation is None else interpretation.ai_operation.operation_sha256
                ),
                "clarification_report_sha256": clarification.report_sha256,
                "project_snapshot_sha256": snapshot.snapshot_sha256,
                "artifact_validation_report_sha256": artifact_validation.report_sha256,
                "artifact_ids": [str(item.id) for item in artifacts],
                "artifact_hashes": {item.artifact_type: item.content_hash for item in artifacts},
                "review_state": self._review_state(validation),
            },
        )
        await self._session.commit()
        return self._client_blueprint_response(
            project=project,
            validation=validation,
            interpretation=interpretation,
            clarification=clarification,
            source_object=source_object,
            aeir_write=aeir_write,
            model=model,
            snapshot=snapshot,
            bundle=bundle,
            artifact_validation=artifact_validation,
            traceability=traceability,
            artifacts=artifacts,
            review_state=self._review_state(validation),
        )

    async def review_client_blueprint(
        self,
        project_id: uuid.UUID,
        request: ClientBlueprintReviewRequest,
        *,
        actor_id: str,
    ) -> ClientBlueprintResponse:
        project = await self._session.get(ProjectModel, project_id)
        if project is None:
            raise ProjectFormationError("Project not found")
        corrected_document = self._corrected_manifest_document(request)
        document = corrected_document or project.manifest
        validation, manifest = self._validated_manifest(document)
        interpretation = self._interpretation_batch(
            document=document,
            interpretation_output=request.interpretation_output,
            ai_operation=request.ai_operation,
        )
        clarification = generate_clarification_report(validation, interpretation)
        if corrected_document is not None:
            project.name = manifest.project_intent.name
            project.description = manifest.project_intent.summary
            project.manifest = document
            project.manifest_hash = hash_json(document)
        source_object = await self._store_source_manifest(project.id, document)
        model, snapshot, bundle, artifact_validation, traceability, artifacts = (
            self._compile_client_blueprint(
                project=project,
                manifest=manifest,
                validation=validation,
                snapshot_id=await self._next_snapshot_id(project.id),
                snapshot_status="approved" if request.decision == "approved" else "draft",
            )
        )
        aeir_write = None
        snapshot_write = None
        if corrected_document is not None:
            aeir_write = await self._append_aeir_projection(
                project_id=project.id,
                model=model,
                actor_id=actor_id,
                source_object=source_object,
                source_metadata={"stage": "client_blueprint_review"},
                snapshot=snapshot,
                validation=validation,
                interpretation=interpretation,
                clarification=clarification,
                bundle=bundle,
                traceability=traceability,
                review_decision={
                    "decision": request.decision,
                    "reviewer_comment": request.reviewer_comment,
                    "corrected_manifest": corrected_document is not None,
                },
            )
        else:
            snapshot_write = await self._append_review_snapshot(
                project_id=project.id,
                model=model,
                actor_id=actor_id,
                snapshot=snapshot,
                validation=validation,
                interpretation=interpretation,
                clarification=clarification,
                bundle=bundle,
                traceability=traceability,
                review_decision={
                    "decision": request.decision,
                    "reviewer_comment": request.reviewer_comment,
                    "corrected_manifest": False,
                },
            )
        approval_decision = {
            "approved": ApprovalDecision.APPROVED,
            "changes_requested": "changes_requested",
            "rejected": ApprovalDecision.REJECTED,
        }[request.decision]
        approval = ApprovalModel(
            id=uuid.uuid4(),
            project_id=project.id,
            artifact_id=next(
                item.id
                for item in artifacts
                if item.artifact_type == ArtifactType.PROJECT_BLUEPRINT
            ),
            decision=approval_decision,
            reviewer=actor_id,
            comment=request.reviewer_comment,
        )
        self._session.add_all([*artifacts, approval])
        await AuditWriter(self._session).append_project_event(
            project_id=project.id,
            event_type="client_blueprint.review_recorded",
            actor_type="human",
            actor_id=actor_id,
            payload={
                "decision": request.decision,
                "corrected_manifest": corrected_document is not None,
                "corrected_manifest_content_type": (
                    request.content_type if corrected_document is not None else None
                ),
                "source_manifest_sha256": model.source_manifest_sha256,
                "source_object": source_object.__dict__,
                "aeir_model_version_id": (
                    None if aeir_write is None else str(aeir_write.version.id)
                ),
                "aeir_change_event_hash": (
                    snapshot_write.event.event_hash
                    if snapshot_write is not None and snapshot_write.event is not None
                    else None if aeir_write is None else aeir_write.event.event_hash
                ),
                "validation_report_sha256": validation.report_sha256,
                "interpretation_batch_sha256": (
                    None if interpretation is None else interpretation.batch_sha256
                ),
                "ai_operation_sha256": (
                    None if interpretation is None else interpretation.ai_operation.operation_sha256
                ),
                "clarification_report_sha256": clarification.report_sha256,
                "blueprint_artifact_id": str(
                    next(
                        item.id
                        for item in artifacts
                        if item.artifact_type == ArtifactType.PROJECT_BLUEPRINT
                    )
                ),
                "project_snapshot_sha256": snapshot.snapshot_sha256,
                "traceability_manifest_sha256": traceability.manifest_sha256,
                "artifact_validation_report_sha256": artifact_validation.report_sha256,
                "aeir_snapshot_event_hash": (
                    None
                    if snapshot_write is None or snapshot_write.event is None
                    else snapshot_write.event.event_hash
                ),
            },
        )
        await self._session.commit()
        return self._client_blueprint_response(
            project=project,
            validation=validation,
            interpretation=interpretation,
            clarification=clarification,
            source_object=source_object,
            aeir_write=aeir_write,
            model=model,
            snapshot=snapshot,
            bundle=bundle,
            artifact_validation=artifact_validation,
            traceability=traceability,
            artifacts=artifacts,
            review_state=self._review_state(validation, request.decision),
        )

    async def answer_client_blueprint_clarifications(
        self,
        project_id: uuid.UUID,
        request: ClientBlueprintClarificationAnswerRequest,
        *,
        actor_id: str,
    ) -> ClientBlueprintResponse:
        project = await self._session.get(ProjectModel, project_id)
        if project is None:
            raise ProjectFormationError("Project not found")
        validation, manifest = self._validated_manifest(project.manifest)
        base_model = compile_aepm(manifest)
        try:
            clarification = ClarificationReport.model_validate(request.clarification_report)
            if clarification.validation_report_sha256 != validation.report_sha256:
                raise ValueError("clarification report does not match current validation")
            answers = tuple(
                ClarificationAnswer.model_validate(answer) for answer in request.answers
            )
            answer_batch = build_answer_batch(
                report=clarification,
                base_model=base_model,
                respondent_id=request.respondent_id or actor_id,
                answers=answers,
            )
            model = apply_answer_batch(
                report=clarification,
                base_model=base_model,
                batch=answer_batch,
            )
        except (ValidationError, ValueError) as exc:
            raise ProjectFormationError(
                "Clarification answers failed validation"
            ) from exc
        source_object = await self._store_source_manifest(project.id, project.manifest)
        snapshot = compile_project_snapshot(
            model,
            snapshot_id=await self._next_snapshot_id(project.id),
            status="draft",
        )
        bundle = compile_artifact_bundle(model, snapshot, allow_draft=True)
        artifact_validation = validate_artifact_bundle(model, bundle)
        traceability = compile_traceability_manifest(model, bundle)
        blueprint = self._client_blueprint_markdown(manifest, bundle, traceability)
        generated_at = datetime.now(UTC)
        artifact_bodies = [
            (
                ArtifactType.PROJECT_MANIFEST,
                "application/json",
                canonical_json(manifest.model_dump(mode="json")),
            ),
            (
                ArtifactType.CANONICAL_PROJECT_MODEL,
                "application/json",
                canonical_json(model.model_dump(mode="json")),
            ),
            (
                ArtifactType.PROJECT_SNAPSHOT,
                "application/json",
                canonical_json(snapshot.model_dump(mode="json")),
            ),
            (
                ArtifactType.PROJECT_BLUEPRINT,
                "text/markdown; charset=utf-8",
                blueprint,
            ),
            (
                ArtifactType.TRACEABILITY_MANIFEST,
                "application/json",
                canonical_json(traceability.model_dump(mode="json")),
            ),
            (
                ArtifactType.ARTIFACT_CONTRACTS,
                "application/json",
                canonical_json(
                    {
                        "schema_version": "artifact-contract-bundle-0.1",
                        "contracts": [
                            item.model_dump(mode="json") for item in bundle.contracts
                        ],
                    }
                ),
            ),
            (
                ArtifactType.ARTIFACT_VALIDATION_REPORT,
                "application/json",
                canonical_json(artifact_validation.model_dump(mode="json")),
            ),
        ]
        artifacts = [
            ArtifactModel(
                id=uuid.uuid4(),
                project_id=project.id,
                run_id=None,
                artifact_type=artifact_type,
                media_type=media_type,
                content=content,
                content_hash=hash_json(
                    {
                        "artifact_type": artifact_type,
                        "project_id": str(project.id),
                        "generated_at": generated_at.isoformat(),
                        "content": content,
                    }
                ),
            )
            for artifact_type, media_type, content in artifact_bodies
        ]
        aeir_write = await self._append_aeir_projection(
            project_id=project.id,
            model=model,
            actor_id=actor_id,
            source_object=source_object,
            source_metadata={"stage": "client_blueprint_clarification_answers"},
            snapshot=snapshot,
            validation=validation,
            clarification=clarification,
            answer_batch=answer_batch,
            bundle=bundle,
            traceability=traceability,
            review_decision={
                "decision": "clarifications_answered",
                "answer_batch_sha256": answer_batch.answer_batch_sha256,
                "respondent_id": answer_batch.respondent_id,
            },
        )
        self._session.add_all([*artifacts])
        await AuditWriter(self._session).append_project_event(
            project_id=project.id,
            event_type="client_blueprint.clarifications_answered",
            actor_type="human",
            actor_id=actor_id,
            payload={
                "clarification_report_sha256": clarification.report_sha256,
                "answer_batch_sha256": answer_batch.answer_batch_sha256,
                "answer_count": len(answer_batch.answers),
                "aeir_model_version_id": str(aeir_write.version.id),
                "aeir_change_event_hash": aeir_write.event.event_hash,
                "project_snapshot_sha256": snapshot.snapshot_sha256,
                "artifact_validation_report_sha256": artifact_validation.report_sha256,
            },
        )
        await self._session.commit()
        return self._client_blueprint_response(
            project=project,
            validation=validation,
            interpretation=None,
            clarification=clarification,
            source_object=source_object,
            aeir_write=aeir_write,
            model=model,
            snapshot=snapshot,
            bundle=bundle,
            artifact_validation=artifact_validation,
            traceability=traceability,
            artifacts=artifacts,
            review_state="clarifications_answered",
        )

    async def get_client_blueprint_markdown(
        self, project_id: uuid.UUID, artifact_id: uuid.UUID | None
    ) -> str:
        statement = select(ArtifactModel).where(
            ArtifactModel.project_id == project_id,
            ArtifactModel.artifact_type == ArtifactType.PROJECT_BLUEPRINT,
        )
        if artifact_id is not None:
            statement = statement.where(ArtifactModel.id == artifact_id)
        artifact = await self._session.scalar(statement.order_by(ArtifactModel.created_at.desc()))
        if artifact is None:
            raise ProjectFormationError("Client blueprint artifact not found")
        return artifact.content

    def _missing_information(self, request: FormationRequest) -> list[str]:
        missing: list[str] = []
        if not request.expected_outcome:
            missing.append("expected outcome")
        if not request.target_users:
            missing.append("target users")
        if not request.constraints:
            missing.append("constraints or known limits")
        if not request.known_systems:
            missing.append("existing systems or integrations")
        return missing

    def _next_action(self, missing: list[str]) -> str:
        if missing:
            return "Ask the client for the missing information, then regenerate the formation pack."
        return "Review the formation approval pack and approve before starting execution work."

    def _documents(
        self,
        project: ProjectModel,
        request: FormationRequest,
        missing: list[str],
        status: str,
        traceability: dict[str, Any],
    ) -> list[FormationDocument]:
        modules = self._modules(request.idea, project.manifest.get("project_type"))
        return [
            FormationDocument(
                ArtifactType.PROJECT_BRIEF,
                "Project Brief",
                {
                    "problem_statement": request.idea,
                    "business_objectives": [request.expected_outcome or "Clarify expected outcome"],
                    "stakeholders": request.target_users or ["to be confirmed"],
                    "constraints": request.constraints,
                    "assumptions": missing,
                    "success_metrics": self._success_metrics(request),
                },
                (
                    "Business brief created from the idea, target users, constraints, "
                    "and success signals."
                ),
            ),
            FormationDocument(
                ArtifactType.SOLUTION_PROPOSAL,
                "Solution Proposal",
                {
                    "recommended_modules": modules,
                    "integration_targets": request.known_systems,
                    "security_requirements": [
                        "human approval before execution",
                        "audit trail for decisions",
                        "repository boundary validation",
                    ],
                    "architecture_direction": "modular monolith first with clear bounded contexts",
                },
                (
                    "Solution proposal created with modules, integrations, security, "
                    "and architecture direction."
                ),
            ),
            FormationDocument(
                ArtifactType.DELIVERY_PLAN,
                "Delivery Plan",
                {
                    "phases": [
                        "intake",
                        "requirements",
                        "architecture",
                        "work package planning",
                        "implementation",
                        "validation",
                        "handover",
                    ],
                    "parallelization_rule": (
                        "Only tasks with approved interfaces and non-overlapping files "
                        "may run in parallel."
                    ),
                    "deadline": request.deadline,
                    "budget_signal": request.budget_signal,
                },
                (
                    "Delivery plan created with phases, parallelization rule, deadline, "
                    "and budget signal."
                ),
            ),
            FormationDocument(
                ArtifactType.FORMATION_QUALITY_REVIEW,
                "Formation Quality Review",
                {
                    "status": status,
                    "missing_information": missing,
                    "risk_register": self._risks(request, missing),
                    "confidence": "medium" if missing else "high",
                    "correction_attempt": request.correction_attempt,
                },
                "Quality review explains readiness, missing information, risks, and confidence.",
            ),
            FormationDocument(
                ArtifactType.FORMATION_APPROVAL_PACK,
                "Formation Approval Pack",
                {
                    "approval_state": "pending_human_review",
                    "recommended_decision": "request_clarification" if missing else "approve",
                    "operator_message": self._next_action(missing),
                    "traceability": traceability,
                },
                "Approval pack tells the operator whether to approve or ask targeted questions.",
            ),
        ]

    def _modules(self, idea: str, project_type: str | None) -> list[str]:
        words = idea.lower()
        modules = ["project governance", "requirements", "architecture", "delivery planning"]
        if project_type:
            modules.insert(0, project_type.replace("_", " "))
        if "dashboard" in words or "report" in words:
            modules.append("dashboards and reporting")
        if "api" in words or "integrat" in words:
            modules.append("API and integration")
        if "security" in words or "compliance" in words:
            modules.append("security and compliance")
        if "deploy" in words or "cloud" in words:
            modules.append("DevOps and infrastructure")
        return list(dict.fromkeys(modules))

    def _success_metrics(self, request: FormationRequest) -> list[str]:
        metrics = ["approved project plan", "clear execution graph", "reusable blueprint output"]
        if request.budget_signal:
            metrics.append("budget alignment visible before implementation")
        if request.deadline:
            metrics.append("delivery plan aligned to deadline")
        return metrics

    def _risks(self, request: FormationRequest, missing: list[str]) -> list[dict[str, str]]:
        risks = [
            {
                "risk": "unclear scope",
                "mitigation": "keep human approval before execution",
            }
        ]
        if missing:
            risks.append(
                {
                    "risk": "missing formation information",
                    "mitigation": "ask targeted clarification questions before approval",
                }
            )
        if not request.known_systems:
            risks.append(
                {
                    "risk": "unknown integrations",
                    "mitigation": "run infrastructure discovery before architecture approval",
                }
            )
        return risks

    def _manifest_document(self, request: ClientBlueprintImportRequest) -> dict[str, Any]:
        if request.manifest is not None and request.manifest_text is not None:
            raise ProjectFormationError("Submit either manifest or manifest_text, not both")
        if request.manifest is not None:
            return request.manifest
        if request.manifest_text is None:
            raise ProjectFormationError("Client manifest is required")
        return self._parse_manifest_text(request.manifest_text, request.content_type)

    def _corrected_manifest_document(
        self, request: ClientBlueprintReviewRequest
    ) -> dict[str, Any] | None:
        if request.corrected_manifest is not None and request.corrected_manifest_text is not None:
            raise ProjectFormationError(
                "Submit either corrected_manifest or corrected_manifest_text, not both"
            )
        if request.corrected_manifest is not None:
            return request.corrected_manifest
        if request.corrected_manifest_text is None:
            return None
        return self._parse_manifest_text(request.corrected_manifest_text, request.content_type)

    def _parse_manifest_text(self, manifest_text: str, content_type: str) -> dict[str, Any]:
        try:
            if content_type == "application/json":
                parsed = json.loads(manifest_text)
            else:
                parsed = yaml.safe_load(manifest_text)
        except (json.JSONDecodeError, yaml.YAMLError) as exc:
            raise ProjectFormationError("Client manifest could not be parsed") from exc
        if not isinstance(parsed, dict):
            raise ProjectFormationError("Client manifest must be an object")
        return parsed

    def _validated_manifest(
        self, document: dict[str, Any]
    ) -> tuple[AepmValidationReport, AepmManifest]:
        validation = AepmValidationEngine().validate(document)
        if not validation.valid:
            raise ProjectFormationError("Client manifest has blocking validation findings")
        try:
            return validation, AepmManifest.model_validate(document)
        except ValidationError as exc:
            raise ProjectFormationError("Client manifest does not match AEPM v0.1") from exc

    def _interpretation_batch(
        self,
        *,
        document: dict[str, Any],
        interpretation_output: dict[str, Any] | None,
        ai_operation: dict[str, Any] | None,
    ) -> InterpretationBatch | None:
        if interpretation_output is None:
            if ai_operation is not None:
                raise ProjectFormationError(
                    "AI operation provenance requires interpretation_output"
                )
            return None
        validation = interpretation_output_validator().validate(
            json.dumps(interpretation_output, sort_keys=True)
        )
        if not validation.valid or validation.normalized_output is None:
            raise ProjectFormationError("AI interpretation output failed structured validation")
        assert validation.output_hash is not None
        try:
            return finalize_interpretation(
                source=document,
                normalized_output=validation.normalized_output,
                model_output_sha256=validation.output_hash,
                ai_operation=ai_operation,
            )
        except ValueError as exc:
            raise ProjectFormationError(
                "AI interpretation output failed provenance binding"
            ) from exc

    async def _store_source_manifest(
        self, project_id: uuid.UUID, document: dict[str, Any]
    ) -> StoredObject:
        content = canonical_json(document).encode("utf-8")
        return await LocalContentAddressedObjectStore(get_settings().artifact_root).put(
            project_id=project_id,
            content=content,
        )

    async def _append_aeir_projection(
        self,
        *,
        project_id: uuid.UUID,
        model: AeirProjectModel,
        actor_id: str,
        source_object: StoredObject,
        source_metadata: dict[str, object],
        snapshot: AeirProjectSnapshot | None = None,
        validation: AepmValidationReport | None = None,
        interpretation: InterpretationBatch | None = None,
        clarification: ClarificationReport | None = None,
        answer_batch: object | None = None,
        bundle: ArtifactBundle | None = None,
        traceability: ArtifactTraceabilityManifest | None = None,
        review_decision: dict[str, object] | None = None,
    ) -> AeirWriteSet:
        version_number = (
            await self._session.scalar(
                select(func.max(AeirModelVersionModel.version_number)).where(
                    AeirModelVersionModel.project_id == project_id
                )
            )
            or 0
        ) + 1
        artifact_version_start = (
            await self._session.scalar(
                select(func.max(AeirArtifactVersionModel.version_number)).where(
                    AeirArtifactVersionModel.project_id == project_id
                )
            )
            or 0
        ) + 1
        event_sequence = (
            await self._session.scalar(
                select(func.max(AeirChangeEventModel.sequence)).where(
                    AeirChangeEventModel.project_id == project_id
                )
            )
            or 0
        ) + 1
        previous_event_hash = await self._session.scalar(
            select(AeirChangeEventModel.event_hash)
            .where(AeirChangeEventModel.project_id == project_id)
            .order_by(AeirChangeEventModel.sequence.desc())
            .limit(1)
        )
        write_set = build_aeir_write_set(
            project_id=project_id,
            model=model,
            version_number=version_number,
            actor_id=actor_id,
            previous_event_hash=previous_event_hash,
            event_sequence=event_sequence,
            stored_source=source_object,
            source_metadata=source_metadata,
            snapshot=snapshot,
            validation=validation,
            interpretation=interpretation,
            clarification=clarification,
            answer_batch=answer_batch,
            bundle=bundle,
            traceability=traceability,
            artifact_version_start=artifact_version_start,
            review_decision=review_decision,
        )
        self._session.add(write_set.version)
        self._session.add_all([*write_set.sources, *write_set.objects, *write_set.relationships])
        self._session.add_all(list(write_set.r2_records))
        self._session.add(write_set.event)
        return write_set

    async def _append_review_snapshot(
        self,
        *,
        project_id: uuid.UUID,
        model: AeirProjectModel,
        actor_id: str,
        snapshot: AeirProjectSnapshot,
        validation: AepmValidationReport,
        interpretation: InterpretationBatch | None,
        clarification: ClarificationReport,
        bundle: ArtifactBundle,
        traceability: ArtifactTraceabilityManifest,
        review_decision: dict[str, object],
    ) -> AeirSnapshotWriteSet:
        model_version = await self._session.scalar(
            select(AeirModelVersionModel)
            .where(
                AeirModelVersionModel.project_id == project_id,
                AeirModelVersionModel.model_sha256 == model.model_sha256,
            )
            .order_by(AeirModelVersionModel.version_number.desc())
            .limit(1)
        )
        if model_version is None:
            raise ProjectFormationError(
                "Approved review requires an existing AEIR model version"
            )
        artifact_version_start = (
            await self._session.scalar(
                select(func.max(AeirArtifactVersionModel.version_number)).where(
                    AeirArtifactVersionModel.project_id == project_id
                )
            )
            or 0
        ) + 1
        event_sequence = (
            await self._session.scalar(
                select(func.max(AeirChangeEventModel.sequence)).where(
                    AeirChangeEventModel.project_id == project_id
                )
            )
            or 0
        ) + 1
        previous_event_hash = await self._session.scalar(
            select(AeirChangeEventModel.event_hash)
            .where(AeirChangeEventModel.project_id == project_id)
            .order_by(AeirChangeEventModel.sequence.desc())
            .limit(1)
        )
        write_set = build_aeir_snapshot_write_set(
            project_id=project_id,
            model_version_id=model_version.id,
            model=model,
            snapshot=snapshot,
            validation=validation,
            interpretation=interpretation,
            clarification=clarification,
            bundle=bundle,
            traceability=traceability,
            artifact_version_start=artifact_version_start,
            actor_id=actor_id,
            event_sequence=event_sequence,
            previous_event_hash=previous_event_hash,
            review_decision=review_decision,
        )
        self._session.add_all(list(write_set.records))
        return write_set

    async def _next_snapshot_id(self, project_id: uuid.UUID) -> str:
        latest = await self._session.scalar(
            select(func.max(AeirProjectSnapshotModel.snapshot_id)).where(
                AeirProjectSnapshotModel.project_id == project_id
            )
        )
        if latest is None:
            return "SNP-0001"
        try:
            number = int(str(latest).removeprefix("SNP-"))
        except ValueError as exc:
            raise ProjectFormationError("Stored project snapshot id is invalid") from exc
        return f"SNP-{number + 1:04d}"

    def _compile_client_blueprint(
        self,
        *,
        project: ProjectModel,
        manifest: AepmManifest,
        validation: AepmValidationReport,
        snapshot_id: str,
        snapshot_status: Literal["draft", "approved"],
    ) -> tuple[
        AeirProjectModel,
        AeirProjectSnapshot,
        ArtifactBundle,
        ArtifactValidationReport,
        ArtifactTraceabilityManifest,
        list[ArtifactModel],
    ]:
        generated_at = datetime.now(UTC)
        model = compile_aepm(manifest)
        snapshot = compile_project_snapshot(
            model,
            snapshot_id=snapshot_id,
            status=snapshot_status,
        )
        bundle = compile_artifact_bundle(
            model,
            snapshot,
            allow_draft=snapshot_status == "draft",
        )
        artifact_validation = validate_artifact_bundle(model, bundle)
        traceability = compile_traceability_manifest(model, bundle)
        blueprint = self._client_blueprint_markdown(manifest, bundle, traceability)
        bodies = [
            (
                ArtifactType.PROJECT_MANIFEST,
                "application/json",
                canonical_json(manifest.model_dump(mode="json")),
            ),
            (
                ArtifactType.CANONICAL_PROJECT_MODEL,
                "application/json",
                canonical_json(model.model_dump(mode="json")),
            ),
            (
                ArtifactType.PROJECT_SNAPSHOT,
                "application/json",
                canonical_json(snapshot.model_dump(mode="json")),
            ),
            (
                ArtifactType.PROJECT_BLUEPRINT,
                "text/markdown; charset=utf-8",
                blueprint,
            ),
            (
                ArtifactType.TRACEABILITY_MANIFEST,
                "application/json",
                canonical_json(traceability.model_dump(mode="json")),
            ),
            (
                ArtifactType.ARTIFACT_CONTRACTS,
                "application/json",
                canonical_json(
                    {
                        "schema_version": "artifact-contract-bundle-0.1",
                        "contracts": [
                            item.model_dump(mode="json") for item in bundle.contracts
                        ],
                    }
                ),
            ),
            (
                ArtifactType.ARTIFACT_VALIDATION_REPORT,
                "application/json",
                canonical_json(artifact_validation.model_dump(mode="json")),
            ),
        ]
        artifacts = [
            ArtifactModel(
                id=uuid.uuid4(),
                project_id=project.id,
                run_id=None,
                artifact_type=artifact_type,
                media_type=media_type,
                content=content,
                content_hash=hash_json(
                    {
                        "artifact_type": artifact_type,
                        "project_id": str(project.id),
                        "generated_at": generated_at.isoformat(),
                        "content": content,
                    }
                ),
            )
            for artifact_type, media_type, content in bodies
        ]
        return model, snapshot, bundle, artifact_validation, traceability, artifacts

    def _client_blueprint_markdown(
        self,
        manifest: AepmManifest,
        bundle: ArtifactBundle,
        traceability: ArtifactTraceabilityManifest,
    ) -> str:
        lines = [
            f"# Project Blueprint - {manifest.project_intent.name}",
            "",
            f"Source manifest SHA-256: `{traceability.source_manifest_sha256}`",
            f"AEIR model SHA-256: `{bundle.source_model_sha256}`",
            f"Artifact bundle SHA-256: `{bundle.bundle_sha256}`",
            f"Traceability manifest SHA-256: `{traceability.manifest_sha256}`",
            "",
        ]
        for artifact_type in bundle.artifacts:
            lines.append(
                render_traceable_artifact_markdown(
                    artifact_type.artifact_type, bundle, traceability
                ).rstrip()
            )
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _client_blueprint_response(
        self,
        *,
        project: ProjectModel,
        validation: AepmValidationReport,
        interpretation: InterpretationBatch | None,
        clarification: ClarificationReport,
        source_object: StoredObject,
        aeir_write: AeirWriteSet | None,
        model: AeirProjectModel,
        snapshot: AeirProjectSnapshot,
        bundle: ArtifactBundle,
        artifact_validation: ArtifactValidationReport,
        traceability: ArtifactTraceabilityManifest,
        artifacts: list[ArtifactModel],
        review_state: str,
    ) -> ClientBlueprintResponse:
        blueprint_artifact = next(
            item for item in artifacts if item.artifact_type == ArtifactType.PROJECT_BLUEPRINT
        )
        missing = [
            f"{finding.path}: {finding.message}"
            for finding in validation.findings
            if finding.severity is ValidationSeverity.ERROR
        ]
        assumptions = [
            f"{finding.path}: {finding.message}"
            for finding in validation.findings
            if finding.rule_id == "AEPM.AMBIGUITY.UNRESOLVED_ASSUMPTION"
        ]
        assumptions.extend(
            (
                f"{item.id} "
                f"[{item.lifecycle_status}/{item.truth_status}/{item.approval_status}]: "
                f"{item.name}"
            )
            for item in model.objects
            if item.truth_status in {TruthStatus.INFERRED, TruthStatus.ASSUMED}
            or item.approval_status is ApprovalStatus.PENDING
        )
        assumptions.extend(
            f"{question.id}: {question.prompt}"
            for question in (
                *clarification.important_ambiguities,
                *clarification.unverified_assumptions,
            )
        )
        return ClientBlueprintResponse(
            project_id=project.id,
            status=str(project.status),
            review_state=review_state,
            project_name=project.name,
            source_manifest_sha256=model.source_manifest_sha256,
            validation_report=validation.model_dump(mode="json"),
            interpretation_batch=(
                None if interpretation is None else interpretation.model_dump(mode="json")
            ),
            clarification_report=clarification.model_dump(mode="json"),
            missing_information=missing,
            assumptions=assumptions,
            canonical_model=model.model_dump(mode="json"),
            canonical_object_count=len(model.objects),
            relationship_count=len(model.relationships),
            artifacts=[
                ClientBlueprintArtifactResponse(
                    artifact_id=item.id,
                    artifact_type=str(item.artifact_type),
                    media_type=item.media_type,
                    content_hash=item.content_hash,
                    download_url=(
                        f"/api/v1/project-formation/client-blueprints/{project.id}/download"
                        f"?artifact_id={item.id}"
                        if item.id == blueprint_artifact.id
                        else None
                    ),
                )
                for item in artifacts
            ],
            blueprint_download_url=(
                f"/api/v1/project-formation/client-blueprints/{project.id}/download"
                f"?artifact_id={blueprint_artifact.id}"
            ),
            traceability={
                "schema_version": traceability.schema_version,
                "source_model_sha256": traceability.source_model_sha256,
                "source_manifest_sha256": traceability.source_manifest_sha256,
                "source_object": source_object.__dict__,
                "artifact_bundle_sha256": traceability.artifact_bundle_sha256,
                "project_snapshot_id": snapshot.snapshot_id,
                "project_snapshot_sha256": snapshot.snapshot_sha256,
                "project_snapshot_status": snapshot.status,
                "traceability_manifest_sha256": traceability.manifest_sha256,
                "artifact_validation_report_sha256": artifact_validation.report_sha256,
                "artifact_validation_valid": artifact_validation.valid,
                "artifact_validation_finding_count": len(artifact_validation.findings),
                "section_trace_count": len(traceability.section_traces),
                "entry_trace_count": len(traceability.entry_traces),
                "artifact_types": [item.artifact_type.value for item in bundle.artifacts],
            },
            proof=self._r1_proof(
                project=project,
                validation=validation,
                interpretation=interpretation,
                clarification=clarification,
                source_object=source_object,
                aeir_write=aeir_write,
                model=model,
                snapshot=snapshot,
                bundle=bundle,
                artifact_validation=artifact_validation,
                traceability=traceability,
                artifacts=artifacts,
                review_state=review_state,
            ),
            next_action=self._client_next_action(review_state),
        )

    def _r1_proof(
        self,
        *,
        project: ProjectModel,
        validation: AepmValidationReport,
        interpretation: InterpretationBatch | None,
        clarification: ClarificationReport,
        source_object: StoredObject,
        aeir_write: AeirWriteSet | None,
        model: AeirProjectModel,
        snapshot: AeirProjectSnapshot,
        bundle: ArtifactBundle,
        artifact_validation: ArtifactValidationReport,
        traceability: ArtifactTraceabilityManifest,
        artifacts: list[ArtifactModel],
        review_state: str,
    ) -> dict[str, object]:
        return {
            "schema_version": "r1-manifest-to-blueprint-proof-0.1",
            "ready": validation.valid and artifact_validation.valid and len(bundle.artifacts) == 5,
            "review_state": review_state,
            "project_id": str(project.id),
            "source_manifest_sha256": model.source_manifest_sha256,
            "source_object": source_object.__dict__,
            "validation_report_sha256": validation.report_sha256,
            "interpretation_batch_sha256": (
                None if interpretation is None else interpretation.batch_sha256
            ),
            "ai_operation_sha256": (
                None if interpretation is None else interpretation.ai_operation.operation_sha256
            ),
            "ai_operation_review_required": (
                None if interpretation is None else interpretation.ai_operation.review_required
            ),
            "clarification_report_sha256": clarification.report_sha256,
            "aeir_model_sha256": model.model_sha256,
            "project_snapshot_id": snapshot.snapshot_id,
            "project_snapshot_sha256": snapshot.snapshot_sha256,
            "project_snapshot_status": snapshot.status,
            "aeir_model_version_id": None if aeir_write is None else str(aeir_write.version.id),
            "aeir_change_event_hash": None if aeir_write is None else aeir_write.event.event_hash,
            "artifact_bundle_sha256": bundle.bundle_sha256,
            "artifact_compilation_status": bundle.compilation_status,
            "artifact_contract_count": len(bundle.contracts),
            "artifact_validation_report_sha256": artifact_validation.report_sha256,
            "artifact_validation_valid": artifact_validation.valid,
            "artifact_validation_finding_count": len(artifact_validation.findings),
            "traceability_manifest_sha256": traceability.manifest_sha256,
            "artifact_count": len(bundle.artifacts),
            "stored_artifact_count": len(artifacts),
            "canonical_object_count": len(model.objects),
            "relationship_count": len(model.relationships),
            "section_trace_count": len(traceability.section_traces),
            "entry_trace_count": len(traceability.entry_traces),
        }

    def _review_state(self, validation: AepmValidationReport, decision: str | None = None) -> str:
        if decision == "approved":
            return "client_approved"
        if decision == "rejected":
            return "client_rejected"
        if decision == "changes_requested":
            return "client_changes_requested"
        if validation.findings:
            return "awaiting_client_review_with_warnings"
        return "awaiting_client_review"

    def _client_next_action(self, review_state: str) -> str:
        if review_state == "client_approved":
            return "Use the downloaded blueprint as the approved requirements and design baseline."
        if review_state == "client_rejected":
            return "Revise the client manifest before generating a new blueprint baseline."
        if review_state == "client_changes_requested":
            return "Apply client corrections, then regenerate and review the blueprint again."
        if review_state == "clarifications_answered":
            return (
                "Review the regenerated draft blueprint, then approve or request further changes."
            )
        return "Ask the client to review assumptions and approve or correct the blueprint."
