import asyncio
import logging
import os
import socket
import uuid
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.integration.processor import IntegrationWorkerEntry
from ai_enterprise.application.recovery.processor import RecoveryWorkerEntry
from ai_enterprise.application.workflow.service import WorkflowService
from ai_enterprise.config import Settings, get_settings
from ai_enterprise.domain.enums import JobType
from ai_enterprise.infrastructure.architecture.provider_factory import (
    ArchitectureProviderConfig,
    architecture_provider_ready,
)
from ai_enterprise.infrastructure.database.models import JobModel
from ai_enterprise.infrastructure.database.session import SessionFactory
from ai_enterprise.infrastructure.jobs.crash_safety import LeaseLostError, RetryPolicy
from ai_enterprise.infrastructure.jobs.dispatcher import JobDispatcher
from ai_enterprise.infrastructure.jobs.models import WorkerInstanceModel
from ai_enterprise.infrastructure.jobs.profiles import (
    WorkerProfile,
    allowed_job_types,
)
from ai_enterprise.infrastructure.jobs.recovery import JobRecoveryService, WorkerRegistry
from ai_enterprise.infrastructure.jobs.repository import JobRepository
from ai_enterprise.infrastructure.requirements_llm.provider import (
    RequirementsProviderError,
    create_requirements_provider,
    provider_config_from_settings,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("ai_enterprise.worker")

IntegrationEntryFactory = Callable[[AsyncSession, Settings, str], IntegrationWorkerEntry]


RecoveryEntryFactory = Callable[[AsyncSession, Settings, str], RecoveryWorkerEntry]


def build_worker_id() -> str:
    hostname = socket.gethostname()
    process_id = os.getpid()
    random_suffix = uuid.uuid4().hex[:8]

    return f"{hostname}:{process_id}:{random_suffix}"


async def _heartbeat_job(
    *,
    worker_id: str,
    job_id: uuid.UUID,
    lease_token: uuid.UUID,
    lease_version: int,
    lease_seconds: int,
    interval: int,
    lease_lost: asyncio.Event,
) -> None:
    while True:
        await asyncio.sleep(interval)
        async with SessionFactory() as session:
            repository = JobRepository(session)
            async with session.begin():
                extended = await repository.extend_lease(
                    job_id=job_id,
                    worker_id=worker_id,
                    lease_token=lease_token,
                    lease_version=lease_version,
                    lease_duration=timedelta(seconds=lease_seconds),
                )
        if not extended:
            logger.warning("Lease heartbeat lost for job %s", job_id)
            lease_lost.set()
            return


async def process_one_job(
    worker_id: str,
    *,
    profile: WorkerProfile = WorkerProfile.GENERAL,
    integration_entry: IntegrationWorkerEntry | None = None,
    integration_entry_factory: IntegrationEntryFactory | None = None,
    recovery_entry: RecoveryWorkerEntry | None = None,
    recovery_entry_factory: RecoveryEntryFactory | None = None,
) -> bool:
    settings = get_settings()
    permitted_job_types = set(allowed_job_types(profile))
    provider_degraded = False
    if JobType.RUN_ARCHITECTURE_CREW in permitted_job_types:
        architecture_ready = await architecture_provider_ready(
            ArchitectureProviderConfig(
                provider=settings.architecture_provider,
                model_name=settings.architecture_model_name,
                base_url=settings.architecture_model_base_url,
                temperature=settings.architecture_temperature,
                timeout_seconds=settings.architecture_timeout_seconds,
                max_tokens=settings.architecture_max_tokens,
            )
        )
        if not architecture_ready:
            provider_degraded = True
            permitted_job_types.remove(JobType.RUN_ARCHITECTURE_CREW)
            logger.warning("Architecture provider degraded; leasing is disabled")
    if (
        JobType.RUN_REQUIREMENTS_CREW in permitted_job_types
        and settings.requirements_crew_adapter.strip().lower() == "crewai"
    ):
        try:
            await create_requirements_provider(provider_config_from_settings(settings)).preflight()
        except RequirementsProviderError:
            provider_degraded = True
            permitted_job_types.remove(JobType.RUN_REQUIREMENTS_CREW)
            logger.warning("Requirements provider preflight failed; leasing is disabled")

    async with SessionFactory() as claim_session:
        repository = JobRepository(claim_session)

        async with claim_session.begin():
            worker_record = await claim_session.scalar(
                select(WorkerInstanceModel).where(WorkerInstanceModel.worker_id == worker_id)
            )
            if worker_record is not None:
                worker_record.status = "degraded" if provider_degraded else "online"
            job = await repository.claim_next(
                worker_id=worker_id,
                lease_duration=timedelta(seconds=settings.worker_lease_seconds),
                allowed_job_types=permitted_job_types,
                execution_timeout=timedelta(seconds=settings.worker_execution_timeout_seconds),
            )

        if job is None:
            return False

        job_id = job.id
        job_type = job.job_type
        lease_token = job.lease_token
        lease_version = job.lease_version
        retry_count = job.retry_count
        if lease_token is None:
            raise RuntimeError(f"Claimed job {job_id} has no lease token")

    logger.info(
        "Claimed job %s of type %s",
        job_id,
        job_type,
    )

    lease_lost = asyncio.Event()
    heartbeat = asyncio.create_task(
        _heartbeat_job(
            worker_id=worker_id,
            job_id=job_id,
            lease_token=lease_token,
            lease_version=lease_version,
            lease_seconds=settings.worker_lease_seconds,
            interval=settings.worker_heartbeat_seconds,
            lease_lost=lease_lost,
        )
    )

    try:

        async def execute() -> None:
            async with SessionFactory() as execution_session:
                job_integration_entry = integration_entry
                if (
                    profile is WorkerProfile.INTEGRATION
                    and job_integration_entry is None
                    and integration_entry_factory is not None
                ):
                    job_integration_entry = integration_entry_factory(
                        execution_session,
                        settings,
                        worker_id,
                    )
                job_recovery_entry = recovery_entry
                if (
                    profile is WorkerProfile.RECOVERY
                    and job_recovery_entry is None
                    and recovery_entry_factory is not None
                ):
                    job_recovery_entry = recovery_entry_factory(
                        execution_session,
                        settings,
                        worker_id,
                    )
                job = await execution_session.get(JobModel, job_id)

                if job is None:
                    raise RuntimeError(f"Job {job_id} disappeared")

                dispatcher = JobDispatcher(
                    session=execution_session,
                    settings=settings,
                    integration_entry=job_integration_entry,
                    recovery_entry=job_recovery_entry,
                )
                await dispatcher.dispatch(job)

        execution = asyncio.create_task(execute())
        loss_waiter = asyncio.create_task(lease_lost.wait())
        done, _ = await asyncio.wait(
            {execution, loss_waiter},
            timeout=settings.worker_execution_timeout_seconds,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if loss_waiter in done and lease_lost.is_set():
            execution.cancel()
            await asyncio.gather(execution, return_exceptions=True)
            raise LeaseLostError(f"Lease lost while executing job {job_id}")
        if execution not in done:
            execution.cancel()
            await asyncio.gather(execution, return_exceptions=True)
            raise TimeoutError(
                f"Job {job_id} exceeded {settings.worker_execution_timeout_seconds}s deadline"
            )
        loss_waiter.cancel()
        await asyncio.gather(loss_waiter, return_exceptions=True)
        await execution

        async with SessionFactory() as completion_session:
            repository = JobRepository(completion_session)

            async with completion_session.begin():
                await repository.mark_succeeded(
                    job_id=job_id,
                    worker_id=worker_id,
                    lease_token=lease_token,
                    lease_version=lease_version,
                )

        logger.info("Job %s succeeded", job_id)

    except LeaseLostError:
        logger.warning("Discarded output for job %s after losing its lease", job_id)
    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        policy = RetryPolicy(
            base_seconds=settings.worker_retry_base_seconds,
            maximum_seconds=settings.worker_retry_maximum_seconds,
        )
        decision = policy.classify(exc)

        try:
            async with SessionFactory() as failure_session:
                repository = JobRepository(failure_session)

                async with failure_session.begin():
                    await repository.mark_failed(
                        job_id=job_id,
                        worker_id=worker_id,
                        lease_token=lease_token,
                        lease_version=lease_version,
                        error=str(exc),
                        retry_delay=policy.delay(retry_count + 1),
                        failure_class=decision.failure_class,
                        failure_code=decision.code,
                        retryable=decision.retryable,
                        attempt_status=("timed_out" if isinstance(exc, TimeoutError) else "failed"),
                    )
                    failed_job = await failure_session.get(JobModel, job_id)
                    if failed_job is not None and failed_job.status == "dead_letter":
                        await WorkflowService(failure_session, settings).dead_letter(
                            project_id=failed_job.project_id, error=str(exc)
                        )
        except LeaseLostError:
            logger.warning("Discarded failure result for job %s after losing its lease", job_id)

    finally:
        heartbeat.cancel()
        try:
            await heartbeat
        except asyncio.CancelledError:
            pass

    return True


async def _maintenance_loop(worker_id: str, profile: WorkerProfile, settings: Settings) -> None:
    policy = RetryPolicy(
        base_seconds=settings.worker_retry_base_seconds,
        maximum_seconds=settings.worker_retry_maximum_seconds,
    )
    while True:
        async with SessionFactory() as session:
            async with session.begin():
                await WorkerRegistry(session).heartbeat(worker_id)
                await JobRecoveryService(session, policy).recover_expired(
                    stale_worker_after=timedelta(seconds=settings.worker_stale_after_seconds)
                )
        await asyncio.sleep(settings.worker_recovery_interval_seconds)


async def run_worker(
    profile: WorkerProfile | None = None,
    integration_entry: IntegrationWorkerEntry | None = None,
    integration_entry_factory: IntegrationEntryFactory | None = None,
    recovery_entry: RecoveryWorkerEntry | None = None,
    recovery_entry_factory: RecoveryEntryFactory | None = None,
) -> None:
    settings = get_settings()
    selected_profile = profile or WorkerProfile(settings.worker_profile)
    if (
        selected_profile is WorkerProfile.INTEGRATION
        and integration_entry is None
        and integration_entry_factory is None
    ):
        raise RuntimeError(
            "Integration worker requires an explicitly configured processor "
            "with credential broker and rollback metadata hook"
        )
    if (
        selected_profile is WorkerProfile.RECOVERY
        and recovery_entry is None
        and recovery_entry_factory is None
    ):
        raise RuntimeError(
            "Recovery worker requires an explicitly configured processor "
            "and restricted credential broker"
        )
    worker_id = build_worker_id()

    logger.info("Worker started: %s (%s)", worker_id, selected_profile.value)
    policy = RetryPolicy(
        base_seconds=settings.worker_retry_base_seconds,
        maximum_seconds=settings.worker_retry_maximum_seconds,
    )
    async with SessionFactory() as startup_session:
        async with startup_session.begin():
            await WorkerRegistry(startup_session).register(
                worker_id=worker_id, profile=selected_profile.value
            )
            await JobRecoveryService(startup_session, policy).recover_expired(
                stale_worker_after=timedelta(seconds=settings.worker_stale_after_seconds)
            )
    maintenance = asyncio.create_task(_maintenance_loop(worker_id, selected_profile, settings))
    try:
        while True:
            claimed = await process_one_job(
                worker_id,
                profile=selected_profile,
                integration_entry=integration_entry,
                integration_entry_factory=integration_entry_factory,
                recovery_entry=recovery_entry,
                recovery_entry_factory=recovery_entry_factory,
            )

            if not claimed:
                await asyncio.sleep(settings.worker_poll_interval_seconds)
    finally:
        maintenance.cancel()
        await asyncio.gather(maintenance, return_exceptions=True)
        async with SessionFactory() as shutdown_session:
            async with shutdown_session.begin():
                await WorkerRegistry(shutdown_session).stop(worker_id)


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
