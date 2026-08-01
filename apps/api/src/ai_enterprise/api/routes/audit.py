import uuid

from fastapi import APIRouter, HTTPException, Query, Response

from ai_enterprise.api.dependencies import SessionDependency
from ai_enterprise.application.audit.dto import (
    AuditTimelineResponse,
    IntegrityResponse,
    ProjectAuditSummaryResponse,
    ProjectProvenanceResponse,
)
from ai_enterprise.application.audit.service import AuditQueryService
from ai_enterprise.domain.audit.exceptions import (
    AuditProjectNotFoundError,
    InvalidAuditCursorError,
)
from ai_enterprise.infrastructure.audit.audit_exporter import AuditExporter

router = APIRouter(prefix="/projects", tags=["audit"])


def _not_found(exc: AuditProjectNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get("/{project_id}/audit/timeline", response_model=AuditTimelineResponse)
async def timeline(
    project_id: uuid.UUID, session: SessionDependency,
    limit: int = Query(default=100, ge=1, le=500), cursor: str | None = None,
    aggregate_type: str | None = None, event_type: str | None = None,
) -> AuditTimelineResponse:
    try:
        return await AuditQueryService(session).timeline(
            project_id=project_id, limit=limit, cursor_value=cursor,
            aggregate_type=aggregate_type, event_type=event_type,
        )
    except AuditProjectNotFoundError as exc:
        raise _not_found(exc) from exc
    except InvalidAuditCursorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{project_id}/audit/summary", response_model=ProjectAuditSummaryResponse)
async def summary(
    project_id: uuid.UUID, session: SessionDependency,
) -> ProjectAuditSummaryResponse:
    try:
        return await AuditQueryService(session).summary(project_id)
    except AuditProjectNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/{project_id}/audit/provenance", response_model=ProjectProvenanceResponse)
async def provenance(
    project_id: uuid.UUID, session: SessionDependency,
) -> ProjectProvenanceResponse:
    try:
        return await AuditQueryService(session).provenance(project_id)
    except AuditProjectNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/{project_id}/audit/integrity", response_model=IntegrityResponse)
async def integrity(
    project_id: uuid.UUID, session: SessionDependency,
) -> IntegrityResponse:
    try:
        return await AuditQueryService(session).integrity(project_id)
    except AuditProjectNotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/{project_id}/audit/export")
async def export(project_id: uuid.UUID, session: SessionDependency) -> Response:
    try:
        files = await AuditQueryService(session).export_data(project_id)
    except AuditProjectNotFoundError as exc:
        raise _not_found(exc) from exc
    payload, root_sha256 = AuditExporter().build(files)
    return Response(
        payload, media_type="application/gzip",
        headers={"X-Audit-Root-SHA256": root_sha256,
                 "Content-Disposition": f'attachment; filename="audit-{project_id}.tar.gz"'},
    )
