import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select, text

from ai_enterprise.api.architecture_schemas import (
    ApproveArchitectureRequest,
    ArchitectureApprovalResponse,
    ArchitectureArtifactResponse,
    ArchitectureLineageResponse,
    ArchitectureReviewResponse,
    ArchitectureRunResponse,
    CompleteArchitectureReviewRequest,
    CreateArchitectureRevisionRequest,
    CreateArchitectureRunRequest,
    OpenArchitectureReviewRequest,
    WorkPackageGateResponse,
)
from ai_enterprise.api.dependencies import ActorDependency, SessionDependency
from ai_enterprise.application.architecture_operations.contracts import (
    ArchitectureIntegrityRecord,
    ArchitectureRunSnapshot,
)
from ai_enterprise.application.architecture_operations.integrity import (
    ArchitectureIntegrityScanner,
)
from ai_enterprise.application.architecture_operations.observability import (
    ArchitectureWorkerHealth,
)
from ai_enterprise.application.architecture_operations.recovery import (
    ArchitectureRecoveryPolicy,
)
from ai_enterprise.application.architecture_service import (
    ArchitectureGovernanceError,
    ArchitectureGovernanceService,
)
from ai_enterprise.config import get_settings
from ai_enterprise.domain.hashing import hash_json
from ai_enterprise.infrastructure.architecture.models import (
    ArchitectureApprovalModel,
    ArchitectureArtifactModel,
    ArchitectureReviewModel,
    ArchitectureRunModel,
)
from ai_enterprise.infrastructure.architecture.provider_factory import (
    ArchitectureProviderConfig,
    create_architecture_provider,
)
from ai_enterprise.infrastructure.database.models import JobModel

router = APIRouter(prefix="/architecture", tags=["architecture-governance"])


def conflict(exc: ArchitectureGovernanceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post(
    "/projects/{project_id}/runs",
    response_model=ArchitectureRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_run(
    project_id: uuid.UUID, request: CreateArchitectureRunRequest, session: SessionDependency
) -> ArchitectureRunResponse:
    try:
        value = await ArchitectureGovernanceService(session).create_run(
            project_id, request.requirements_artifact_id
        )
    except ArchitectureGovernanceError as exc:
        raise conflict(exc) from exc
    return ArchitectureRunResponse.model_validate(value)


@router.get("/runs/{run_id}", response_model=ArchitectureRunResponse)
async def get_run(run_id: uuid.UUID, session: SessionDependency) -> ArchitectureRunResponse:
    value = await session.get(ArchitectureRunModel, run_id)
    if value is None:
        raise HTTPException(404, "Architecture run not found")
    return ArchitectureRunResponse.model_validate(value)


@router.get("/artifacts/{artifact_id}", response_model=ArchitectureArtifactResponse)
async def get_artifact(
    artifact_id: uuid.UUID, session: SessionDependency
) -> ArchitectureArtifactResponse:
    value = await session.get(ArchitectureArtifactModel, artifact_id)
    if value is None:
        raise HTTPException(404, "Architecture artifact not found")
    return ArchitectureArtifactResponse.model_validate(value)


@router.post(
    "/artifacts/{artifact_id}/reviews", response_model=ArchitectureReviewResponse, status_code=201
)
async def open_review(
    artifact_id: uuid.UUID,
    request: OpenArchitectureReviewRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> ArchitectureReviewResponse:
    try:
        value = await ArchitectureGovernanceService(session).open_review(
            artifact_id, request.reviewer_id, actor
        )
    except ArchitectureGovernanceError as exc:
        raise conflict(exc) from exc
    return ArchitectureReviewResponse.model_validate(value)


@router.post("/reviews/{review_id}/complete", response_model=ArchitectureReviewResponse)
async def complete_review(
    review_id: uuid.UUID,
    request: CompleteArchitectureReviewRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> ArchitectureReviewResponse:
    try:
        value = await ArchitectureGovernanceService(session).complete_review(
            review_id, request.decision, request.comments, request.findings, actor
        )
    except ArchitectureGovernanceError as exc:
        raise conflict(exc) from exc
    return ArchitectureReviewResponse.model_validate(value)


@router.post(
    "/reviews/{review_id}/revision", response_model=ArchitectureRunResponse, status_code=202
)
async def create_revision(
    review_id: uuid.UUID,
    request: CreateArchitectureRevisionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> ArchitectureRunResponse:
    try:
        _, run = await ArchitectureGovernanceService(session).create_revision(
            review_id, request.revision_instructions, actor
        )
    except ArchitectureGovernanceError as exc:
        raise conflict(exc) from exc
    return ArchitectureRunResponse.model_validate(run)


@router.post(
    "/artifacts/{artifact_id}/approval",
    response_model=ArchitectureApprovalResponse,
    status_code=201,
)
async def approve(
    artifact_id: uuid.UUID,
    request: ApproveArchitectureRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> ArchitectureApprovalResponse:
    try:
        value = await ArchitectureGovernanceService(session).approve(
            artifact_id, request.evidence, actor
        )
    except ArchitectureGovernanceError as exc:
        raise conflict(exc) from exc
    return ArchitectureApprovalResponse.model_validate(value)


@router.get("/projects/{project_id}/latest", response_model=ArchitectureArtifactResponse)
async def latest(project_id: uuid.UUID, session: SessionDependency) -> ArchitectureArtifactResponse:
    value = await session.scalar(
        select(ArchitectureArtifactModel)
        .where(
            ArchitectureArtifactModel.project_id == project_id,
            ArchitectureArtifactModel.status == "approved",
        )
        .order_by(ArchitectureArtifactModel.version.desc())
        .limit(1)
    )
    if value is None:
        raise HTTPException(404, "Approved architecture not found")
    return ArchitectureArtifactResponse.model_validate(value)


@router.get("/artifacts/{artifact_id}/lineage", response_model=ArchitectureLineageResponse)
async def lineage(
    artifact_id: uuid.UUID, session: SessionDependency
) -> ArchitectureLineageResponse:
    current = await session.get(ArchitectureArtifactModel, artifact_id)
    if current is None:
        raise HTTPException(404, "Architecture artifact not found")
    ancestors = []
    parent = current.parent_artifact_id
    while parent is not None:
        item = await session.get(ArchitectureArtifactModel, parent)
        if item is None:
            raise HTTPException(409, "Architecture lineage is corrupt")
        ancestors.append(ArchitectureArtifactResponse.model_validate(item))
        parent = item.parent_artifact_id
    return ArchitectureLineageResponse(
        artifact=ArchitectureArtifactResponse.model_validate(current), ancestors=ancestors
    )


@router.get("/artifacts/{artifact_id}/work-package-gate", response_model=WorkPackageGateResponse)
async def work_package_gate(
    artifact_id: uuid.UUID, approval_id: uuid.UUID, session: SessionDependency
) -> WorkPackageGateResponse:
    try:
        approval = await ArchitectureGovernanceService(session).gate(artifact_id, approval_id)
    except ArchitectureGovernanceError as exc:
        raise conflict(exc) from exc
    return WorkPackageGateResponse(
        eligible=True,
        architecture_artifact_id=artifact_id,
        architecture_approval_id=approval.id,
        checksum=approval.approved_checksum,
        version=approval.architecture_version,
    )


@router.get("/projects/{project_id}/history", response_model=list[ArchitectureArtifactResponse])
async def history(
    project_id: uuid.UUID, session: SessionDependency
) -> list[ArchitectureArtifactResponse]:
    rows = list(
        (
            await session.scalars(
                select(ArchitectureArtifactModel)
                .where(ArchitectureArtifactModel.project_id == project_id)
                .order_by(ArchitectureArtifactModel.version)
            )
        ).all()
    )
    return [ArchitectureArtifactResponse.model_validate(item) for item in rows]


@router.get("/worker/health")
async def worker_health(session: SessionDependency) -> dict[str, object]:
    database_reachable = queue_reachable = False
    active = 0
    try:
        await session.execute(text("SELECT 1"))
        database_reachable = True
        await session.scalar(select(func.count()).select_from(JobModel))
        queue_reachable = True
        active = int(
            await session.scalar(
                select(func.count())
                .select_from(ArchitectureRunModel)
                .where(ArchitectureRunModel.status.in_(("ready", "running")))
            )
            or 0
        )
    except Exception:
        pass
    return ArchitectureWorkerHealth(
        database_reachable=database_reachable,
        queue_reachable=queue_reachable,
        lease_store_reachable=queue_reachable,
        accepting_work=database_reachable and queue_reachable,
        active_leases=active,
    ).payload()


@router.get("/worker/health/live")
async def worker_liveness(session: SessionDependency) -> dict[str, object]:
    payload = await worker_health(session)
    if not payload["live"]:
        raise HTTPException(503, detail={"code": "ARCHITECTURE_WORKER_NOT_LIVE"})
    return payload


@router.get("/worker/health/ready")
async def worker_readiness(session: SessionDependency) -> dict[str, object]:
    payload = await worker_health(session)
    if not payload["ready"]:
        raise HTTPException(503, detail={"code": "ARCHITECTURE_WORKER_NOT_READY"})
    return payload


@router.get("/provider/readiness")
async def architecture_provider_readiness() -> dict[str, object]:
    settings = get_settings()
    config = ArchitectureProviderConfig(
        provider=settings.architecture_provider,
        model_name=settings.architecture_model_name,
        base_url=settings.ollama_base_url,
        temperature=settings.architecture_temperature,
        timeout_seconds=settings.architecture_timeout_seconds,
        max_tokens=settings.architecture_max_tokens,
    )
    try:
        provider = create_architecture_provider(
            config, scripted_outputs=[] if config.provider == "scripted" else None
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(503, detail={"code": "ARCHITECTURE_PROVIDER_NOT_READY"}) from exc
    return {"status": "ready", "provider": config.provider, "model": provider.model_name}


@router.get("/runs/{run_id}/integrity")
async def run_integrity(run_id: uuid.UUID, session: SessionDependency) -> dict[str, object]:
    run = await session.get(ArchitectureRunModel, run_id)
    if run is None:
        raise HTTPException(404, "Architecture run not found")
    artifacts = list(
        (
            await session.scalars(
                select(ArchitectureArtifactModel).where(ArchitectureArtifactModel.run_id == run.id)
            )
        ).all()
    )
    artifact = artifacts[0] if len(artifacts) == 1 else None
    reviews = (
        []
        if artifact is None
        else list(
            (
                await session.scalars(
                    select(ArchitectureReviewModel).where(
                        ArchitectureReviewModel.architecture_artifact_id == artifact.id
                    )
                )
            ).all()
        )
    )
    approval = (
        None
        if artifact is None
        else await session.scalar(
            select(ArchitectureApprovalModel).where(
                ArchitectureApprovalModel.architecture_artifact_id == artifact.id
            )
        )
    )
    artifact_valid = artifact is None or artifact.checksum == hash_json(
        {
            "markdown": artifact.markdown_content,
            "structured": artifact.structured_content,
            "schema_version": artifact.schema_version,
        }
    )
    review_valid = artifact is None or all(
        item.reviewed_checksum == artifact.checksum for item in reviews
    )
    approval_valid = approval is None or (
        artifact is not None
        and approval.approved_checksum == artifact.checksum
        and approval.review_checksum == artifact.checksum
    )
    evidence_valid = True
    if approval is not None and artifact is not None:
        evidence_valid = approval.evidence_checksum == hash_json(
            {
                "artifact_id": str(artifact.id),
                "review_id": str(approval.approving_review_id),
                "checksum": artifact.checksum,
                "version": artifact.version,
                "approver": approval.approved_by,
                "policy": approval.policy_version,
                "evidence": approval.evidence,
            }
        )
    lineage_valid = artifact is None or (
        run.parent_architecture_artifact_id == artifact.parent_artifact_id
    )
    record = ArchitectureIntegrityRecord(
        run_id=str(run.id),
        run_status=run.status,
        attempt_statuses=(),
        artifact_ids=tuple(str(item.id) for item in artifacts),
        artifact_checksum_valid=artifact_valid,
        review_checksum_valid=review_valid,
        approval_checksum_valid=approval_valid,
        approval_evidence_checksum_valid=evidence_valid,
        audit_chain_valid=True,
        revision_lineage_valid=lineage_valid,
    )
    findings = ArchitectureIntegrityScanner().scan((record,))
    return {
        "valid": not findings,
        "findings": [
            {
                "code": item.code,
                "severity": item.severity,
                "aggregate_id": item.aggregate_id,
                "description": item.description,
            }
            for item in findings
        ],
    }


@router.get("/runs/{run_id}/recovery-inspection")
async def recovery_inspection(run_id: uuid.UUID, session: SessionDependency) -> dict[str, object]:
    run = await session.get(ArchitectureRunModel, run_id)
    if run is None:
        raise HTTPException(404, "Architecture run not found")
    artifact = await session.scalar(
        select(ArchitectureArtifactModel).where(ArchitectureArtifactModel.run_id == run.id)
    )
    snapshot = ArchitectureRunSnapshot(
        run_id=str(run.id),
        project_id=str(run.project_id),
        status=run.status,
        latest_attempt_status="succeeded" if artifact is not None else None,
        artifact_present=artifact is not None,
        successful_attempt_count=1 if artifact is not None else 0,
        artifact_checksum_valid=True,
    )
    inspection = ArchitectureRecoveryPolicy().inspect(snapshot)
    return {
        "run_id": str(run.id),
        "action": inspection.recovery_action,
        "eligible": inspection.recovery_eligible,
        "reason": inspection.reason,
    }
