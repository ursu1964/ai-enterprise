from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status

from ai_enterprise.api.dependencies import (
    Actor,
    ActorDependency,
    SessionDependency,
    require_capability,
)
from ai_enterprise.api.resilience_schemas import (
    BackupManifestRequest,
    ContinuityActivationRequest,
    DependencyRequest,
    DisasterRecoveryPlanRequest,
    DisasterRecoveryRunRequest,
    DisasterRecoveryTransitionRequest,
    ObjectiveRequest,
    RestoreVerificationRequest,
    ServiceRequest,
)
from ai_enterprise.application.resilience.service import ResilienceControlPlane
from ai_enterprise.domain.resilience.entities import (
    BackupManifest,
    ContinuityActivation,
    ContinuityPolicy,
    DisasterRecoveryRun,
    RecoveryObjective,
    RestoreVerification,
)
from ai_enterprise.domain.resilience.enums import (
    BackupStatus,
    Capability,
    DisasterRecoveryStatus,
)
from ai_enterprise.domain.resilience.policies import ResiliencePolicyError
from ai_enterprise.infrastructure.resilience.models import (
    BackupManifestModel,
    CapabilityDecisionModel,
    ContinuityActivationModel,
    DisasterRecoveryPlanModel,
    DisasterRecoveryRunModel,
    RecoveryObjectiveModel,
    ResilienceServiceModel,
    RestoreVerificationModel,
    ServiceDependencyModel,
)
from ai_enterprise.infrastructure.resilience.repository import SqlAlchemyResilienceRepository

router = APIRouter(prefix="/resilience", tags=["enterprise-resilience"])


def _human(actor: Actor, roles: set[str]) -> None:
    if actor.actor_type != "human":
        raise HTTPException(
            status_code=403, detail="Required human resilience authority is missing"
        )
    for role in roles:
        try:
            require_capability(actor, f"resilience.{role}", "global")
            return
        except HTTPException:
            continue
    raise HTTPException(
        status_code=403, detail="Required human resilience authority is missing"
    )


async def _authorize(
    repository: SqlAlchemyResilienceRepository,
    capability: Capability,
    actor: Actor,
) -> None:
    try:
        activations = await repository.active_continuity()
        decision = ResilienceControlPlane().authorize(
            capability, activations, now=datetime.now(UTC)
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Continuity policy state unavailable") from exc
    repository.session.add(
        CapabilityDecisionModel(
            id=uuid.uuid4(),
            capability=capability,
            subject_id=actor.subject,
            resource_type="resilience_control_plane",
            resource_id=None,
            allowed=decision.allowed,
            reason=decision.reason,
            policy_versions=list(decision.policy_versions),
            activation_ids=[str(value) for value in decision.activation_ids],
            evaluated_at=datetime.now(UTC),
        )
    )
    if not decision.allowed:
        await repository.audit(
            event_type="continuity.capability_denied",
            actor_id=actor.subject,
            payload={"capability": capability, "reason": decision.reason},
        )
        await repository.session.commit()
        raise HTTPException(
            status_code=409,
            detail={"code": "CAPABILITY_PROHIBITED", "reason": decision.reason},
        )


@router.post("/services", status_code=status.HTTP_201_CREATED)
async def create_service(
    request: ServiceRequest, session: SessionDependency, actor: ActorDependency
) -> dict[str, object]:
    _human(actor, {"resilience_admin"})
    repository = SqlAlchemyResilienceRepository(session)
    await _authorize(repository, Capability.CREATE_PROJECT, actor)
    if request.primary_owner == request.deputy_owner:
        raise HTTPException(status_code=422, detail="Primary and deputy must be distinct")
    value = ResilienceServiceModel(id=uuid.uuid4(), status="draft", **request.model_dump())
    session.add(value)
    await repository.audit(
        event_type="resilience.service_created",
        actor_id=actor.subject,
        payload={"service_id": str(value.id), "name": value.name},
    )
    await session.commit()
    return {"id": value.id, "status": value.status}


@router.get("/services")
async def list_services(
    session: SessionDependency, actor: ActorDependency
) -> list[dict[str, object]]:
    _human(actor, {"resilience_admin", "resilience_auditor", "disaster_recovery_commander"})
    from sqlalchemy import select

    rows = (await session.execute(select(ResilienceServiceModel))).scalars().all()
    return [{"id": row.id, "name": row.name, "status": row.status} for row in rows]


@router.post("/services/{service_id}/objectives", status_code=201)
async def create_objective(
    service_id: uuid.UUID,
    request: ObjectiveRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, object]:
    _human(actor, {"resilience_admin"})
    repository = SqlAlchemyResilienceRepository(session)
    await _authorize(repository, Capability.GRANT_APPROVAL, actor)
    service = await session.get(ResilienceServiceModel, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Service not found")
    latest = await repository.latest_objective(service_id)
    objective = RecoveryObjective(
        service_id=service_id,
        primary_owner=service.primary_owner,
        deputy_owner=service.deputy_owner,
        policy_version=(latest.policy_version + 1 if latest else 1),
        approved_by=actor.subject,
        approved_at=datetime.now(UTC),
        **request.model_dump(),
    )
    try:
        ResilienceControlPlane().validate_objective(objective)
    except ResiliencePolicyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = RecoveryObjectiveModel(
        id=uuid.uuid4(),
        approved_by=objective.approved_by,
        approved_at=objective.approved_at,
        **{
            key: getattr(objective, key)
            for key in (
                "service_id",
                "tier",
                "rto_seconds",
                "rpo_seconds",
                "mtpd_seconds",
                "work_recovery_time_seconds",
                "policy_version",
            )
        },
    )
    session.add(row)
    service.status = "active"
    await repository.audit(
        event_type="resilience.objective_approved",
        actor_id=actor.subject,
        payload={"service_id": str(service_id), "policy_version": objective.policy_version},
    )
    await session.commit()
    return {"id": row.id, "policy_version": row.policy_version, "approved": True}


@router.get("/services/{service_id}/objectives/latest")
async def get_latest_objective(
    service_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> dict[str, object]:
    _human(actor, {"resilience_admin", "resilience_auditor"})
    value = await SqlAlchemyResilienceRepository(session).latest_objective(service_id)
    if value is None:
        raise HTTPException(status_code=404, detail="Recovery objective not found")
    return {
        "service_id": value.service_id,
        "tier": value.tier,
        "policy_version": value.policy_version,
        "approved_by": value.approved_by,
    }


@router.post("/services/{service_id}/dependencies", status_code=201)
async def create_dependency(
    service_id: uuid.UUID,
    request: DependencyRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, object]:
    _human(actor, {"resilience_admin"})
    repository = SqlAlchemyResilienceRepository(session)
    await _authorize(repository, Capability.GRANT_APPROVAL, actor)
    if service_id == request.dependency_service_id:
        raise HTTPException(status_code=422, detail="A service cannot depend on itself")
    if (
        await session.get(ResilienceServiceModel, service_id) is None
        or await session.get(ResilienceServiceModel, request.dependency_service_id) is None
    ):
        raise HTTPException(status_code=404, detail="Service or dependency not found")
    row = ServiceDependencyModel(service_id=service_id, **request.model_dump())
    session.add(row)
    await repository.audit(
        event_type="resilience.dependency_recorded",
        actor_id=actor.subject,
        payload={
            "service_id": str(service_id),
            "dependency_service_id": str(request.dependency_service_id),
            "requirement": request.requirement,
        },
    )
    await session.commit()
    return {"service_id": service_id, **request.model_dump()}


@router.get("/services/{service_id}/dependencies")
async def list_dependencies(
    service_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> list[dict[str, object]]:
    _human(actor, {"resilience_admin", "resilience_auditor"})
    from sqlalchemy import select

    rows = (
        (
            await session.execute(
                select(ServiceDependencyModel).where(
                    ServiceDependencyModel.service_id == service_id
                )
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "dependency_service_id": row.dependency_service_id,
            "requirement": row.requirement,
            "fail_open_prohibited": row.fail_open_prohibited,
        }
        for row in rows
    ]


@router.post("/continuity/activations", status_code=201)
async def activate_continuity(
    request: ContinuityActivationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, object]:
    _human(actor, {"resilience_admin", "crisis_commander"})
    now = datetime.now(UTC)
    from sqlalchemy import func, select

    latest_version = await session.scalar(
        select(func.max(ContinuityActivationModel.policy_version))
    )
    policy = ContinuityPolicy(
        request.mode,
        frozenset(request.allowed_capabilities),
        frozenset(request.prohibited_capabilities),
        request.maximum_duration_seconds,
        int(latest_version or 0) + 1,
    )
    activation = ContinuityActivation(
        uuid.uuid4(),
        policy,
        now,
        now + timedelta(seconds=request.maximum_duration_seconds),
        actor.subject,
        request.reason,
    )
    decision = ResilienceControlPlane().authorize(
        Capability.READ_GOVERNANCE, (activation,), now=now
    )
    if decision.reason == "INVALID_CONTINUITY_POLICY_STATE":
        raise HTTPException(status_code=422, detail=decision.reason)
    row = ContinuityActivationModel(
        id=activation.id,
        mode=activation.policy.mode,
        policy_version=activation.policy.policy_version,
        allowed_capabilities=sorted(activation.policy.allowed),
        prohibited_capabilities=sorted(activation.policy.prohibited),
        activated_by=actor.subject,
        reason=activation.reason,
        activated_at=activation.activated_at,
        expires_at=activation.expires_at,
    )
    session.add(row)
    repo = SqlAlchemyResilienceRepository(session)
    await repo.audit(
        event_type="continuity.mode_activated",
        actor_id=actor.subject,
        payload={"activation_id": str(row.id), "mode": row.mode},
    )
    await session.commit()
    return {"id": row.id, "mode": row.mode, "expires_at": row.expires_at}


@router.post("/continuity/activations/{activation_id}/close")
async def close_continuity(
    activation_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> dict[str, object]:
    _human(actor, {"resilience_admin", "crisis_commander"})
    row = await session.get(ContinuityActivationModel, activation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Activation not found")
    if row.activated_by == actor.subject:
        raise HTTPException(status_code=409, detail="Independent exit reviewer required")
    row.exit_reviewed_by = actor.subject
    row.closed_at = datetime.now(UTC)
    repo = SqlAlchemyResilienceRepository(session)
    await repo.audit(
        event_type="continuity.mode_closed",
        actor_id=actor.subject,
        payload={"activation_id": str(row.id)},
    )
    await session.commit()
    return {"id": row.id, "closed": True}


@router.get("/continuity/effective")
async def effective_continuity(
    session: SessionDependency, actor: ActorDependency
) -> dict[str, object]:
    _human(actor, {"resilience_admin", "resilience_auditor", "crisis_commander"})
    activations = await SqlAlchemyResilienceRepository(session).active_continuity()
    return {
        "activation_ids": [value.id for value in activations],
        "modes": [value.policy.mode for value in activations],
        "requires_review": any(value.expires_at <= datetime.now(UTC) for value in activations),
    }


@router.post("/backups", status_code=201)
async def declare_backup(
    request: BackupManifestRequest, session: SessionDependency, actor: ActorDependency
) -> dict[str, object]:
    _human(actor, {"backup_operator"})
    repository = SqlAlchemyResilienceRepository(session)
    await _authorize(repository, Capability.APPEND_AUDIT, actor)
    row = BackupManifestModel(id=uuid.uuid4(), status=BackupStatus.CREATED, **request.model_dump())
    session.add(row)
    await repository.audit(
        event_type="backup.manifest_declared",
        actor_id=actor.subject,
        payload={"backup_id": str(row.id), "status": row.status},
    )
    await session.commit()
    return {"id": row.id, "status": row.status, "recoverable": False}


@router.get("/backups/{backup_id}")
async def get_backup(
    backup_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> dict[str, object]:
    _human(actor, {"backup_operator", "backup_verifier", "resilience_auditor"})
    row = await session.get(BackupManifestModel, backup_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Backup not found")
    return {"id": row.id, "status": row.status, "content_hash": row.content_hash}


@router.post("/backups/{backup_id}/restore-verifications", status_code=201)
async def record_restore_verification(
    backup_id: uuid.UUID,
    request: RestoreVerificationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, object]:
    _human(actor, {"backup_verifier"})
    repository = SqlAlchemyResilienceRepository(session)
    await _authorize(repository, Capability.APPEND_AUDIT, actor)
    backup_row = await session.get(BackupManifestModel, backup_id)
    if backup_row is None:
        raise HTTPException(status_code=404, detail="Backup not found")
    backup = BackupManifest(
        backup_row.id,
        backup_row.backup_type,
        backup_row.content_hash,
        backup_row.object_count,
        backup_row.total_bytes,
        backup_row.encryption_profile,
        backup_row.schema_version,
        backup_row.audit_checkpoint_hash,
        tuple(backup_row.storage_locations),
        BackupStatus(backup_row.status),
    )
    verification = RestoreVerification(id=uuid.uuid4(), backup_id=backup_id, **request.model_dump())
    row = RestoreVerificationModel(
        id=verification.id,
        backup_id=backup_id,
        status=verification.status,
        isolated_environment=verification.isolated_environment,
        production_credentials_disabled=verification.production_credentials_disabled,
        external_dispatch_blocked=verification.external_dispatch_blocked,
        checks=verification.checks,
    )
    session.add(row)
    try:
        recovered = ResilienceControlPlane().verify_restore(backup, verification)
    except ResiliencePolicyError as exc:
        await repository.audit(
            event_type="backup.restore_verification_failed",
            actor_id=actor.subject,
            payload={"backup_id": str(backup_id), "reason": str(exc)},
        )
        await session.commit()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    backup_row.status = recovered.status
    await repository.audit(
        event_type="backup.restore_verified",
        actor_id=actor.subject,
        payload={"backup_id": str(backup_id), "verification_id": str(row.id)},
    )
    await session.commit()
    return {"id": row.id, "backup_status": backup_row.status}


@router.get("/backups/{backup_id}/restore-verifications")
async def list_restore_verifications(
    backup_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> list[dict[str, object]]:
    _human(actor, {"backup_operator", "backup_verifier", "resilience_auditor"})
    from sqlalchemy import select

    rows = (
        (
            await session.execute(
                select(RestoreVerificationModel).where(
                    RestoreVerificationModel.backup_id == backup_id
                )
            )
        )
        .scalars()
        .all()
    )
    return [{"id": row.id, "status": row.status, "checks": row.checks} for row in rows]


@router.post("/dr-runs", status_code=201)
async def create_dr_run(
    request: DisasterRecoveryRunRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, object]:
    _human(actor, {"disaster_recovery_commander"})
    if request.commander != actor.subject:
        raise HTTPException(status_code=422, detail="Commander must match authenticated actor")
    repository = SqlAlchemyResilienceRepository(session)
    await _authorize(repository, Capability.EXECUTE_RECOVERY, actor)
    from sqlalchemy import select

    approved_plan = await session.scalar(
        select(DisasterRecoveryPlanModel.id).where(
            DisasterRecoveryPlanModel.plan_version == request.plan_version,
            DisasterRecoveryPlanModel.status == "approved",
        )
    )
    if approved_plan is None:
        raise HTTPException(status_code=409, detail="Approved DR plan version is required")
    row = DisasterRecoveryRunModel(
        id=uuid.uuid4(), status=DisasterRecoveryStatus.DECLARED, **request.model_dump()
    )
    session.add(row)
    await repository.audit(
        event_type="dr.run_declared",
        actor_id=actor.subject,
        payload={"run_id": str(row.id), "recovery_site": row.recovery_site},
    )
    await session.commit()
    return {"id": row.id, "status": row.status}


@router.post("/dr-plans", status_code=201)
async def create_dr_plan(
    request: DisasterRecoveryPlanRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, object]:
    _human(actor, {"resilience_admin"})
    repository = SqlAlchemyResilienceRepository(session)
    await _authorize(repository, Capability.GRANT_APPROVAL, actor)
    from sqlalchemy import func, select

    latest = await session.scalar(
        select(func.max(DisasterRecoveryPlanModel.plan_version)).where(
            DisasterRecoveryPlanModel.plan_key == request.plan_key
        )
    )
    row = DisasterRecoveryPlanModel(
        id=uuid.uuid4(),
        plan_version=int(latest or 0) + 1,
        status="approved",
        approved_by=actor.subject,
        approved_at=datetime.now(UTC),
        **request.model_dump(),
    )
    session.add(row)
    await repository.audit(
        event_type="dr.plan_approved",
        actor_id=actor.subject,
        payload={"plan_id": str(row.id), "plan_version": row.plan_version},
    )
    await session.commit()
    return {"id": row.id, "plan_version": row.plan_version, "status": row.status}


@router.get("/dr-plans")
async def list_dr_plans(
    session: SessionDependency, actor: ActorDependency
) -> list[dict[str, object]]:
    _human(actor, {"resilience_admin", "resilience_auditor", "disaster_recovery_commander"})
    from sqlalchemy import select

    rows = (await session.execute(select(DisasterRecoveryPlanModel))).scalars().all()
    return [
        {
            "id": row.id,
            "plan_key": row.plan_key,
            "plan_version": row.plan_version,
            "status": row.status,
        }
        for row in rows
    ]


@router.post("/dr-runs/{run_id}/transitions")
async def transition_dr_run(
    run_id: uuid.UUID,
    request: DisasterRecoveryTransitionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, object]:
    required = (
        {"disaster_recovery_reviewer"}
        if request.target == DisasterRecoveryStatus.COMPLETED
        else {"disaster_recovery_commander"}
    )
    _human(actor, required)
    repository = SqlAlchemyResilienceRepository(session)
    await _authorize(repository, Capability.EXECUTE_RECOVERY, actor)
    row = await session.get(DisasterRecoveryRunModel, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="DR run not found")
    run = DisasterRecoveryRun(
        id=row.id,
        plan_version=row.plan_version,
        status=DisasterRecoveryStatus(row.status),
        commander=row.commander,
        recovery_site=row.recovery_site,
        selected_recovery_point=request.selected_recovery_point or row.selected_recovery_point,
        unresolved_workflows=request.unresolved_workflows,
        unresolved_external_effects=request.unresolved_external_effects,
        missing_artifacts=request.missing_artifacts,
        exit_reviewed_by=(
            actor.subject if request.target == DisasterRecoveryStatus.COMPLETED else None
        ),
    )
    try:
        updated = ResilienceControlPlane().advance_dr(run, request.target)
    except ResiliencePolicyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    for field in (
        "status",
        "selected_recovery_point",
        "unresolved_workflows",
        "unresolved_external_effects",
        "missing_artifacts",
        "exit_reviewed_by",
    ):
        setattr(row, field, getattr(updated, field))
    await repository.audit(
        event_type="dr.run_transitioned",
        actor_id=actor.subject,
        payload={"run_id": str(run_id), "status": updated.status},
    )
    await session.commit()
    return {"id": row.id, "status": row.status}


@router.get("/dr-runs/{run_id}")
async def get_dr_run(
    run_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> dict[str, object]:
    _human(
        actor, {"disaster_recovery_commander", "disaster_recovery_reviewer", "resilience_auditor"}
    )
    row = await session.get(DisasterRecoveryRunModel, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="DR run not found")
    return {
        "id": row.id,
        "status": row.status,
        "selected_recovery_point": row.selected_recovery_point,
        "unresolved_workflows": row.unresolved_workflows,
        "unresolved_external_effects": row.unresolved_external_effects,
        "missing_artifacts": row.missing_artifacts,
    }


@router.get("/services/{service_id}/readiness")
async def service_readiness(
    service_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> dict[str, object]:
    _human(actor, {"resilience_admin", "resilience_auditor", "disaster_recovery_commander"})
    repository = SqlAlchemyResilienceRepository(session)
    service = await session.get(ResilienceServiceModel, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Service not found")
    objective = await repository.latest_objective(service_id)
    backup = await repository.latest_backup()
    from sqlalchemy import select

    dependencies = (
        (
            await session.execute(
                select(ServiceDependencyModel).where(
                    ServiceDependencyModel.service_id == service_id,
                    ServiceDependencyModel.requirement == "mandatory",
                )
            )
        )
        .scalars()
        .all()
    )
    mandatory_dependencies_ready = True
    for dependency in dependencies:
        if await repository.latest_objective(dependency.dependency_service_id) is None:
            mandatory_dependencies_ready = False
            break
    plan_version = await session.scalar(
        select(DisasterRecoveryPlanModel.plan_version)
        .where(DisasterRecoveryPlanModel.status == "approved")
        .order_by(DisasterRecoveryPlanModel.plan_version.desc())
        .limit(1)
    )
    result = ResilienceControlPlane().readiness(
        objective=objective,
        backup=backup,
        plan_version=plan_version,
        mandatory_dependencies_ready=mandatory_dependencies_ready,
    )
    return {"service_id": service_id, "ready": result.ready, "failures": result.failures}
