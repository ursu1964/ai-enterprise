from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from ai_enterprise.api.dependencies import ActorDependency, SessionDependency, SettingsDependency
from ai_enterprise.api.r4_ai_schemas import (
    CandidatePromotionResponse,
    CandidateReviewRequest,
    ClarificationAnswerRequest,
    InterpretationRunRequest,
    InterpretationRunResponse,
    NormalizationResponse,
    RegisterTextSourceRequest,
    SourceResponse,
)
from ai_enterprise.domain.hashing import hash_json
from ai_enterprise.domain.r4_interpretation import (
    CandidateReview,
    CandidateStatus,
    InterpretationRequest,
    PromptDefinition,
    R4OperationStatus,
    duplicate_candidate_findings,
    normalize_and_segment,
    prompt_injection_indicators,
    register_text_source,
)
from ai_enterprise.infrastructure.database.models import ProjectModel
from ai_enterprise.infrastructure.knowledge.models import (
    AeirChangeEventModel,
    AeirModelVersionModel,
    AeirObjectModel,
    AeirObjectVersionModel,
    AeirRelationshipModel,
    AeirRelationshipVersionModel,
    AeirSourceObjectModel,
    R4AiOperationFailureModel,
    R4AiOperationModel,
    R4AiProvenanceLinkModel,
    R4AiUsageRecordModel,
    R4CandidateObjectModel,
    R4CandidatePromotionModel,
    R4CandidateRelationshipModel,
    R4CandidateReviewModel,
    R4CandidateSourceLinkModel,
    R4CandidateValidationResultModel,
    R4ClarificationQuestionModel,
    R4PromptVersionModel,
    R4SourceNormalizationModel,
    R4SourceSegmentModel,
    R4UncertaintyRecordModel,
)
from ai_enterprise.infrastructure.r4_ai.provider import (
    R4ProviderError,
    create_r4_provider,
    r4_provider_config_from_settings,
)
from ai_enterprise.infrastructure.r4_ai.retry import R4RetryPolicy, execute_with_retries
from ai_enterprise.infrastructure.r4_ai.security import (
    contains_unredacted_secret,
    redact_source_segments,
)

router = APIRouter(prefix="/projects", tags=["r4-ai-interpretation"])


def _require_human(actor: object) -> None:
    if getattr(actor, "actor_type", None) != "human":
        raise HTTPException(status_code=403, detail="Human project authority is required")


@router.post("/{project_id}/sources", response_model=SourceResponse)
async def register_source(
    project_id: uuid.UUID,
    request: RegisterTextSourceRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> SourceResponse:
    _require_human(actor)
    await _project(session, project_id)
    source_id = await _next_source_id(session, project_id)
    registered = register_text_source(
        source_id=source_id,
        project_id=str(project_id),
        name=request.name,
        text=request.text,
        captured_by=actor.subject,
        media_type=request.media_type,
        language=request.language,
    )
    source_row = AeirSourceObjectModel(
        id=uuid.uuid4(),
        project_id=project_id,
        storage_provider="database",
        bucket="r4-sources",
        object_key=f"{project_id}/{source_id}.txt",
        original_filename=f"{source_id}.txt",
        media_type=request.media_type,
        content_sha256=registered.checksum,
        size_bytes=len(request.text.encode("utf-8")),
        source_metadata={
            "r4_source": registered.model_dump(mode="json"),
            "stage": "r4_source_registration",
            "prompt_injection_indicators": list(prompt_injection_indicators(request.text)),
        },
        uploaded_by=actor.subject,
    )
    event = await _event(
        session,
        project_id=project_id,
        actor_id=actor.subject,
        event_type="r4.source.registered",
        payload={"source_id": source_id, "checksum": registered.checksum},
    )
    session.add(source_row)
    session.add(event)
    await session.commit()
    return SourceResponse(
        project_id=project_id,
        source_id=source_id,
        processing_status=registered.processing_status,
        checksum=registered.checksum,
        prompt_injection_indicators=list(prompt_injection_indicators(request.text)),
    )


@router.post(
    "/{project_id}/sources/{source_id}/normalization-runs",
    response_model=NormalizationResponse,
)
async def normalize_source(
    project_id: uuid.UUID,
    source_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> NormalizationResponse:
    _require_human(actor)
    source_row = await _source_row(session, project_id, source_id)
    source_document = source_row.source_metadata["r4_source"]
    registered = register_text_source(
        source_id=source_id,
        project_id=str(project_id),
        name=source_document["name"],
        text=source_document["text"],
        captured_by=source_document["captured_by"],
        media_type=source_document["media_type"],
        language=source_document["language"],
    )
    normalized = normalize_and_segment(registered)
    normalization_row = R4SourceNormalizationModel(
        id=uuid.uuid4(),
        project_id=project_id,
        source_row_id=source_row.id,
        source_id=source_id,
        normalization_version=normalized.normalization_version,
        language=normalized.language,
        character_count=normalized.character_count,
        segment_count=normalized.segment_count,
        normalized_document=normalized.model_dump(mode="json"),
        checksum=normalized.checksum,
        created_by=actor.subject,
    )
    segment_rows = [
        R4SourceSegmentModel(
            id=uuid.uuid4(),
            project_id=project_id,
            normalization_id=normalization_row.id,
            source_id=source_id,
            segment_id=segment.id,
            sequence=segment.sequence,
            segment_type=segment.segment_type,
            heading_path=list(segment.heading_path),
            text=segment.text,
            start_offset=segment.start_offset,
            end_offset=segment.end_offset,
            checksum=segment.checksum,
        )
        for segment in normalized.segments
    ]
    event = await _event(
        session,
        project_id=project_id,
        actor_id=actor.subject,
        event_type="r4.source.normalized",
        payload={"source_id": source_id, "segment_count": len(segment_rows)},
    )
    source_row.source_metadata = source_row.source_metadata | {
        "r4_source": source_document | {"processing_status": "normalized"}
    }
    session.add(normalization_row)
    session.add_all(segment_rows)
    session.add(event)
    await session.commit()
    return NormalizationResponse(
        project_id=project_id,
        source_id=source_id,
        normalization_id=normalization_row.id,
        checksum=normalized.checksum,
        segment_count=len(segment_rows),
        segments=[segment.model_dump(mode="json") for segment in normalized.segments],
    )


@router.get("/{project_id}/sources/{source_id}/segments")
async def list_segments(
    project_id: uuid.UUID,
    source_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> list[dict[str, Any]]:
    _require_human(actor)
    rows = (
        await session.scalars(
            select(R4SourceSegmentModel)
            .where(
                R4SourceSegmentModel.project_id == project_id,
                R4SourceSegmentModel.source_id == source_id,
            )
            .order_by(R4SourceSegmentModel.sequence)
        )
    ).all()
    return [_segment_payload(row) for row in rows]


@router.post("/{project_id}/interpretation-runs", response_model=InterpretationRunResponse)
async def start_interpretation(
    project_id: uuid.UUID,
    request: InterpretationRunRequest,
    session: SessionDependency,
    actor: ActorDependency,
    settings: SettingsDependency,
) -> InterpretationRunResponse:
    _require_human(actor)
    await _project(session, project_id)
    segments = (
        await session.scalars(
            select(R4SourceSegmentModel)
            .where(
                R4SourceSegmentModel.project_id == project_id,
                R4SourceSegmentModel.source_id.in_(request.source_ids),
            )
            .order_by(R4SourceSegmentModel.source_id, R4SourceSegmentModel.sequence)
        )
    ).all()
    if not segments:
        raise HTTPException(
            status_code=422,
            detail="Source must be normalized before interpretation",
        )
    operation_id = await _next_operation_id(session, project_id)
    prompt = PromptDefinition()
    prompt_row = await _ensure_prompt(session, prompt)
    domain_segments = tuple(_domain_segment(row) for row in segments)
    redaction = redact_source_segments(
        domain_segments,
        enabled=settings.r4_interpretation_redact_secrets,
    )
    request_contract = InterpretationRequest(
        operation_id=operation_id,
        project_id=str(project_id),
        source_segments=redaction.segments,
        prompt=prompt,
        parameters={
            "temperature": settings.r4_interpretation_temperature,
            "max_output_tokens": settings.r4_interpretation_max_tokens,
            "secret_redaction_applied": redaction.redacted,
        },
        correlation_id=str(uuid.uuid4()),
    )
    adapter = create_r4_provider(r4_provider_config_from_settings(settings))

    async def persist_failure(
        failure_type: str,
        retry_count: int,
        final_status: str,
        error_summary: str,
    ) -> None:
        failure_row = _failure_row(
            project_id=project_id,
            operation_id=operation_id,
            operation_row_id=None,
            failure_type=failure_type,
            retry_count=retry_count,
            final_status=final_status,
            error_summary=error_summary,
        )
        event = await _event(
            session,
            project_id=project_id,
            actor_id=actor.subject,
            event_type=f"r4.interpretation.{final_status}",
            payload=failure_row.failure_document,
        )
        session.add(failure_row)
        session.add(event)
        await session.commit()

    try:
        execution = await execute_with_retries(
            adapter,
            request_contract,
            known_segment_ids={row.segment_id for row in segments},
            policy=R4RetryPolicy(
                provider_retries=settings.r4_interpretation_provider_retries,
                schema_repair_attempts=settings.r4_interpretation_schema_repair_attempts,
            ),
            on_failure=persist_failure,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except R4ProviderError as exc:
        failure_row = _failure_row(
            project_id=project_id,
            operation_id=operation_id,
            operation_row_id=None,
            failure_type="provider_error",
            retry_count=settings.r4_interpretation_provider_retries,
            final_status=R4OperationStatus.PROVIDER_FAILED,
            error_summary=str(exc),
        )
        event = await _event(
            session,
            project_id=project_id,
            actor_id=actor.subject,
            event_type="r4.interpretation.provider_failed",
            payload=failure_row.failure_document,
        )
        session.add(failure_row)
        session.add(event)
        await session.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    adapter_result = execution.adapter_result
    extraction = execution.extraction
    if contains_unredacted_secret(adapter_result.structured_output):
        failure_row = _failure_row(
            project_id=project_id,
            operation_id=operation_id,
            operation_row_id=None,
            failure_type="secret_policy",
            retry_count=0,
            final_status=R4OperationStatus.REJECTED,
            error_summary="AI output contains unredacted secret-like material",
        )
        session.add(failure_row)
        await session.commit()
        raise HTTPException(
            status_code=422,
            detail="AI output contains unredacted secret-like material",
        )
    duplicate_findings = duplicate_candidate_findings(extraction)
    operation_document = {
        "operation_id": operation_id,
        "prompt_row_id": str(prompt_row.id),
        "adapter_result": adapter_result.model_dump(mode="json"),
        "duplicate_findings": list(duplicate_findings),
        "provider_retry_count": execution.provider_retry_count,
        "schema_repair_count": execution.schema_repair_count,
        "secret_redaction": {
            "applied": redaction.redacted,
            "indicators": list(redaction.indicators),
        },
    }
    operation_row = R4AiOperationModel(
        id=uuid.uuid4(),
        project_id=project_id,
        operation_id=operation_id,
        operation_type=request.operation_type,
        provider=adapter_result.model_metadata.get("provider", adapter.name),
        model=adapter_result.model_metadata.get("model", adapter.model_name),
        prompt_id=prompt.prompt_id,
        prompt_version=prompt.version,
        response_schema_id="AI-EXTRACTION-RESPONSE",
        response_schema_version="0.1",
        status=(
            R4OperationStatus.COMPLETED
            if not duplicate_findings
            else R4OperationStatus.COMPLETED_WITH_WARNINGS
        ),
        source_ids=request.source_ids,
        segment_ids=[row.segment_id for row in segments],
        parameters=request_contract.parameters,
        operation_document=operation_document,
        operation_hash=hash_json(operation_document),
        review_required=True,
        created_by=actor.subject,
    )
    usage_row = R4AiUsageRecordModel(
        id=uuid.uuid4(),
        operation_row_id=operation_row.id,
        project_id=project_id,
        provider=adapter_result.model_metadata.get("provider", adapter.name),
        model=adapter_result.model_metadata.get("model", adapter.model_name),
        input_tokens=adapter_result.input_token_count,
        output_tokens=adapter_result.output_token_count,
        cached_input_tokens=0,
        execution_seconds=adapter_result.latency_ms / 1000,
        estimated_cost=0.0,
        currency="EUR",
        usage_document=adapter_result.model_dump(mode="json"),
    )
    candidate_rows, relationship_rows, source_links, provenance_links = _candidate_rows(
        project_id, operation_row, extraction
    )
    validation_rows = [
        R4CandidateValidationResultModel(
            id=uuid.uuid4(),
            project_id=project_id,
            ai_operation_row_id=operation_row.id,
            candidate_id=row.candidate_id,
            status="valid" if not duplicate_findings else "valid_with_warnings",
            findings=list(duplicate_findings),
            result_hash=hash_json(
                {
                    "project_id": str(project_id),
                    "operation_id": operation_id,
                    "candidate_id": row.candidate_id,
                    "findings": list(duplicate_findings),
                }
            ),
        )
        for row in [*candidate_rows, *relationship_rows]
    ]
    uncertainty_rows = _uncertainty_rows(project_id, operation_row, extraction)
    clarification_rows = _clarification_rows(project_id, operation_row, extraction)
    event = await _event(
        session,
        project_id=project_id,
        actor_id=actor.subject,
        event_type="r4.interpretation.completed",
        payload={
            "operation_id": operation_id,
            "candidate_object_count": len(candidate_rows),
            "candidate_relationship_count": len(extraction.candidate_relationships),
        },
    )
    source_rows = (
        await session.scalars(
            select(AeirSourceObjectModel).where(
                AeirSourceObjectModel.project_id == project_id,
                AeirSourceObjectModel.source_metadata["stage"].astext
                == "r4_source_registration",
            )
        )
    ).all()
    for source_row in source_rows:
        source_document = source_row.source_metadata.get("r4_source", {})
        if source_document.get("source_id") in request.source_ids:
            source_row.source_metadata = source_row.source_metadata | {
                "r4_source": source_document | {"processing_status": "interpreted"}
            }
    session.add(operation_row)
    session.add(usage_row)
    session.add_all(
        [
            *candidate_rows,
            *relationship_rows,
            *source_links,
            *validation_rows,
            *uncertainty_rows,
        ]
    )
    session.add_all([*clarification_rows, *provenance_links])
    session.add(event)
    await session.commit()
    return InterpretationRunResponse(
        project_id=project_id,
        operation_id=operation_id,
        status=operation_row.status,
        candidate_object_count=len(candidate_rows),
        candidate_relationship_count=len(extraction.candidate_relationships),
        ambiguity_count=len(extraction.ambiguities),
        assumption_count=len(extraction.assumptions),
        probable_contradiction_count=len(extraction.probable_contradictions),
        clarification_question_count=len(extraction.clarification_candidates),
        usage=usage_row.usage_document,
    )


@router.get("/{project_id}/interpretation-runs/{operation_id}")
async def get_interpretation_run(
    project_id: uuid.UUID,
    operation_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, Any]:
    _require_human(actor)
    operation = await session.scalar(
        select(R4AiOperationModel).where(
            R4AiOperationModel.project_id == project_id,
            R4AiOperationModel.operation_id == operation_id,
        )
    )
    if operation is None:
        raise HTTPException(status_code=404, detail="Interpretation run not found")
    return operation.operation_document


@router.get("/{project_id}/candidates")
async def list_candidates(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
    object_type: str | None = None,
    candidate_status: str | None = None,
    truth_status: str | None = None,
    ai_operation: str | None = None,
    source: str | None = None,
    validation_status: str | None = None,
    confidence_min: float | None = None,
    confidence_max: float | None = None,
) -> list[dict[str, Any]]:
    _require_human(actor)
    object_statement = select(R4CandidateObjectModel).where(
        R4CandidateObjectModel.project_id == project_id
    )
    relationship_statement = select(R4CandidateRelationshipModel).where(
        R4CandidateRelationshipModel.project_id == project_id
    )
    if object_type is not None:
        object_statement = object_statement.where(
            R4CandidateObjectModel.proposed_object_type == object_type
        )
        relationship_statement = relationship_statement.where(
            R4CandidateRelationshipModel.relationship_type == object_type
        )
    if candidate_status is not None:
        object_statement = object_statement.where(
            R4CandidateObjectModel.candidate_status == candidate_status
        )
        relationship_statement = relationship_statement.where(
            R4CandidateRelationshipModel.candidate_status == candidate_status
        )
    if truth_status is not None:
        object_statement = object_statement.where(
            R4CandidateObjectModel.truth_status == truth_status
        )
        relationship_statement = relationship_statement.where(
            R4CandidateRelationshipModel.truth_status == truth_status
        )
    if validation_status is not None:
        object_statement = object_statement.where(
            R4CandidateObjectModel.deterministic_validation_status == validation_status
        )
        relationship_statement = relationship_statement.where(
            R4CandidateRelationshipModel.schema_status == validation_status
        )
    if confidence_min is not None:
        object_statement = object_statement.where(
            R4CandidateObjectModel.confidence >= confidence_min
        )
        relationship_statement = relationship_statement.where(
            R4CandidateRelationshipModel.confidence >= confidence_min
        )
    if confidence_max is not None:
        object_statement = object_statement.where(
            R4CandidateObjectModel.confidence <= confidence_max
        )
        relationship_statement = relationship_statement.where(
            R4CandidateRelationshipModel.confidence <= confidence_max
        )
    rows = [
        *(await session.scalars(object_statement)).all(),
        *(await session.scalars(relationship_statement)).all(),
    ]
    if ai_operation is not None:
        rows = [row for row in rows if row.payload.get("ai_operation_id") == ai_operation]
    if source is not None:
        rows = [
            row
            for row in rows
            if any(
                support.get("source_id") == source
                for support in row.payload.get("source_support", [])
            )
        ]
    return [
        row.payload
        | {
            "candidate_status": row.candidate_status,
            "schema_status": row.schema_status,
        }
        for row in sorted(rows, key=lambda item: item.candidate_id)
    ]


@router.post("/{project_id}/candidates/{candidate_id}/reviews")
async def review_candidate(
    project_id: uuid.UUID,
    candidate_id: str,
    request: CandidateReviewRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, Any]:
    _require_human(actor)
    candidate = await _candidate(session, project_id, candidate_id)
    review_id = await _next_review_id(session, project_id)
    review = CandidateReview(
        id=review_id,
        candidate_id=candidate_id,
        reviewer_id=actor.subject,
        action=request.action,
        original_payload_checksum=candidate.candidate_hash,
        approved_payload_checksum=hash_json(
            {"payload": candidate.payload, "edits": request.edits}
        ),
        edits=tuple(request.edits),
        rationale=request.rationale,
    )
    candidate.candidate_status = _reviewed_candidate_status(request.action)
    if hasattr(candidate, "reviewed_at"):
        candidate.reviewed_at = datetime.now(UTC)
    if hasattr(candidate, "reviewed_by"):
        candidate.reviewed_by = actor.subject
    review_row = R4CandidateReviewModel(
        id=uuid.uuid4(),
        project_id=project_id,
        candidate_id=candidate_id,
        review_id=review_id,
        reviewer_id=actor.subject,
        action=request.action,
        review_document=review.model_dump(mode="json"),
        review_hash=hash_json(review.model_dump(mode="json")),
    )
    event = await _event(
        session,
        project_id=project_id,
        actor_id=actor.subject,
        event_type="r4.candidate.reviewed",
        payload=review.model_dump(mode="json"),
    )
    session.add(review_row)
    session.add(event)
    await session.commit()
    return review.model_dump(mode="json")


@router.post(
    "/{project_id}/candidates/{candidate_id}/promotion",
    response_model=CandidatePromotionResponse,
)
async def promote_candidate(
    project_id: uuid.UUID,
    candidate_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> CandidatePromotionResponse:
    _require_human(actor)
    candidate = await _candidate(session, project_id, candidate_id)
    review = await session.scalar(
        select(R4CandidateReviewModel)
        .where(
            R4CandidateReviewModel.project_id == project_id,
            R4CandidateReviewModel.candidate_id == candidate_id,
            R4CandidateReviewModel.action.in_(["approve", "approve_with_edits"]),
        )
        .order_by(R4CandidateReviewModel.created_at.desc())
        .limit(1)
    )
    if review is None:
        raise HTTPException(status_code=422, detail="Candidate requires approval before promotion")
    if candidate.candidate_status not in {
        CandidateStatus.PENDING_REVIEW,
        CandidateStatus.APPROVED,
        CandidateStatus.APPROVED_WITH_EDITS,
    }:
        raise HTTPException(status_code=422, detail="Candidate status cannot be promoted")
    if isinstance(candidate, R4CandidateRelationshipModel):
        return await _promote_relationship_candidate(
            project_id=project_id,
            candidate=candidate,
            review=review,
            session=session,
            actor=actor,
        )
    canonical_object_id = candidate.proposed_object_id
    model_version = await _latest_model_version(session, project_id)
    if model_version is None:
        raise HTTPException(
            status_code=422,
            detail="Candidate promotion requires an existing canonical model version",
        )
    existing = await session.scalar(
        select(AeirObjectModel).where(
            AeirObjectModel.model_version_id == model_version.id,
            AeirObjectModel.object_id == canonical_object_id,
        )
    )
    if existing is not None and existing.approval_status == "approved":
        raise HTTPException(
            status_code=422,
            detail="AI cannot directly modify approved canonical knowledge",
        )
    source_refs = sorted(
        {
            support["source_id"]
            for support in candidate.payload.get("source_support", [])
            if "source_id" in support
        }
    ) or [candidate.payload.get("ai_operation_id", "AIOP-0000")]
    evidence_refs = [candidate.payload.get("ai_operation_id", "AIOP-0000"), review.review_id]
    object_row = existing or AeirObjectModel(
        id=uuid.uuid4(),
        model_version_id=model_version.id,
        object_id=canonical_object_id,
        object_type=str(candidate.proposed_object_type).lower(),
        name=candidate.payload["name"],
        description=candidate.payload["description"],
        lifecycle_status="draft",
        truth_status=candidate.truth_status,
        approval_status="approved",
        confidence=candidate.confidence,
        object_version="0.1.0",
        source_document={
            "kind": "ai_operation",
            "reference": candidate.payload.get("ai_operation_id"),
            "manifest_sha256": model_version.source_manifest_sha256,
            "evidence_references": evidence_refs,
        },
        source_refs=source_refs,
        evidence_refs=evidence_refs,
        relationship_refs=[],
        attributes=candidate.payload.get("attributes", {}),
        object_metadata={
            "origin_candidate_id": candidate_id,
            "ai_derived": True,
            "review_id": review.review_id,
        },
    )
    version_number = await _next_object_version(session, object_row.id) if existing else 1
    promotion_document = {
        "schema_version": "r4-candidate-promotion-0.1",
        "candidate_id": candidate_id,
        "canonical_object_id": canonical_object_id,
        "review_hash": review.review_hash,
        "ai_provenance": candidate.payload.get("ai_operation_id"),
    }
    promotion_row = R4CandidatePromotionModel(
        id=uuid.uuid4(),
        project_id=project_id,
        candidate_id=candidate_id,
        canonical_object_id=canonical_object_id,
        canonical_relationship_id=None,
        promoted_by=actor.subject,
        promotion_document=promotion_document,
        promotion_hash=hash_json(promotion_document),
    )
    version_row = AeirObjectVersionModel(
        id=uuid.uuid4(),
        object_row_id=object_row.id,
        model_version_id=model_version.id,
        object_id=canonical_object_id,
        version_number=version_number,
        version_document={
            "schema_version": "aeir-object-version-0.1",
            "object_id": canonical_object_id,
            "object": candidate.payload,
            "origin_candidate_id": candidate_id,
        },
        object_version_hash=hash_json(
            {
                "project_id": str(project_id),
                "candidate_id": candidate_id,
                "canonical_object_id": canonical_object_id,
            }
        ),
        created_by=actor.subject,
    )
    event = await _event(
        session,
        project_id=project_id,
        actor_id=actor.subject,
        event_type="r4.candidate.promoted",
        payload=promotion_document,
    )
    if existing is None:
        session.add(object_row)
    candidate.candidate_status = CandidateStatus.PROMOTED
    session.add(promotion_row)
    session.add(version_row)
    session.add(event)
    await session.commit()
    return CandidatePromotionResponse(
        project_id=project_id,
        candidate_id=candidate_id,
        status="promoted",
        canonical_object_id=canonical_object_id,
        promotion_hash=promotion_row.promotion_hash,
    )


async def _promote_relationship_candidate(
    *,
    project_id: uuid.UUID,
    candidate: R4CandidateRelationshipModel,
    review: R4CandidateReviewModel,
    session: Any,
    actor: Any,
) -> CandidatePromotionResponse:
    model_version = await _latest_model_version(session, project_id)
    if model_version is None:
        raise HTTPException(
            status_code=422,
            detail="Candidate promotion requires an existing canonical model version",
        )
    source_promotion = await session.scalar(
        select(R4CandidatePromotionModel).where(
            R4CandidatePromotionModel.project_id == project_id,
            R4CandidatePromotionModel.candidate_id == candidate.source_candidate_ref,
            R4CandidatePromotionModel.canonical_object_id.is_not(None),
        )
    )
    target_promotion = await session.scalar(
        select(R4CandidatePromotionModel).where(
            R4CandidatePromotionModel.project_id == project_id,
            R4CandidatePromotionModel.candidate_id == candidate.target_candidate_ref,
            R4CandidatePromotionModel.canonical_object_id.is_not(None),
        )
    )
    if source_promotion is None or target_promotion is None:
        raise HTTPException(
            status_code=422,
            detail="Relationship promotion requires promoted source and target object candidates",
        )
    source_object = await session.scalar(
        select(AeirObjectModel).where(
            AeirObjectModel.model_version_id == model_version.id,
            AeirObjectModel.object_id == source_promotion.canonical_object_id,
        )
    )
    target_object = await session.scalar(
        select(AeirObjectModel).where(
            AeirObjectModel.model_version_id == model_version.id,
            AeirObjectModel.object_id == target_promotion.canonical_object_id,
        )
    )
    if source_object is None or target_object is None:
        raise HTTPException(
            status_code=422,
            detail="Promoted relationship endpoints are missing from canonical AEIR",
        )
    existing = await session.scalar(
        select(AeirRelationshipModel).where(
            AeirRelationshipModel.model_version_id == model_version.id,
            AeirRelationshipModel.relationship_type == candidate.relationship_type,
            AeirRelationshipModel.source_object_id == source_object.id,
            AeirRelationshipModel.target_object_id == target_object.id,
        )
    )
    if existing is not None and existing.approval_status == "approved":
        raise HTTPException(
            status_code=422,
            detail="AI cannot directly modify approved canonical knowledge",
        )
    relationship_id = (
        existing.relationship_id if existing is not None else await _next_relationship_id(
            session, model_version.id
        )
    )
    evidence_refs = [candidate.payload.get("ai_operation_id", "AIOP-0000"), review.review_id]
    relationship_document = {
        "schema_version": "aeir-relationship-0.1",
        "id": relationship_id,
        "relationship_type": candidate.relationship_type,
        "source_object_id": source_object.object_id,
        "target_object_id": target_object.object_id,
        "truth_status": candidate.truth_status,
        "approval_status": "approved",
        "confidence": candidate.confidence,
        "source_refs": [
            support["source_id"]
            for support in candidate.payload.get("source_support", [])
            if "source_id" in support
        ],
        "evidence_refs": evidence_refs,
        "origin_candidate_id": candidate.candidate_id,
    }
    relationship_row = existing or AeirRelationshipModel(
        id=uuid.uuid4(),
        model_version_id=model_version.id,
        relationship_id=relationship_id,
        relationship_type=candidate.relationship_type,
        source_object_id=source_object.id,
        target_object_id=target_object.id,
        lifecycle_status="draft",
        truth_status=candidate.truth_status,
        approval_status="approved",
        confidence=candidate.confidence,
        valid_from="2026-08-05",
        valid_to=None,
        relationship_document=relationship_document,
    )
    version_number = (
        await _next_relationship_version(session, relationship_row.id) if existing else 1
    )
    promotion_document = {
        "schema_version": "r4-candidate-promotion-0.1",
        "candidate_id": candidate.candidate_id,
        "canonical_relationship_id": relationship_id,
        "source_canonical_object_id": source_object.object_id,
        "target_canonical_object_id": target_object.object_id,
        "review_hash": review.review_hash,
        "ai_provenance": candidate.payload.get("ai_operation_id"),
    }
    promotion_row = R4CandidatePromotionModel(
        id=uuid.uuid4(),
        project_id=project_id,
        candidate_id=candidate.candidate_id,
        canonical_object_id=None,
        canonical_relationship_id=relationship_id,
        promoted_by=actor.subject,
        promotion_document=promotion_document,
        promotion_hash=hash_json(promotion_document),
    )
    version_row = AeirRelationshipVersionModel(
        id=uuid.uuid4(),
        relationship_row_id=relationship_row.id,
        model_version_id=model_version.id,
        relationship_id=relationship_id,
        version_number=version_number,
        version_document=relationship_document,
        relationship_version_hash=hash_json(
            {
                "project_id": str(project_id),
                "candidate_id": candidate.candidate_id,
                "canonical_relationship_id": relationship_id,
            }
        ),
        created_by=actor.subject,
    )
    event = await _event(
        session,
        project_id=project_id,
        actor_id=actor.subject,
        event_type="r4.candidate.promoted",
        payload=promotion_document,
    )
    if existing is None:
        session.add(relationship_row)
    candidate.candidate_status = CandidateStatus.PROMOTED
    session.add(promotion_row)
    session.add(version_row)
    session.add(event)
    await session.commit()
    return CandidatePromotionResponse(
        project_id=project_id,
        candidate_id=candidate.candidate_id,
        status="promoted",
        canonical_relationship_id=relationship_id,
        promotion_hash=promotion_row.promotion_hash,
    )


@router.get("/{project_id}/ambiguities")
async def list_ambiguities(
    project_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> list[dict[str, Any]]:
    return await _list_uncertainty(project_id, "ambiguity", session, actor)


@router.get("/{project_id}/assumptions")
async def list_assumptions(
    project_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> list[dict[str, Any]]:
    return await _list_uncertainty(project_id, "assumption", session, actor)


@router.get("/{project_id}/probable-contradictions")
async def list_probable_contradictions(
    project_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> list[dict[str, Any]]:
    return await _list_uncertainty(project_id, "probable_contradiction", session, actor)


@router.get("/{project_id}/clarification-questions")
async def list_r4_clarification_questions(
    project_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> list[dict[str, Any]]:
    _require_human(actor)
    rows = (
        await session.scalars(
            select(R4ClarificationQuestionModel)
            .where(R4ClarificationQuestionModel.project_id == project_id)
            .order_by(R4ClarificationQuestionModel.question_id)
        )
    ).all()
    return [row.question_document for row in rows]


@router.post("/{project_id}/clarification-questions/{question_id}/answers")
async def answer_r4_clarification_question(
    project_id: uuid.UUID,
    question_id: str,
    request: ClarificationAnswerRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, Any]:
    _require_human(actor)
    answer_document = {
        "question_id": question_id,
        "answer": request.answer,
        "answered_by": request.answered_by or actor.subject,
    }
    event = await _event(
        session,
        project_id=project_id,
        actor_id=actor.subject,
        event_type="r4.clarification.answer.recorded",
        payload=answer_document,
    )
    session.add(event)
    await session.commit()
    return {"project_id": str(project_id), **answer_document, "status": "answered"}


@router.get("/{project_id}/ai-usage")
async def get_ai_usage(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, Any]:
    _require_human(actor)
    rows = (
        await session.scalars(
            select(R4AiUsageRecordModel).where(R4AiUsageRecordModel.project_id == project_id)
        )
    ).all()
    return {
        "project_id": str(project_id),
        "operation_count": len(rows),
        "input_tokens": sum(row.input_tokens for row in rows),
        "output_tokens": sum(row.output_tokens for row in rows),
        "estimated_cost": sum(row.estimated_cost for row in rows),
        "currency": "EUR",
    }


async def _project(session: Any, project_id: uuid.UUID) -> ProjectModel:
    project = await session.get(ProjectModel, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _source_row(session: Any, project_id: uuid.UUID, source_id: str) -> AeirSourceObjectModel:
    row = await session.scalar(
        select(AeirSourceObjectModel).where(
            AeirSourceObjectModel.project_id == project_id,
            AeirSourceObjectModel.source_metadata["r4_source"]["source_id"].astext == source_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return row


async def _candidate(
    session: Any, project_id: uuid.UUID, candidate_id: str
) -> R4CandidateObjectModel | R4CandidateRelationshipModel:
    row = await session.scalar(
        select(R4CandidateObjectModel).where(
            R4CandidateObjectModel.project_id == project_id,
            R4CandidateObjectModel.candidate_id == candidate_id,
        )
    )
    if row is None:
        row = await session.scalar(
            select(R4CandidateRelationshipModel).where(
                R4CandidateRelationshipModel.project_id == project_id,
                R4CandidateRelationshipModel.candidate_id == candidate_id,
            )
        )
    if row is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return row


def _reviewed_candidate_status(action: str) -> CandidateStatus:
    if action == "approve":
        return CandidateStatus.APPROVED
    if action == "approve_with_edits":
        return CandidateStatus.APPROVED_WITH_EDITS
    if action == "reject":
        return CandidateStatus.REJECTED
    if action == "defer":
        return CandidateStatus.DEFERRED
    if action == "request_clarification":
        return CandidateStatus.DEFERRED
    return CandidateStatus.PENDING_REVIEW


async def _next_source_id(session: Any, project_id: uuid.UUID) -> str:
    value = await session.scalar(
        select(func.count(AeirSourceObjectModel.id)).where(
            AeirSourceObjectModel.project_id == project_id,
            AeirSourceObjectModel.source_metadata["stage"].astext == "r4_source_registration",
        )
    )
    return f"SRC-{int(value or 0) + 2:03d}"


async def _next_operation_id(session: Any, project_id: uuid.UUID) -> str:
    value = await session.scalar(
        select(func.count(R4AiOperationModel.id)).where(R4AiOperationModel.project_id == project_id)
    )
    return f"AIOP-{int(value or 0) + 1:04d}"


async def _next_review_id(session: Any, project_id: uuid.UUID) -> str:
    value = await session.scalar(
        select(func.count(R4CandidateReviewModel.id)).where(
            R4CandidateReviewModel.project_id == project_id
        )
    )
    return f"REV-{int(value or 0) + 1:04d}"


async def _latest_model_version(
    session: Any,
    project_id: uuid.UUID,
) -> AeirModelVersionModel | None:
    return await session.scalar(
        select(AeirModelVersionModel)
        .where(AeirModelVersionModel.project_id == project_id)
        .order_by(AeirModelVersionModel.version_number.desc())
        .limit(1)
    )


async def _next_object_version(session: Any, object_row_id: uuid.UUID) -> int:
    value = await session.scalar(
        select(func.max(AeirObjectVersionModel.version_number)).where(
            AeirObjectVersionModel.object_row_id == object_row_id
        )
    )
    return int(value or 0) + 1


async def _next_relationship_id(session: Any, model_version_id: uuid.UUID) -> str:
    value = await session.scalar(
        select(func.count(AeirRelationshipModel.id)).where(
            AeirRelationshipModel.model_version_id == model_version_id
        )
    )
    return f"REL-{int(value or 0) + 1:03d}"


async def _next_relationship_version(session: Any, relationship_row_id: uuid.UUID) -> int:
    value = await session.scalar(
        select(func.max(AeirRelationshipVersionModel.version_number)).where(
            AeirRelationshipVersionModel.relationship_row_id == relationship_row_id
        )
    )
    return int(value or 0) + 1


async def _ensure_prompt(session: Any, prompt: PromptDefinition) -> R4PromptVersionModel:
    existing = await session.scalar(
        select(R4PromptVersionModel).where(
            R4PromptVersionModel.prompt_id == prompt.prompt_id,
            R4PromptVersionModel.prompt_version == prompt.version,
        )
    )
    if existing is not None:
        return existing
    row = R4PromptVersionModel(
        id=uuid.uuid4(),
        prompt_id=prompt.prompt_id,
        prompt_version=prompt.version,
        operation_type=prompt.operation_type,
        system_instruction_ref=prompt.system_instruction_ref,
        task_template_ref=prompt.task_template_ref,
        response_schema_ref=prompt.response_schema_ref,
        status=prompt.status,
        prompt_document=prompt.model_dump(mode="json"),
        approved_by=prompt.approved_by,
    )
    session.add(row)
    return row


async def _event(
    session: Any,
    *,
    project_id: uuid.UUID,
    actor_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> AeirChangeEventModel:
    sequence = int(
        await session.scalar(
            select(func.max(AeirChangeEventModel.sequence)).where(
                AeirChangeEventModel.project_id == project_id
            )
        )
        or 0
    ) + 1
    previous_hash = await session.scalar(
        select(AeirChangeEventModel.event_hash)
        .where(AeirChangeEventModel.project_id == project_id)
        .order_by(AeirChangeEventModel.sequence.desc())
        .limit(1)
    )
    document = {
        "project_id": str(project_id),
        "sequence": sequence,
        "event_type": event_type,
        "actor_id": actor_id,
        "previous_hash": previous_hash,
        "payload": payload,
    }
    return AeirChangeEventModel(
        id=uuid.uuid4(),
        project_id=project_id,
        model_version_id=None,
        sequence=sequence,
        event_type=event_type,
        actor_id=actor_id,
        previous_hash=previous_hash,
        event_hash=hash_json(document),
        payload=payload,
    )


def _failure_row(
    *,
    project_id: uuid.UUID,
    operation_id: str,
    operation_row_id: uuid.UUID | None,
    failure_type: str,
    retry_count: int,
    final_status: str,
    error_summary: str,
) -> R4AiOperationFailureModel:
    failure_document = {
        "operation_id": operation_id,
        "failure_type": failure_type,
        "retry_count": retry_count,
        "final_status": final_status,
        "error_summary": error_summary,
    }
    return R4AiOperationFailureModel(
        id=uuid.uuid4(),
        project_id=project_id,
        ai_operation_row_id=operation_row_id,
        operation_id=operation_id,
        failure_type=failure_type,
        retry_count=retry_count,
        final_status=final_status,
        error_summary=error_summary,
        failure_document=failure_document,
        failure_hash=hash_json({"project_id": str(project_id), "failure": failure_document}),
    )


def _domain_segment(row: R4SourceSegmentModel):  # type: ignore[no-untyped-def]
    from ai_enterprise.domain.r4_interpretation import SourceSegment

    return SourceSegment(
        id=row.segment_id,
        source_id=row.source_id,
        sequence=row.sequence,
        segment_type=row.segment_type,
        heading_path=tuple(row.heading_path),
        text=row.text,
        start_offset=row.start_offset,
        end_offset=row.end_offset,
        checksum=row.checksum,
    )


def _segment_payload(row: R4SourceSegmentModel) -> dict[str, Any]:
    return {
        "id": row.segment_id,
        "source_id": row.source_id,
        "sequence": row.sequence,
        "segment_type": row.segment_type,
        "heading_path": row.heading_path,
        "text": row.text,
        "start_offset": row.start_offset,
        "end_offset": row.end_offset,
        "checksum": row.checksum,
    }


def _candidate_rows(
    project_id: uuid.UUID,
    operation: R4AiOperationModel,
    extraction: Any,
) -> tuple[
    list[R4CandidateObjectModel],
    list[R4CandidateRelationshipModel],
    list[R4CandidateSourceLinkModel],
    list[R4AiProvenanceLinkModel],
]:
    candidates: list[R4CandidateObjectModel] = []
    relationships: list[R4CandidateRelationshipModel] = []
    links: list[R4CandidateSourceLinkModel] = []
    provenance: list[R4AiProvenanceLinkModel] = []
    for candidate in extraction.candidate_objects:
        payload = candidate.model_dump(mode="json") | {"ai_operation_id": operation.operation_id}
        candidate_hash = hash_json(payload)
        candidates.append(
            R4CandidateObjectModel(
                id=uuid.uuid4(),
                project_id=project_id,
                ai_operation_row_id=operation.id,
                candidate_id=candidate.candidate_id,
                proposed_object_type=candidate.proposed_type,
                proposed_object_id=candidate.proposed_id,
                truth_status=candidate.truth_status,
                approval_status=candidate.approval_status,
                candidate_status=CandidateStatus.PENDING_REVIEW,
                schema_status="valid",
                deterministic_validation_status="valid",
                confidence=candidate.confidence,
                payload=payload,
                candidate_hash=candidate_hash,
            )
        )
        segment_refs = [support.segment_id for support in candidate.source_support]
        provenance.append(
            R4AiProvenanceLinkModel(
                id=uuid.uuid4(),
                project_id=project_id,
                entity_type="candidate_object",
                entity_id=candidate.candidate_id,
                ai_operation_id=operation.operation_id,
                source_segment_refs=segment_refs,
                derivation_type="direct_extraction",
                confidence=candidate.confidence,
                provenance_document={
                    "candidate_id": candidate.candidate_id,
                    "source_segment_refs": segment_refs,
                    "ai_operation_id": operation.operation_id,
                },
            )
        )
        for support in candidate.source_support:
            links.append(
                R4CandidateSourceLinkModel(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    candidate_id=candidate.candidate_id,
                    source_id=support.source_id,
                    segment_id=support.segment_id,
                    support_type=support.support_type,
                    quoted_fragment=support.quoted_fragment,
                    link_document=support.model_dump(mode="json"),
                )
            )
    for relationship in extraction.candidate_relationships:
        payload = relationship.model_dump(mode="json") | {
            "ai_operation_id": operation.operation_id
        }
        candidate_hash = hash_json(payload)
        relationships.append(
            R4CandidateRelationshipModel(
                id=uuid.uuid4(),
                project_id=project_id,
                ai_operation_row_id=operation.id,
                candidate_id=relationship.candidate_id,
                relationship_type=relationship.type,
                source_candidate_ref=relationship.source_candidate_ref,
                target_candidate_ref=relationship.target_candidate_ref,
                truth_status=relationship.truth_status,
                approval_status=relationship.approval_status,
                candidate_status=CandidateStatus.PENDING_REVIEW,
                schema_status="valid",
                confidence=relationship.confidence,
                payload=payload,
                candidate_hash=candidate_hash,
            )
        )
        segment_refs = [support.segment_id for support in relationship.source_support]
        provenance.append(
            R4AiProvenanceLinkModel(
                id=uuid.uuid4(),
                project_id=project_id,
                entity_type="candidate_relationship",
                entity_id=relationship.candidate_id,
                ai_operation_id=operation.operation_id,
                source_segment_refs=segment_refs,
                derivation_type="direct_extraction",
                confidence=relationship.confidence,
                provenance_document={
                    "candidate_id": relationship.candidate_id,
                    "source_segment_refs": segment_refs,
                    "ai_operation_id": operation.operation_id,
                },
            )
        )
        for support in relationship.source_support:
            links.append(
                R4CandidateSourceLinkModel(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    candidate_id=relationship.candidate_id,
                    source_id=support.source_id,
                    segment_id=support.segment_id,
                    support_type=support.support_type,
                    quoted_fragment=support.quoted_fragment,
                    link_document=support.model_dump(mode="json"),
                )
            )
    return candidates, relationships, links, provenance


def _uncertainty_rows(
    project_id: uuid.UUID, operation: R4AiOperationModel, extraction: Any
) -> list[R4UncertaintyRecordModel]:
    rows: list[R4UncertaintyRecordModel] = []
    specs = [
        ("ambiguity", extraction.ambiguities),
        ("assumption", extraction.assumptions),
        ("probable_contradiction", extraction.probable_contradictions),
        ("missing_information", extraction.missing_information),
    ]
    for record_type, collection in specs:
        for item in collection:
            payload = item.model_dump(mode="json")
            rows.append(
                R4UncertaintyRecordModel(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    ai_operation_row_id=operation.id,
                    record_id=item.id,
                    record_type=record_type,
                    category=(
                        payload.get("category")
                        or payload.get("contradiction_type", "general")
                    ),
                    severity=payload.get("severity", "warning"),
                    blocking=bool(
                        payload.get("blocking", payload.get("blocking_recommendation", False))
                    ),
                    status=payload.get("status", "open"),
                    payload=payload,
                    record_hash=hash_json({"project_id": str(project_id), "payload": payload}),
                )
            )
    return rows


def _clarification_rows(
    project_id: uuid.UUID, operation: R4AiOperationModel, extraction: Any
) -> list[R4ClarificationQuestionModel]:
    return [
        R4ClarificationQuestionModel(
            id=uuid.uuid4(),
            project_id=project_id,
            ai_operation_row_id=operation.id,
            question_id=item.id,
            origin_type=item.origin_type,
            origin_ref=item.origin_ref,
            priority=item.priority,
            blocking=item.blocking,
            status=item.status,
            question_document=item.model_dump(mode="json"),
            question_hash=hash_json(
                {"project_id": str(project_id), "question": item.model_dump(mode="json")}
            ),
        )
        for item in extraction.clarification_candidates
    ]


async def _list_uncertainty(
    project_id: uuid.UUID,
    record_type: str,
    session: Any,
    actor: Any,
) -> list[dict[str, Any]]:
    _require_human(actor)
    rows = (
        await session.scalars(
            select(R4UncertaintyRecordModel)
            .where(
                R4UncertaintyRecordModel.project_id == project_id,
                R4UncertaintyRecordModel.record_type == record_type,
            )
            .order_by(R4UncertaintyRecordModel.record_id)
        )
    ).all()
    return [row.payload for row in rows]
