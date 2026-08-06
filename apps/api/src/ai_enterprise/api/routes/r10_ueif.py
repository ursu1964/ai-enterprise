from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from ai_enterprise.api.dependencies import ActorDependency, SessionDependency
from ai_enterprise.api.r10_ueif_schemas import (
    R10AiInteractionProposalRequest,
    R10ApprovalWorkspaceRequest,
    R10CollaborationThreadRequest,
    R10DocumentationPanelRequest,
    R10ExperienceApiContractRequest,
    R10ExperienceDashboardResponse,
    R10ExperienceProfileRequest,
    R10ExplainabilityViewRequest,
    R10ManifestStudioSessionRequest,
    R10NotificationRuleRequest,
    R10RecordResponse,
    R10RoleDashboardRequest,
    R10RoleWorkspaceRequest,
    R10SearchIndexSnapshotRequest,
    R10TraceabilityViewRequest,
    R10VisualModelRequest,
    R10WorkspaceSurfaceRequest,
)
from ai_enterprise.domain.r10_ueif import (
    UeifDevice,
    UeifRole,
    UeifWorkspaceSurfaceType,
    ai_interaction_policy,
    ai_interaction_proposal,
    approval_workspace,
    collaboration_thread,
    documentation_panel,
    experience_api_contract,
    experience_profile,
    explainability_view,
    manifest_studio_session,
    navigation_map,
    notification_rule,
    role_dashboard,
    role_workspace,
    search_index_snapshot,
    traceability_view,
    visual_model,
    workspace_surface,
)
from ai_enterprise.infrastructure.database.models import ProjectModel
from ai_enterprise.infrastructure.knowledge.models import R10ExperienceRecordModel

router = APIRouter(prefix="/projects", tags=["r10-ueif"])


def _require_human(actor: object) -> None:
    if getattr(actor, "actor_type", None) != "human":
        raise HTTPException(status_code=403, detail="Human experience authority is required")


@router.post(
    "/{project_id}/ueif/role-workspaces",
    response_model=R10RecordResponse,
    status_code=201,
)
async def create_role_workspace(
    project_id: uuid.UUID,
    request: R10RoleWorkspaceRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R10RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = role_workspace(
        index=(await _record_count(session, project_id, "role_workspace")) + 1,
        project_id=str(project_id),
        manifest_ref=request.manifest_ref,
        role=UeifRole(request.role),
        components=tuple(request.components),
    )
    row = _row(project_id, "role_workspace", value, actor.subject)
    session.add(row)
    await session.commit()
    return R10RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ueif/manifest-studio-sessions",
    response_model=R10RecordResponse,
    status_code=201,
)
async def create_manifest_studio_session(
    project_id: uuid.UUID,
    request: R10ManifestStudioSessionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R10RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = manifest_studio_session(
        index=(await _record_count(session, project_id, "manifest_studio_session")) + 1,
        manifest_ref=request.manifest_ref,
        validation_hash=request.validation_hash,
        approval_workflow_ref=request.approval_workflow_ref,
    )
    row = _row(project_id, "manifest_studio_session", value, actor.subject)
    session.add(row)
    await session.commit()
    return R10RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ueif/visual-models",
    response_model=R10RecordResponse,
    status_code=201,
)
async def create_visual_model(
    project_id: uuid.UUID,
    request: R10VisualModelRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R10RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = visual_model(
        index=(await _record_count(session, project_id, "visual_model")) + 1,
        manifest_object_ref=request.manifest_object_ref,
        object_kind=request.object_kind,
        nodes=tuple(request.nodes),
        edges=tuple(request.edges),
    )
    row = _row(project_id, "visual_model", value, actor.subject)
    session.add(row)
    await session.commit()
    return R10RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ueif/search-snapshots",
    response_model=R10RecordResponse,
    status_code=201,
)
async def create_search_snapshot(
    project_id: uuid.UUID,
    request: R10SearchIndexSnapshotRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R10RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = search_index_snapshot(
        index=(await _record_count(session, project_id, "search_snapshot")) + 1,
        query=request.query,
        targets=tuple(request.targets),
        result_refs=tuple(request.result_refs),
    )
    row = _row(project_id, "search_snapshot", value, actor.subject)
    session.add(row)
    await session.commit()
    return R10RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ueif/ai-proposals",
    response_model=R10RecordResponse,
    status_code=201,
)
async def create_ai_proposal(
    project_id: uuid.UUID,
    request: R10AiInteractionProposalRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R10RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = ai_interaction_proposal(
        index=(await _record_count(session, project_id, "ai_proposal")) + 1,
        ai_session_ref=request.ai_session_ref,
        manifest_ref=request.manifest_ref,
        recommendation=request.recommendation,
        impact_analysis_ref=request.impact_analysis_ref,
        validation_ref=request.validation_ref,
    )
    row = _row(project_id, "ai_proposal", value, actor.subject)
    session.add(row)
    await session.commit()
    return R10RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ueif/approval-workspaces",
    response_model=R10RecordResponse,
    status_code=201,
)
async def create_approval_workspace(
    project_id: uuid.UUID,
    request: R10ApprovalWorkspaceRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R10RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = approval_workspace(
        index=(await _record_count(session, project_id, "approval_workspace")) + 1,
        proposal_ref=request.proposal_ref,
        affected_object_refs=tuple(request.affected_object_refs),
        risk_ref=request.risk_ref,
        simulation_ref=request.simulation_ref,
        reviewer_comments=tuple(request.reviewer_comments),
    )
    row = _row(project_id, "approval_workspace", value, actor.subject)
    session.add(row)
    await session.commit()
    return R10RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ueif/explainability-views",
    response_model=R10RecordResponse,
    status_code=201,
)
async def create_explainability_view(
    project_id: uuid.UUID,
    request: R10ExplainabilityViewRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R10RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = explainability_view(
        index=(await _record_count(session, project_id, "explainability_view")) + 1,
        object_ref=request.object_ref,
        answers=request.answers,
        traceability_refs=tuple(request.traceability_refs),
    )
    row = _row(project_id, "explainability_view", value, actor.subject)
    session.add(row)
    await session.commit()
    return R10RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ueif/experience-profiles",
    response_model=R10RecordResponse,
    status_code=201,
)
async def create_experience_profile(
    project_id: uuid.UUID,
    request: R10ExperienceProfileRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R10RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = experience_profile(
        index=(await _record_count(session, project_id, "experience_profile")) + 1,
        user_ref=request.user_ref,
        role=UeifRole(request.role),
        device=UeifDevice(request.device),
        personalization=request.personalization,
    )
    row = _row(project_id, "experience_profile", value, actor.subject)
    session.add(row)
    await session.commit()
    return R10RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ueif/traceability-views",
    response_model=R10RecordResponse,
    status_code=201,
)
async def create_traceability_view(
    project_id: uuid.UUID,
    request: R10TraceabilityViewRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R10RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = traceability_view(
        index=(await _record_count(session, project_id, "traceability_view")) + 1,
        object_ref=request.object_ref,
        lineage_refs=tuple(request.lineage_refs),
    )
    row = _row(project_id, "traceability_view", value, actor.subject)
    session.add(row)
    await session.commit()
    return R10RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ueif/collaboration-threads",
    response_model=R10RecordResponse,
    status_code=201,
)
async def create_collaboration_thread(
    project_id: uuid.UUID,
    request: R10CollaborationThreadRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R10RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = collaboration_thread(
        index=(await _record_count(session, project_id, "collaboration_thread")) + 1,
        manifest_object_ref=request.manifest_object_ref,
        comments=tuple(request.comments),
        review_refs=tuple(request.review_refs),
        assignment_refs=tuple(request.assignment_refs),
        notification_refs=tuple(request.notification_refs),
    )
    row = _row(project_id, "collaboration_thread", value, actor.subject)
    session.add(row)
    await session.commit()
    return R10RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ueif/notification-rules",
    response_model=R10RecordResponse,
    status_code=201,
)
async def create_notification_rule(
    project_id: uuid.UUID,
    request: R10NotificationRuleRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R10RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = notification_rule(
        index=(await _record_count(session, project_id, "notification_rule")) + 1,
        event_type=request.event_type,
        role=UeifRole(request.role),
        object_ref=request.object_ref,
        delivery_channels=tuple(UeifDevice(item) for item in request.delivery_channels),
    )
    row = _row(project_id, "notification_rule", value, actor.subject)
    session.add(row)
    await session.commit()
    return R10RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ueif/role-dashboards",
    response_model=R10RecordResponse,
    status_code=201,
)
async def create_role_dashboard(
    project_id: uuid.UUID,
    request: R10RoleDashboardRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R10RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = role_dashboard(
        index=(await _record_count(session, project_id, "role_dashboard")) + 1,
        role=UeifRole(request.role),
        widgets=tuple(request.widgets),
        source_refs=tuple(request.source_refs),
    )
    row = _row(project_id, "role_dashboard", value, actor.subject)
    session.add(row)
    await session.commit()
    return R10RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ueif/navigation-maps",
    response_model=R10RecordResponse,
    status_code=201,
)
async def create_navigation_map(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R10RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = navigation_map(
        index=(await _record_count(session, project_id, "navigation_map")) + 1
    )
    row = _row(project_id, "navigation_map", value, actor.subject)
    session.add(row)
    await session.commit()
    return R10RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ueif/documentation-panels",
    response_model=R10RecordResponse,
    status_code=201,
)
async def create_documentation_panel(
    project_id: uuid.UUID,
    request: R10DocumentationPanelRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R10RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = documentation_panel(
        index=(await _record_count(session, project_id, "documentation_panel")) + 1,
        object_ref=request.object_ref,
        source_refs=tuple(request.source_refs),
    )
    row = _row(project_id, "documentation_panel", value, actor.subject)
    session.add(row)
    await session.commit()
    return R10RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ueif/workspace-surfaces",
    response_model=R10RecordResponse,
    status_code=201,
)
async def create_workspace_surface(
    project_id: uuid.UUID,
    request: R10WorkspaceSurfaceRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R10RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = workspace_surface(
        index=(await _record_count(session, project_id, "workspace_surface")) + 1,
        surface_type=UeifWorkspaceSurfaceType(request.surface_type),
        role=UeifRole(request.role),
        visible_object_refs=tuple(request.visible_object_refs),
        source_system_refs=tuple(request.source_system_refs),
    )
    row = _row(project_id, "workspace_surface", value, actor.subject)
    session.add(row)
    await session.commit()
    return R10RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ueif/ai-interaction-policies",
    response_model=R10RecordResponse,
    status_code=201,
)
async def create_ai_interaction_policy(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R10RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = ai_interaction_policy(
        index=(await _record_count(session, project_id, "ai_interaction_policy")) + 1
    )
    row = _row(project_id, "ai_interaction_policy", value, actor.subject)
    session.add(row)
    await session.commit()
    return R10RecordResponse.model_validate(row)


@router.post(
    "/{project_id}/ueif/experience-api-contracts",
    response_model=R10RecordResponse,
    status_code=201,
)
async def create_experience_api_contract(
    project_id: uuid.UUID,
    request: R10ExperienceApiContractRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R10RecordResponse:
    _require_human(actor)
    await _project(session, project_id)
    value = experience_api_contract(
        index=(await _record_count(session, project_id, "experience_api_contract")) + 1,
        platform_api_refs=tuple(request.platform_api_refs),
    )
    row = _row(project_id, "experience_api_contract", value, actor.subject)
    session.add(row)
    await session.commit()
    return R10RecordResponse.model_validate(row)


@router.get("/{project_id}/ueif/records", response_model=list[R10RecordResponse])
async def list_experience_records(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
    record_type: str | None = Query(default=None),
) -> list[R10RecordResponse]:
    _require_human(actor)
    await _project(session, project_id)
    statement = select(R10ExperienceRecordModel).where(
        R10ExperienceRecordModel.project_id == project_id
    )
    if record_type is not None:
        statement = statement.where(R10ExperienceRecordModel.record_type == record_type)
    rows = (
        await session.scalars(
            statement.order_by(
                R10ExperienceRecordModel.created_at.asc(),
                R10ExperienceRecordModel.record_id.asc(),
            )
        )
    ).all()
    return [R10RecordResponse.model_validate(row) for row in rows]


@router.get("/{project_id}/ueif/events")
async def stream_experience_events(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> StreamingResponse:
    _require_human(actor)
    await _project(session, project_id)
    rows = await _records(session, project_id)
    event_payload = {
        "project_id": str(project_id),
        "record_count": len(rows),
        "latest_record_hash": rows[-1].record_hash if rows else None,
        "records": [
            R10RecordResponse.model_validate(row).model_dump(mode="json") for row in rows[-20:]
        ],
    }

    async def events() -> AsyncIterator[str]:
        import json

        yield f"event: snapshot\ndata: {json.dumps(event_payload, sort_keys=True)}\n\n"
        yield f"event: heartbeat\ndata: {json.dumps({'project_id': str(project_id)})}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{project_id}/ueif/dashboard", response_model=R10ExperienceDashboardResponse)
async def experience_dashboard(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R10ExperienceDashboardResponse:
    _require_human(actor)
    await _project(session, project_id)
    rows = await _records(session, project_id)
    return R10ExperienceDashboardResponse(
        project_id=project_id,
        workspace_count=sum(1 for row in rows if row.record_type == "role_workspace"),
        manifest_studio_session_count=sum(
            1 for row in rows if row.record_type == "manifest_studio_session"
        ),
        visual_model_count=sum(1 for row in rows if row.record_type == "visual_model"),
        search_snapshot_count=sum(1 for row in rows if row.record_type == "search_snapshot"),
        ai_proposal_count=sum(1 for row in rows if row.record_type == "ai_proposal"),
        pending_ai_proposal_count=sum(
            1
            for row in rows
            if row.record_type == "ai_proposal" and row.status == "review_required"
        ),
        approval_workspace_count=sum(
            1 for row in rows if row.record_type == "approval_workspace"
        ),
        explainability_view_count=sum(
            1 for row in rows if row.record_type == "explainability_view"
        ),
        experience_profile_count=sum(
            1 for row in rows if row.record_type == "experience_profile"
        ),
        traceability_view_count=sum(
            1 for row in rows if row.record_type == "traceability_view"
        ),
        collaboration_thread_count=sum(
            1 for row in rows if row.record_type == "collaboration_thread"
        ),
        notification_rule_count=sum(
            1 for row in rows if row.record_type == "notification_rule"
        ),
        role_dashboard_count=sum(1 for row in rows if row.record_type == "role_dashboard"),
        navigation_map_count=sum(1 for row in rows if row.record_type == "navigation_map"),
        documentation_panel_count=sum(
            1 for row in rows if row.record_type == "documentation_panel"
        ),
        workspace_surface_count=sum(
            1 for row in rows if row.record_type == "workspace_surface"
        ),
        ai_interaction_policy_count=sum(
            1 for row in rows if row.record_type == "ai_interaction_policy"
        ),
        experience_api_contract_count=sum(
            1 for row in rows if row.record_type == "experience_api_contract"
        ),
    )


async def _project(session: object, project_id: uuid.UUID) -> ProjectModel:
    project = await session.get(ProjectModel, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _record_count(session: object, project_id: uuid.UUID, record_type: str) -> int:
    return len(
        (
            await session.scalars(
                select(R10ExperienceRecordModel).where(
                    R10ExperienceRecordModel.project_id == project_id,
                    R10ExperienceRecordModel.record_type == record_type,
                )
            )
        ).all()
    )


async def _records(
    session: object,
    project_id: uuid.UUID,
) -> list[R10ExperienceRecordModel]:
    return (
        await session.scalars(
            select(R10ExperienceRecordModel)
            .where(R10ExperienceRecordModel.project_id == project_id)
            .order_by(
                R10ExperienceRecordModel.created_at.asc(),
                R10ExperienceRecordModel.record_id.asc(),
            )
        )
    ).all()


def _row(
    project_id: uuid.UUID,
    record_type: str,
    value: object,
    created_by: str,
) -> R10ExperienceRecordModel:
    document = value.model_dump(mode="json")  # type: ignore[attr-defined]
    return R10ExperienceRecordModel(
        id=uuid.uuid4(),
        project_id=project_id,
        record_type=record_type,
        record_id=_document_record_id(document),
        role=_document_role(document),
        object_ref=_document_object_ref(document),
        status=_document_status(document),
        record_document=document,
        record_hash=_document_hash(document),
        created_by=created_by,
    )


def _document_record_id(document: dict[str, Any]) -> str:
    for key in (
        "workspace_id",
        "session_id",
        "visual_id",
        "search_id",
        "proposal_id",
        "approval_workspace_id",
        "explainability_id",
        "profile_id",
        "traceability_view_id",
        "thread_id",
        "notification_id",
        "dashboard_id",
        "navigation_id",
        "documentation_id",
        "surface_id",
        "policy_id",
        "api_contract_id",
    ):
        if key in document:
            return str(document[key])
    raise HTTPException(status_code=422, detail="UEIF record id missing")


def _document_hash(document: dict[str, Any]) -> str:
    for key in (
        "workspace_hash",
        "session_hash",
        "visual_hash",
        "search_hash",
        "proposal_hash",
        "approval_hash",
        "explainability_hash",
        "profile_hash",
        "traceability_hash",
        "collaboration_hash",
        "notification_hash",
        "dashboard_hash",
        "navigation_hash",
        "documentation_hash",
        "surface_hash",
        "policy_hash",
        "contract_hash",
    ):
        if key in document:
            return str(document[key])
    raise HTTPException(status_code=422, detail="UEIF record hash missing")


def _document_role(document: dict[str, Any]) -> str | None:
    role = document.get("role")
    if isinstance(role, str):
        return role
    return None


def _document_object_ref(document: dict[str, Any]) -> str | None:
    for key in (
        "object_ref",
        "manifest_object_ref",
        "manifest_ref",
        "proposal_ref",
        "api_contract_id",
    ):
        value = document.get(key)
        if isinstance(value, str):
            return value
    return None


def _document_status(document: dict[str, Any]) -> str:
    return str(document.get("status") or "active")
