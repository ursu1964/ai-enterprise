from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass

from docker import from_env
from docker.errors import DockerException, ImageNotFound

from ai_enterprise.config import Settings
from ai_enterprise.domain.enums import JobType
from ai_enterprise.infrastructure.architecture.provider_factory import (
    ArchitectureProviderConfig,
    architecture_provider_ready,
)
from ai_enterprise.infrastructure.requirements_llm.provider import (
    RequirementsProviderError,
    create_requirements_provider,
    provider_config_from_settings,
)


@dataclass(frozen=True, slots=True)
class SetupBlocker:
    code: str
    capability: str
    job_types: frozenset[JobType]
    detail: str
    next_action: str

    @property
    def evidence(self) -> str:
        return (
            f"Setup blocker [{self.code}] capability={self.capability}. "
            f"{self.detail} Next: {self.next_action}"
        )


@dataclass(frozen=True, slots=True)
class WorkerReadiness:
    permitted_job_types: frozenset[JobType]
    blockers: tuple[SetupBlocker, ...]

    @property
    def degraded(self) -> bool:
        return bool(self.blockers)


class WorkerReadinessCache:
    def __init__(
        self,
        interval_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._interval_seconds = interval_seconds
        self._clock = clock
        self._checked_at: float | None = None
        self._result: WorkerReadiness | None = None

    async def get(
        self,
        settings: Settings,
        candidate_job_types: frozenset[JobType],
    ) -> WorkerReadiness:
        now = self._clock()
        if (
            self._result is None
            or self._checked_at is None
            or now - self._checked_at >= self._interval_seconds
        ):
            self._result = await assess_worker_readiness(settings, candidate_job_types)
            self._checked_at = now
        return self._result


async def assess_worker_readiness(
    settings: Settings,
    candidate_job_types: frozenset[JobType],
) -> WorkerReadiness:
    blockers: list[SetupBlocker] = []
    docker_job_types = candidate_job_types & {
        JobType.EXECUTE_WORK_PACKAGE,
        JobType.REVIEW_CANDIDATE_PATCH,
    }
    if docker_job_types:
        blockers.extend(await asyncio.to_thread(_docker_blockers, settings, docker_job_types))

    if JobType.RUN_REQUIREMENTS_CREW in candidate_job_types and (
        settings.requirements_crew_adapter.strip().lower() == "crewai"
    ):
        try:
            await create_requirements_provider(provider_config_from_settings(settings)).preflight()
        except (RequirementsProviderError, ValueError):
            blockers.append(
                _model_blocker(
                    code="requirements_provider_unavailable",
                    job_type=JobType.RUN_REQUIREMENTS_CREW,
                    model=settings.requirements_llm_model,
                )
            )

    model_checks: list[tuple[JobType, str, str, str]] = []
    if JobType.RUN_ARCHITECTURE_CREW in candidate_job_types:
        model_checks.append(
            (
                JobType.RUN_ARCHITECTURE_CREW,
                "architecture_provider_unavailable",
                settings.architecture_model_name,
                settings.architecture_model_base_url,
            )
        )
    if JobType.RUN_WORK_PACKAGE_DECOMPOSITION in candidate_job_types:
        model_checks.append(
            (
                JobType.RUN_WORK_PACKAGE_DECOMPOSITION,
                "decomposition_provider_unavailable",
                settings.decomposition_model_name,
                settings.decomposition_model_base_url,
            )
        )
    if (
        JobType.PLAN_WORK_PACKAGE in candidate_job_types
        and settings.architecture_provider.strip().lower() != "scripted"
    ):
        model_checks.append(
            (
                JobType.PLAN_WORK_PACKAGE,
                "planning_provider_unavailable",
                settings.ollama_model,
                settings.ollama_base_url,
            )
        )
    readiness = await asyncio.gather(
        *(
            architecture_provider_ready(
                ArchitectureProviderConfig(
                    provider=(
                        settings.architecture_provider
                        if job_type is JobType.RUN_ARCHITECTURE_CREW
                        else "crewai-ollama"
                    ),
                    model_name=model,
                    base_url=base_url,
                    timeout_seconds=10,
                )
            )
            for job_type, _code, model, base_url in model_checks
        )
    )
    for (job_type, code, model, _base_url), ready in zip(model_checks, readiness, strict=True):
        if not ready:
            blockers.append(_model_blocker(code=code, job_type=job_type, model=model))

    blocked_types = frozenset(job_type for blocker in blockers for job_type in blocker.job_types)
    return WorkerReadiness(
        permitted_job_types=candidate_job_types - blocked_types,
        blockers=tuple(blockers),
    )


def _docker_blockers(
    settings: Settings, job_types: frozenset[JobType]
) -> tuple[SetupBlocker, ...]:
    provider = settings.execution_container_provider.strip().lower()
    if provider != "restricted-local-docker":
        return (
            SetupBlocker(
                code="restricted_executor_unconfigured",
                capability="container_execution",
                job_types=job_types,
                detail=(
                    "No approved restricted container execution provider is configured for "
                    "execution or review jobs."
                ),
                next_action=(
                    "Set EXECUTION_CONTAINER_PROVIDER=restricted-local-docker only after the "
                    "restricted broker engine, pinned image IDs, and local canaries are verified."
                ),
            ),
        )

    try:
        client = from_env()
        client.ping()
    except (DockerException, OSError):
        return (
            SetupBlocker(
                code="docker_runtime_unavailable",
                capability="container_execution",
                job_types=job_types,
                detail="The worker cannot reach its configured container execution service.",
                next_action=(
                    "Configure an approved restricted execution provider; do not expose an "
                    "unrestricted host Docker socket."
                ),
            ),
        )

    blockers: list[SetupBlocker] = []
    for job_type, image, expected_image_id, unavailable_code, identity_code in (
        (
            JobType.EXECUTE_WORK_PACKAGE,
            settings.execution_image,
            settings.execution_image_id,
            "execution_image_unavailable",
            "execution_image_id_mismatch",
        ),
        (
            JobType.REVIEW_CANDIDATE_PATCH,
            settings.review_image,
            settings.review_image_id,
            "review_image_unavailable",
            "review_image_id_mismatch",
        ),
    ):
        if job_type not in job_types:
            continue
        if expected_image_id is None or not _is_sha256_image_id(expected_image_id):
            blockers.append(
                SetupBlocker(
                    code=f"{job_type.value}_image_id_unconfigured",
                    capability="container_image_identity",
                    job_types=frozenset({job_type}),
                    detail=(
                        f"Required governed runtime image {image!r} does not have a configured "
                        "immutable sha256 image ID."
                    ),
                    next_action=(
                        "Build the pinned image, record its exact Docker image ID, and configure "
                        "the matching *_IMAGE_ID value before dispatch."
                    ),
                )
            )
            continue
        try:
            resolved = client.images.get(image)
        except (DockerException, ImageNotFound):
            blockers.append(
                SetupBlocker(
                    code=unavailable_code,
                    capability="container_image",
                    job_types=frozenset({job_type}),
                    detail=f"Required governed runtime image {image!r} is unavailable.",
                    next_action="Build and verify the pinned runtime image before dispatch.",
                )
            )
            continue
        resolved_attrs = getattr(resolved, "attrs", {})
        actual_image_id = getattr(resolved, "id", None) or resolved_attrs.get("Id")
        if actual_image_id != expected_image_id:
            blockers.append(
                SetupBlocker(
                    code=identity_code,
                    capability="container_image_identity",
                    job_types=frozenset({job_type}),
                    detail=(
                        f"Required governed runtime image {image!r} resolved to "
                        f"{actual_image_id!r}, not the approved immutable image ID."
                    ),
                    next_action=(
                        "Rebuild or retag the pinned runtime image and update the approved image "
                        "ID only after verification."
                    ),
                )
            )
    if not blockers:
        blockers.append(
            SetupBlocker(
                code="restricted_executor_dispatch_unwired",
                capability="container_execution",
                job_types=job_types,
                detail=(
                    "The approved restricted executor images are present, but application "
                    "execution/review dispatch is not wired to the durable broker path yet."
                ),
                next_action=(
                    "Wire execution and review dispatch to the durable restricted broker runner "
                    "before leasing production jobs."
                ),
            )
        )
    return tuple(blockers)


def _is_sha256_image_id(value: str) -> bool:
    if not value.startswith("sha256:") or len(value) != 71:
        return False
    try:
        int(value.removeprefix("sha256:"), 16)
    except ValueError:
        return False
    return True


def _model_blocker(*, code: str, job_type: JobType, model: str) -> SetupBlocker:
    return SetupBlocker(
        code=code,
        capability="model_provider",
        job_types=frozenset({job_type}),
        detail=f"Required model provider for {model!r} did not pass preflight.",
        next_action=(
            "Restore the configured provider and verify the required model before dispatch."
        ),
    )
