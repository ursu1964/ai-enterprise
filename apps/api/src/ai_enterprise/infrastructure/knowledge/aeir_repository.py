from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.domain.aeir import AeirProjectModel
from ai_enterprise.domain.specification.kernel import specification_hash
from ai_enterprise.infrastructure.database.models import ProjectModel
from ai_enterprise.infrastructure.knowledge.models import (
    AeirAiOperationModel,
    AeirArtifactTraceLinkModel,
    AeirArtifactVersionModel,
    AeirChangeEventModel,
    AeirClarificationAnswerModel,
    AeirClarificationQuestionModel,
    AeirDecisionModel,
    AeirEvidenceModel,
    AeirModelVersionModel,
    AeirObjectModel,
    AeirObjectSourceLinkModel,
    AeirObjectVersionModel,
    AeirProjectSnapshotModel,
    AeirRelationshipModel,
    AeirRelationshipSourceLinkModel,
    AeirRelationshipVersionModel,
    AeirSourceObjectModel,
    AeirValidationFindingModel,
)
from ai_enterprise.infrastructure.knowledge.object_store import StoredObject


@dataclass(frozen=True)
class AeirWriteSet:
    version: AeirModelVersionModel
    sources: tuple[AeirSourceObjectModel, ...]
    objects: tuple[AeirObjectModel, ...]
    relationships: tuple[AeirRelationshipModel, ...]
    event: AeirChangeEventModel
    snapshot: AeirProjectSnapshotModel | None = None
    object_versions: tuple[AeirObjectVersionModel, ...] = ()
    relationship_versions: tuple[AeirRelationshipVersionModel, ...] = ()
    evidence: tuple[AeirEvidenceModel, ...] = ()
    object_source_links: tuple[AeirObjectSourceLinkModel, ...] = ()
    relationship_source_links: tuple[AeirRelationshipSourceLinkModel, ...] = ()
    validation_findings: tuple[AeirValidationFindingModel, ...] = ()
    clarification_questions: tuple[AeirClarificationQuestionModel, ...] = ()
    clarification_answers: tuple[AeirClarificationAnswerModel, ...] = ()
    ai_operations: tuple[AeirAiOperationModel, ...] = ()
    artifact_versions: tuple[AeirArtifactVersionModel, ...] = ()
    artifact_trace_links: tuple[AeirArtifactTraceLinkModel, ...] = ()
    decisions: tuple[AeirDecisionModel, ...] = ()

    @property
    def r2_records(self) -> tuple[object, ...]:
        return (
            *((self.snapshot,) if self.snapshot is not None else ()),
            *self.object_versions,
            *self.relationship_versions,
            *self.evidence,
            *self.object_source_links,
            *self.relationship_source_links,
            *self.validation_findings,
            *self.clarification_questions,
            *self.clarification_answers,
            *self.ai_operations,
            *self.artifact_versions,
            *self.artifact_trace_links,
            *self.decisions,
        )


@dataclass(frozen=True)
class AeirSnapshotWriteSet:
    snapshot: AeirProjectSnapshotModel
    validation_findings: tuple[AeirValidationFindingModel, ...] = ()
    clarification_questions: tuple[AeirClarificationQuestionModel, ...] = ()
    ai_operations: tuple[AeirAiOperationModel, ...] = ()
    artifact_versions: tuple[AeirArtifactVersionModel, ...] = ()
    artifact_trace_links: tuple[AeirArtifactTraceLinkModel, ...] = ()
    decisions: tuple[AeirDecisionModel, ...] = ()
    event: AeirChangeEventModel | None = None

    @property
    def records(self) -> tuple[object, ...]:
        return (
            self.snapshot,
            *self.validation_findings,
            *self.clarification_questions,
            *self.ai_operations,
            *self.artifact_versions,
            *self.artifact_trace_links,
            *self.decisions,
            *((self.event,) if self.event is not None else ()),
        )


def build_aeir_write_set(
    *,
    project_id: uuid.UUID,
    model: AeirProjectModel,
    version_number: int,
    actor_id: str,
    previous_event_hash: str | None,
    event_sequence: int | None = None,
    stored_source: StoredObject | None = None,
    original_filename: str = "client-manifest-aepm-0.1.json",
    media_type: str = "application/json",
    source_metadata: dict[str, object] | None = None,
    snapshot: object | None = None,
    validation: object | None = None,
    interpretation: object | None = None,
    clarification: object | None = None,
    answer_batch: object | None = None,
    bundle: object | None = None,
    traceability: object | None = None,
    artifact_version_start: int = 1,
    review_decision: dict[str, object] | None = None,
) -> AeirWriteSet:
    version_id = uuid.uuid4()
    version = AeirModelVersionModel(
        id=version_id,
        project_id=project_id,
        version_number=version_number,
        schema_version=model.schema_version,
        source_manifest_sha256=model.source_manifest_sha256,
        model_sha256=model.model_sha256,
        model_document=model.model_dump(mode="json"),
        created_by=actor_id,
    )
    sources = (
        (
            AeirSourceObjectModel(
                id=uuid.uuid4(),
                project_id=project_id,
                storage_provider=stored_source.provider,
                bucket=stored_source.bucket,
                object_key=stored_source.object_key,
                original_filename=original_filename,
                media_type=media_type,
                content_sha256=stored_source.content_sha256,
                size_bytes=stored_source.size_bytes,
                source_metadata=source_metadata or {},
                uploaded_by=actor_id,
            ),
        )
        if stored_source is not None
        else ()
    )
    object_ids = {item.id: uuid.uuid4() for item in model.objects}
    objects = tuple(
        AeirObjectModel(
            id=object_ids[item.id],
            model_version_id=version_id,
            object_id=item.id,
            object_type=item.type,
            name=item.name,
            description=item.description,
            lifecycle_status=item.lifecycle_status,
            truth_status=item.truth_status,
            approval_status=item.approval_status,
            confidence=item.confidence,
            object_version=item.version,
            source_document=item.source.model_dump(mode="json"),
            source_refs=list(item.source_refs),
            evidence_refs=list(item.evidence_refs),
            relationship_refs=list(item.relationship_refs),
            object_metadata=item.metadata,
            attributes=item.attributes,
        )
        for item in model.objects
    )
    relationships = tuple(
        AeirRelationshipModel(
            id=uuid.uuid4(),
            model_version_id=version_id,
            relationship_id=item.id,
            relationship_type=item.relationship_type,
            source_object_id=object_ids[item.source_object_id],
            target_object_id=object_ids[item.target_object_id],
            lifecycle_status=item.lifecycle_status,
            truth_status=item.truth_status,
            approval_status=item.approval_status,
            confidence=item.confidence,
            valid_from=item.valid_from,
            valid_to=item.valid_to,
            relationship_document=item.model_dump(mode="json"),
        )
        for item in model.relationships
    )
    payload = {
        "schema_version": model.schema_version,
        "version_number": version_number,
        "model_sha256": model.model_sha256,
        "source_object_count": len(sources),
        "object_count": len(objects),
        "relationship_count": len(relationships),
        "clarification_answer_count": (
            0 if answer_batch is None else len(answer_batch.answers)
        ),
    }
    event_hash = specification_hash(
        {
            "project_id": str(project_id),
            "sequence": event_sequence or version_number,
            "event_type": "aeir.model-version-created",
            "actor_id": actor_id,
            "previous_hash": previous_event_hash,
            "payload": payload,
        }
    )
    event = AeirChangeEventModel(
        id=uuid.uuid4(),
        project_id=project_id,
        model_version_id=version_id,
        sequence=event_sequence or version_number,
        event_type="aeir.model-version-created",
        actor_id=actor_id,
        previous_hash=previous_event_hash,
        event_hash=event_hash,
        payload=payload,
    )
    r2 = _build_r2_records(
        project_id=project_id,
        version_id=version_id,
        version_number=version_number,
        actor_id=actor_id,
        object_rows=objects,
        relationship_rows=relationships,
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
    return AeirWriteSet(
        version,
        sources,
        objects,
        relationships,
        event,
        r2["snapshot"],
        r2["object_versions"],
        r2["relationship_versions"],
        r2["evidence"],
        r2["object_source_links"],
        r2["relationship_source_links"],
        r2["validation_findings"],
        r2["clarification_questions"],
        r2["clarification_answers"],
        r2["ai_operations"],
        r2["artifact_versions"],
        r2["artifact_trace_links"],
        r2["decisions"],
    )


def build_aeir_snapshot_write_set(
    *,
    project_id: uuid.UUID,
    model_version_id: uuid.UUID,
    model: AeirProjectModel,
    snapshot: object,
    validation: object | None,
    interpretation: object | None,
    clarification: object | None,
    bundle: object | None,
    traceability: object | None,
    artifact_version_start: int,
    actor_id: str,
    event_sequence: int,
    previous_event_hash: str | None,
    review_decision: dict[str, object] | None,
) -> AeirSnapshotWriteSet:
    snapshot_row = _snapshot_row(project_id, model_version_id, actor_id, snapshot)
    if snapshot_row is None:
        raise ValueError("snapshot-only write set requires a snapshot")
    validation_findings = _validation_finding_rows(
        project_id=project_id,
        snapshot_row=snapshot_row,
        version_id=model_version_id,
        validation=validation,
    )
    clarification_questions = _clarification_question_rows(
        project_id=project_id,
        snapshot_row=snapshot_row,
        clarification=clarification,
    )
    ai_operations = _ai_operation_rows(
        project_id=project_id,
        version_id=model_version_id,
        interpretation=interpretation,
    )
    artifact_versions, artifact_trace_links = _artifact_rows(
        project_id=project_id,
        snapshot_row=snapshot_row,
        bundle=bundle,
        traceability=traceability,
        version_number=artifact_version_start,
        actor_id=actor_id,
    )
    decisions = _decision_rows(
        project_id=project_id,
        snapshot_row=snapshot_row,
        actor_id=actor_id,
        review_decision=review_decision,
    )
    payload = {
        "schema_version": model.schema_version,
        "model_sha256": model.model_sha256,
        "snapshot_id": snapshot_row.snapshot_id,
        "snapshot_sha256": snapshot_row.snapshot_sha256,
        "artifact_version_count": len(artifact_versions),
        "decision_count": len(decisions),
    }
    event_hash = specification_hash(
        {
            "project_id": str(project_id),
            "sequence": event_sequence,
            "event_type": "aeir.project-snapshot-created",
            "actor_id": actor_id,
            "previous_hash": previous_event_hash,
            "payload": payload,
        }
    )
    event = AeirChangeEventModel(
        id=uuid.uuid4(),
        project_id=project_id,
        model_version_id=model_version_id,
        sequence=event_sequence,
        event_type="aeir.project-snapshot-created",
        actor_id=actor_id,
        previous_hash=previous_event_hash,
        event_hash=event_hash,
        payload=payload,
    )
    return AeirSnapshotWriteSet(
        snapshot=snapshot_row,
        validation_findings=validation_findings,
        clarification_questions=clarification_questions,
        ai_operations=ai_operations,
        artifact_versions=artifact_versions,
        artifact_trace_links=artifact_trace_links,
        decisions=decisions,
        event=event,
    )


def _build_r2_records(
    *,
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    version_number: int,
    actor_id: str,
    object_rows: tuple[AeirObjectModel, ...],
    relationship_rows: tuple[AeirRelationshipModel, ...],
    snapshot: object | None,
    validation: object | None,
    interpretation: object | None,
    clarification: object | None,
    answer_batch: object | None,
    bundle: object | None,
    traceability: object | None,
    artifact_version_start: int,
    review_decision: dict[str, object] | None,
) -> dict[str, object]:
    snapshot_row = _snapshot_row(project_id, version_id, actor_id, snapshot)
    object_versions = tuple(
        AeirObjectVersionModel(
            id=uuid.uuid4(),
            object_row_id=row.id,
            model_version_id=version_id,
            object_id=row.object_id,
            version_number=version_number,
            version_document={
                "schema_version": "aeir-object-version-0.1",
                "object_id": row.object_id,
                "model_version_id": str(version_id),
                "object": row.source_document
                | {
                    "id": row.object_id,
                    "type": row.object_type,
                    "name": row.name,
                    "description": row.description,
                    "lifecycle_status": row.lifecycle_status,
                    "truth_status": row.truth_status,
                    "approval_status": row.approval_status,
                    "confidence": row.confidence,
                    "version": row.object_version,
                    "source_refs": row.source_refs,
                    "evidence_refs": row.evidence_refs,
                    "relationship_refs": row.relationship_refs,
                    "attributes": row.attributes,
                    "metadata": row.object_metadata,
                },
            },
            object_version_hash=specification_hash(
                {
                    "project_id": str(project_id),
                    "model_version_id": str(version_id),
                    "object_id": row.object_id,
                    "version_number": version_number,
                    "object_hash": specification_hash(row.source_document),
                }
            ),
            created_by=actor_id,
        )
        for row in object_rows
    )
    relationship_versions = tuple(
        AeirRelationshipVersionModel(
            id=uuid.uuid4(),
            relationship_row_id=row.id,
            model_version_id=version_id,
            relationship_id=row.relationship_id,
            version_number=version_number,
            version_document=row.relationship_document,
            relationship_version_hash=specification_hash(
                {
                    "project_id": str(project_id),
                    "model_version_id": str(version_id),
                    "relationship_id": row.relationship_id,
                    "version_number": version_number,
                    "relationship": row.relationship_document,
                }
            ),
            created_by=actor_id,
        )
        for row in relationship_rows
    )
    evidence_rows = _evidence_rows(
        project_id=project_id,
        version_id=version_id,
        actor_id=actor_id,
        object_rows=object_rows,
        relationship_rows=relationship_rows,
    )
    object_source_links = _object_source_link_rows(
        project_id=project_id,
        version_id=version_id,
        actor_id=actor_id,
        object_rows=object_rows,
    )
    relationship_source_links = _relationship_source_link_rows(
        project_id=project_id,
        version_id=version_id,
        actor_id=actor_id,
        relationship_rows=relationship_rows,
    )
    finding_rows = _validation_finding_rows(
        project_id=project_id,
        snapshot_row=snapshot_row,
        version_id=version_id,
        validation=validation,
    )
    question_rows = _clarification_question_rows(
        project_id=project_id,
        snapshot_row=snapshot_row,
        clarification=clarification,
    )
    answer_rows = _clarification_answer_rows(
        project_id=project_id,
        questions=question_rows,
        answer_batch=answer_batch,
    )
    ai_operation_rows = _ai_operation_rows(
        project_id=project_id,
        version_id=version_id,
        interpretation=interpretation,
    )
    artifact_rows, trace_rows = _artifact_rows(
        project_id=project_id,
        snapshot_row=snapshot_row,
        bundle=bundle,
        traceability=traceability,
        version_number=artifact_version_start,
        actor_id=actor_id,
    )
    decision_rows = _decision_rows(
        project_id=project_id,
        snapshot_row=snapshot_row,
        actor_id=actor_id,
        review_decision=review_decision,
    )
    return {
        "snapshot": snapshot_row,
        "object_versions": object_versions,
        "relationship_versions": relationship_versions,
        "evidence": evidence_rows,
        "object_source_links": object_source_links,
        "relationship_source_links": relationship_source_links,
        "validation_findings": finding_rows,
        "clarification_questions": question_rows,
        "clarification_answers": answer_rows,
        "ai_operations": ai_operation_rows,
        "artifact_versions": artifact_rows,
        "artifact_trace_links": trace_rows,
        "decisions": decision_rows,
    }


def _evidence_rows(
    *,
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    actor_id: str,
    object_rows: tuple[AeirObjectModel, ...],
    relationship_rows: tuple[AeirRelationshipModel, ...],
) -> tuple[AeirEvidenceModel, ...]:
    rows: list[AeirEvidenceModel] = []
    for row in object_rows:
        for source_ref in row.source_refs:
            document = {
                "schema_version": "aeir-evidence-0.1",
                "target_type": "object",
                "object_id": row.object_id,
                "evidence_ref": source_ref,
                "evidence_type": "source_reference",
                "source_refs": [source_ref],
            }
            rows.append(
                AeirEvidenceModel(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    model_version_id=version_id,
                    object_row_id=row.id,
                    relationship_row_id=None,
                    evidence_id=source_ref,
                    evidence_type="source_reference",
                    source_ref=source_ref,
                    evidence_document=document,
                    evidence_hash=specification_hash(
                        {
                            "project_id": str(project_id),
                            "model_version_id": str(version_id),
                            "object_row_id": str(row.id),
                            "evidence_type": "source_reference",
                            "source_ref": source_ref,
                        }
                    ),
                    created_by=actor_id,
                )
            )
        for evidence_ref in row.evidence_refs:
            document = {
                "schema_version": "aeir-evidence-0.1",
                "target_type": "object",
                "object_id": row.object_id,
                "evidence_ref": evidence_ref,
                "evidence_type": "object_evidence_ref",
                "source_refs": row.source_refs,
            }
            rows.append(
                AeirEvidenceModel(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    model_version_id=version_id,
                    object_row_id=row.id,
                    relationship_row_id=None,
                    evidence_id=evidence_ref,
                    evidence_type="object_evidence_ref",
                    source_ref=row.source_refs[0] if row.source_refs else None,
                    evidence_document=document,
                    evidence_hash=specification_hash(
                        {
                            "project_id": str(project_id),
                            "model_version_id": str(version_id),
                            "object_row_id": str(row.id),
                            "evidence_type": "object_evidence_ref",
                            "evidence_ref": evidence_ref,
                        }
                    ),
                    created_by=actor_id,
                )
            )
    for row in relationship_rows:
        document = row.relationship_document
        for source_ref in document.get("source_refs", []):
            evidence_document = {
                "schema_version": "aeir-evidence-0.1",
                "target_type": "relationship",
                "relationship_id": row.relationship_id,
                "evidence_ref": source_ref,
                "evidence_type": "source_reference",
                "source_refs": [source_ref],
            }
            rows.append(
                AeirEvidenceModel(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    model_version_id=version_id,
                    object_row_id=None,
                    relationship_row_id=row.id,
                    evidence_id=source_ref,
                    evidence_type="source_reference",
                    source_ref=source_ref,
                    evidence_document=evidence_document,
                    evidence_hash=specification_hash(
                        {
                            "project_id": str(project_id),
                            "model_version_id": str(version_id),
                            "relationship_row_id": str(row.id),
                            "evidence_type": "source_reference",
                            "source_ref": source_ref,
                        }
                    ),
                    created_by=actor_id,
                )
            )
        for evidence_ref in document.get("evidence_refs", []):
            source_refs = document.get("source_refs", [])
            evidence_document = {
                "schema_version": "aeir-evidence-0.1",
                "target_type": "relationship",
                "relationship_id": row.relationship_id,
                "evidence_ref": evidence_ref,
                "evidence_type": "relationship_evidence_ref",
                "source_refs": source_refs,
            }
            rows.append(
                AeirEvidenceModel(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    model_version_id=version_id,
                    object_row_id=None,
                    relationship_row_id=row.id,
                    evidence_id=evidence_ref,
                    evidence_type="relationship_evidence_ref",
                    source_ref=source_refs[0] if source_refs else None,
                    evidence_document=evidence_document,
                    evidence_hash=specification_hash(
                        {
                            "project_id": str(project_id),
                            "model_version_id": str(version_id),
                            "relationship_row_id": str(row.id),
                            "evidence_type": "relationship_evidence_ref",
                            "evidence_ref": evidence_ref,
                        }
                    ),
                    created_by=actor_id,
                )
            )
    return tuple(rows)


def _object_source_link_rows(
    *,
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    actor_id: str,
    object_rows: tuple[AeirObjectModel, ...],
) -> tuple[AeirObjectSourceLinkModel, ...]:
    rows: list[AeirObjectSourceLinkModel] = []
    for row in object_rows:
        for source_ref in row.source_refs:
            document = {
                "schema_version": "aeir-object-source-link-0.1",
                "object_id": row.object_id,
                "source_ref": source_ref,
                "link_type": "declared_source",
            }
            rows.append(
                AeirObjectSourceLinkModel(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    model_version_id=version_id,
                    object_row_id=row.id,
                    object_id=row.object_id,
                    source_ref=source_ref,
                    link_type="declared_source",
                    link_document=document,
                    link_hash=specification_hash(
                        {
                            "project_id": str(project_id),
                            "model_version_id": str(version_id),
                            "object_row_id": str(row.id),
                            "source_ref": source_ref,
                            "link_type": "declared_source",
                        }
                    ),
                    created_by=actor_id,
                )
            )
    return tuple(rows)


def _relationship_source_link_rows(
    *,
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    actor_id: str,
    relationship_rows: tuple[AeirRelationshipModel, ...],
) -> tuple[AeirRelationshipSourceLinkModel, ...]:
    rows: list[AeirRelationshipSourceLinkModel] = []
    for row in relationship_rows:
        for source_ref in row.relationship_document.get("source_refs", []):
            document = {
                "schema_version": "aeir-relationship-source-link-0.1",
                "relationship_id": row.relationship_id,
                "source_ref": source_ref,
                "link_type": "declared_source",
            }
            rows.append(
                AeirRelationshipSourceLinkModel(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    model_version_id=version_id,
                    relationship_row_id=row.id,
                    relationship_id=row.relationship_id,
                    source_ref=source_ref,
                    link_type="declared_source",
                    link_document=document,
                    link_hash=specification_hash(
                        {
                            "project_id": str(project_id),
                            "model_version_id": str(version_id),
                            "relationship_row_id": str(row.id),
                            "source_ref": source_ref,
                            "link_type": "declared_source",
                        }
                    ),
                    created_by=actor_id,
                )
            )
    return tuple(rows)


def _snapshot_row(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    actor_id: str,
    snapshot: object | None,
) -> AeirProjectSnapshotModel | None:
    if snapshot is None:
        return None
    document = snapshot.model_dump(mode="json")
    return AeirProjectSnapshotModel(
        id=uuid.uuid4(),
        project_id=project_id,
        model_version_id=version_id,
        snapshot_id=document["snapshot_id"],
        aepm_version=document["aepm_version"],
        aeir_version=document["aeir_version"],
        status=document["status"],
        object_versions=document["object_versions"],
        snapshot_document=document,
        snapshot_sha256=document["snapshot_sha256"],
        created_by=actor_id,
    )


def _validation_finding_rows(
    *,
    project_id: uuid.UUID,
    snapshot_row: AeirProjectSnapshotModel | None,
    version_id: uuid.UUID,
    validation: object | None,
) -> tuple[AeirValidationFindingModel, ...]:
    if validation is None:
        return ()
    return tuple(
        AeirValidationFindingModel(
            id=uuid.uuid4(),
            project_id=project_id,
            snapshot_row_id=None if snapshot_row is None else snapshot_row.id,
            model_version_id=version_id,
            rule_row_id=None,
            finding_id=finding.id,
            rule_id=finding.rule_id,
            severity=finding.severity,
            category=finding.category,
            blocking=finding.blocking,
            object_refs=list(finding.object_ids),
            finding_document=finding.model_dump(mode="json"),
            finding_hash=specification_hash(
                {
                    "project_id": str(project_id),
                    "snapshot_row_id": None if snapshot_row is None else str(snapshot_row.id),
                    "finding": finding.model_dump(mode="json"),
                }
            ),
        )
        for finding in validation.findings
    )


def _clarification_question_rows(
    *,
    project_id: uuid.UUID,
    snapshot_row: AeirProjectSnapshotModel | None,
    clarification: object | None,
) -> tuple[AeirClarificationQuestionModel, ...]:
    if clarification is None:
        return ()
    return tuple(
        AeirClarificationQuestionModel(
            id=uuid.uuid4(),
            project_id=project_id,
            snapshot_row_id=None if snapshot_row is None else snapshot_row.id,
            question_id=question.id,
            section=question.section,
            required=question.required,
            target_object_ids=list(question.target_object_ids),
            question_document=question.model_dump(mode="json"),
            question_hash=specification_hash(
                {
                    "project_id": str(project_id),
                    "snapshot_row_id": None if snapshot_row is None else str(snapshot_row.id),
                    "question": question.model_dump(mode="json"),
                }
            ),
        )
        for question in clarification.questions()
    )


def _clarification_answer_rows(
    *,
    project_id: uuid.UUID,
    questions: tuple[AeirClarificationQuestionModel, ...],
    answer_batch: object | None,
) -> tuple[AeirClarificationAnswerModel, ...]:
    if answer_batch is None:
        return ()
    question_ids = {item.question_id: item.id for item in questions}
    return tuple(
        AeirClarificationAnswerModel(
            id=uuid.uuid4(),
            question_row_id=question_ids[answer.question_id],
            project_id=project_id,
            respondent_id=answer_batch.respondent_id,
            resolution=answer.resolution,
            answer_document={
                "schema_version": "aeir-clarification-answer-0.1",
                "report_sha256": answer_batch.report_sha256,
                "base_model_sha256": answer_batch.base_model_sha256,
                "answer_batch_sha256": answer_batch.answer_batch_sha256,
                "answer": answer.model_dump(mode="json"),
            },
            answer_hash=specification_hash(
                {
                    "project_id": str(project_id),
                    "answer_batch_sha256": answer_batch.answer_batch_sha256,
                    "answer": answer.model_dump(mode="json"),
                }
            ),
        )
        for answer in answer_batch.answers
    )


def _ai_operation_rows(
    *,
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    interpretation: object | None,
) -> tuple[AeirAiOperationModel, ...]:
    if interpretation is None:
        return ()
    operation = interpretation.ai_operation
    document = operation.model_dump(mode="json")
    return (
        AeirAiOperationModel(
            id=uuid.uuid4(),
            project_id=project_id,
            model_version_id=version_id,
            model_provider=operation.model_provider,
            model_name=operation.model_name,
            operation_type=operation.operation_type,
            prompt_version=operation.prompt_version,
            input_source_refs=list(operation.input_source_refs),
            review_required=operation.review_required,
            operation_document=document,
            operation_sha256=operation.operation_sha256,
            generated_at=operation.generated_at,
        ),
    )


def _artifact_rows(
    *,
    project_id: uuid.UUID,
    snapshot_row: AeirProjectSnapshotModel | None,
    bundle: object | None,
    traceability: object | None,
    version_number: int,
    actor_id: str,
) -> tuple[tuple[AeirArtifactVersionModel, ...], tuple[AeirArtifactTraceLinkModel, ...]]:
    if snapshot_row is None or bundle is None:
        return (), ()
    contracts = {item.artifact_type: item for item in bundle.contracts}
    artifact_rows = tuple(
        AeirArtifactVersionModel(
            id=uuid.uuid4(),
            project_id=project_id,
            snapshot_row_id=snapshot_row.id,
            artifact_type=artifact.artifact_type,
            version_number=version_number,
            compiler_id=artifact.compiler_id,
            compiler_version=artifact.compiler_version,
            contract_hash=contracts[artifact.artifact_type].contract_sha256,
            compilation_status=artifact.compilation_status,
            output_format="markdown",
            artifact_document=artifact.model_dump(mode="json"),
            artifact_hash=artifact.artifact_sha256,
            created_by=actor_id,
        )
        for artifact in bundle.artifacts
    )
    if traceability is None:
        return artifact_rows, ()
    artifact_ids = {
        (row.artifact_type, row.artifact_hash): row.id
        for row in artifact_rows
    }
    trace_rows: list[AeirArtifactTraceLinkModel] = []
    for trace in traceability.section_traces:
        _extend_trace_rows(
            rows=trace_rows,
            artifact_ids=artifact_ids,
            artifact_type=trace.artifact_type,
            artifact_sha256=trace.artifact_sha256,
            section_id=trace.section_key,
            object_ids=trace.source_object_ids,
            relationship_ids=trace.relationship_ids,
            trace_type="section",
            document=trace.model_dump(mode="json"),
        )
    for trace in traceability.entry_traces:
        _extend_trace_rows(
            rows=trace_rows,
            artifact_ids=artifact_ids,
            artifact_type=trace.artifact_type,
            artifact_sha256=trace.artifact_sha256,
            section_id=f"{trace.section_key}:{trace.entry_index}",
            object_ids=trace.source_object_ids,
            relationship_ids=trace.relationship_ids,
            trace_type="entry",
            document=trace.model_dump(mode="json"),
        )
    return artifact_rows, tuple(trace_rows)


def _extend_trace_rows(
    *,
    rows: list[AeirArtifactTraceLinkModel],
    artifact_ids: dict[tuple[str, str], uuid.UUID],
    artifact_type: str,
    artifact_sha256: str,
    section_id: str,
    object_ids: tuple[str, ...],
    relationship_ids: tuple[str, ...],
    trace_type: str,
    document: dict[str, object],
) -> None:
    artifact_version_id = artifact_ids[(artifact_type, artifact_sha256)]
    relationship_id = relationship_ids[0] if len(relationship_ids) == 1 else None
    for object_id in object_ids:
        rows.append(
            AeirArtifactTraceLinkModel(
                id=uuid.uuid4(),
                artifact_version_id=artifact_version_id,
                artifact_section_id=section_id,
                object_id=object_id,
                relationship_id=relationship_id,
                trace_type=trace_type,
                trace_document=document,
                trace_hash=specification_hash(
                    {
                        "artifact_version_id": str(artifact_version_id),
                        "artifact_section_id": section_id,
                        "object_id": object_id,
                        "trace_type": trace_type,
                        "trace": document,
                    }
                ),
            )
        )


def _decision_rows(
    *,
    project_id: uuid.UUID,
    snapshot_row: AeirProjectSnapshotModel | None,
    actor_id: str,
    review_decision: dict[str, object] | None,
) -> tuple[AeirDecisionModel, ...]:
    if review_decision is None:
        return ()
    document = {
        "schema_version": "aeir-review-decision-0.1",
        "project_id": str(project_id),
        "snapshot_row_id": None if snapshot_row is None else str(snapshot_row.id),
        "reviewer_id": actor_id,
        **review_decision,
    }
    return (
        AeirDecisionModel(
            id=uuid.uuid4(),
            project_id=project_id,
            snapshot_row_id=None if snapshot_row is None else snapshot_row.id,
            object_id=None,
            decision_type="client_blueprint_review",
            decision=str(review_decision["decision"]),
            reviewer_id=actor_id,
            decision_document=document,
            decision_hash=specification_hash(document),
        ),
    )


class SqlAlchemyAeirRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def append_model(
        self,
        *,
        project_id: uuid.UUID,
        model: AeirProjectModel,
        actor_id: str,
        stored_source: StoredObject | None = None,
        original_filename: str = "client-manifest-aepm-0.1.json",
        media_type: str = "application/json",
        source_metadata: dict[str, object] | None = None,
    ) -> AeirWriteSet:
        project = await self.session.get(ProjectModel, project_id, with_for_update=True)
        if project is None:
            raise ValueError("AEIR-PROJECT-NOT-FOUND")
        version_number = (
            await self.session.scalar(
                select(func.max(AeirModelVersionModel.version_number)).where(
                    AeirModelVersionModel.project_id == project_id
                )
            )
            or 0
        ) + 1
        previous_event_hash = await self.session.scalar(
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
            stored_source=stored_source,
            original_filename=original_filename,
            media_type=media_type,
            source_metadata=source_metadata,
        )
        self.session.add(write_set.version)
        self.session.add_all(write_set.sources)
        self.session.add_all(write_set.objects)
        self.session.add_all(write_set.relationships)
        self.session.add(write_set.event)
        await self.session.flush()
        return write_set
