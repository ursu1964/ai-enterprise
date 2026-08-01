import uuid

from fastapi import APIRouter, HTTPException, status

from ai_enterprise.api.dependencies import ActorDependency, SessionDependency
from ai_enterprise.api.enterprise_kernel_authority import enterprise_kernel_actor
from ai_enterprise.api.enterprise_kernel_schemas import (
    EnterpriseResourceResponse,
    EnterpriseScheduleResponse,
)
from ai_enterprise.application.enterprise_kernel.dto import (
    RegisterEnterpriseResource,
    ScheduleEnterpriseWork,
)
from ai_enterprise.application.enterprise_kernel.service import EnterpriseKernelService
from ai_enterprise.domain.enterprise_kernel.exceptions import (
    EnterpriseKernelError,
    EnterpriseResourceNotFound,
    EnterpriseScheduleNotFound,
)
from ai_enterprise.infrastructure.enterprise_kernel.repository import (
    SqlAlchemyEnterpriseKernelAuditSink,
    SqlAlchemyEnterpriseResourceRepository,
)

router = APIRouter(prefix="/enterprise-kernel", tags=["enterprise-kernel"])


def _service(session: SessionDependency) -> EnterpriseKernelService:
    return EnterpriseKernelService(
        SqlAlchemyEnterpriseResourceRepository(session),
        SqlAlchemyEnterpriseKernelAuditSink(session),
    )


def _translate(exc: EnterpriseKernelError) -> HTTPException:
    if isinstance(exc, EnterpriseResourceNotFound | EnterpriseScheduleNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)})


@router.post(
    "/resources", response_model=EnterpriseResourceResponse, status_code=status.HTTP_201_CREATED
)
async def register_resource(
    request: RegisterEnterpriseResource,
    session: SessionDependency,
    actor: ActorDependency,
) -> EnterpriseResourceResponse:
    try:
        value = await _service(session).register_resource(
            request, enterprise_kernel_actor(actor, "enterprise_resource.register")
        )
    except EnterpriseKernelError as exc:
        raise _translate(exc) from exc
    return EnterpriseResourceResponse.model_validate(value)


@router.get("/resources/{resource_id}", response_model=EnterpriseResourceResponse)
async def get_resource(
    resource_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> EnterpriseResourceResponse:
    enterprise_kernel_actor(actor, "enterprise_resource.read")
    try:
        value = await _service(session).get_resource(resource_id)
    except EnterpriseKernelError as exc:
        raise _translate(exc) from exc
    return EnterpriseResourceResponse.model_validate(value)


@router.get("/resources", response_model=tuple[EnterpriseResourceResponse, ...])
async def list_resources(
    organization_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> tuple[EnterpriseResourceResponse, ...]:
    enterprise_kernel_actor(actor, "enterprise_resource.read")
    repository = SqlAlchemyEnterpriseResourceRepository(session)
    values = await repository.list_for_organization(organization_id)
    return tuple(EnterpriseResourceResponse.model_validate(item) for item in values)


@router.post(
    "/schedules", response_model=EnterpriseScheduleResponse, status_code=status.HTTP_201_CREATED
)
async def schedule_work(
    request: ScheduleEnterpriseWork,
    session: SessionDependency,
    actor: ActorDependency,
) -> EnterpriseScheduleResponse:
    try:
        value = await _service(session).schedule_work(
            request, enterprise_kernel_actor(actor, "enterprise_schedule.create")
        )
    except EnterpriseKernelError as exc:
        raise _translate(exc) from exc
    return EnterpriseScheduleResponse.model_validate(value)


@router.get("/schedules", response_model=tuple[EnterpriseScheduleResponse, ...])
async def list_schedules(
    organization_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> tuple[EnterpriseScheduleResponse, ...]:
    enterprise_kernel_actor(actor, "enterprise_schedule.read")
    repository = SqlAlchemyEnterpriseResourceRepository(session)
    values = await repository.list_schedules_for_organization(organization_id)
    return tuple(EnterpriseScheduleResponse.model_validate(item) for item in values)
