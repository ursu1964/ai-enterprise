import asyncio
import logging
import os
import socket
import uuid
from datetime import timedelta

from ai_enterprise.config import get_settings
from ai_enterprise.infrastructure.database.models import JobModel
from ai_enterprise.infrastructure.database.session import SessionFactory
from ai_enterprise.infrastructure.jobs.dispatcher import JobDispatcher
from ai_enterprise.infrastructure.jobs.repository import JobRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("ai_enterprise.worker")


def build_worker_id() -> str:
    hostname = socket.gethostname()
    process_id = os.getpid()
    random_suffix = uuid.uuid4().hex[:8]

    return f"{hostname}:{process_id}:{random_suffix}"


async def process_one_job(worker_id: str) -> bool:
    settings = get_settings()

    async with SessionFactory() as claim_session:
        repository = JobRepository(claim_session)

        async with claim_session.begin():
            job = await repository.claim_next(
                worker_id=worker_id,
                lease_duration=timedelta(
                    seconds=settings.worker_lease_seconds
                ),
            )

        if job is None:
            return False

        job_id = job.id
        job_type = job.job_type

    logger.info(
        "Claimed job %s of type %s",
        job_id,
        job_type,
    )

    try:
        async with SessionFactory() as execution_session:
            job = await execution_session.get(
                JobModel,
                job_id,
            )

            if job is None:
                raise RuntimeError(f"Job {job_id} disappeared")

            dispatcher = JobDispatcher(
                session=execution_session,
                settings=settings,
            )

            await dispatcher.dispatch(job)

        async with SessionFactory() as completion_session:
            repository = JobRepository(completion_session)

            async with completion_session.begin():
                await repository.mark_succeeded(
                    job_id=job_id,
                    worker_id=worker_id,
                )

        logger.info("Job %s succeeded", job_id)

    except Exception as exc:
        logger.exception("Job %s failed", job_id)

        async with SessionFactory() as failure_session:
            repository = JobRepository(failure_session)

            async with failure_session.begin():
                await repository.mark_failed(
                    job_id=job_id,
                    worker_id=worker_id,
                    error=str(exc),
                    retry_delay=timedelta(
                        seconds=settings.worker_retry_delay_seconds
                    ),
                )

    return True


async def run_worker() -> None:
    settings = get_settings()
    worker_id = build_worker_id()

    logger.info("Worker started: %s", worker_id)

    while True:
        claimed = await process_one_job(worker_id)

        if not claimed:
            await asyncio.sleep(
                settings.worker_poll_interval_seconds
            )


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
