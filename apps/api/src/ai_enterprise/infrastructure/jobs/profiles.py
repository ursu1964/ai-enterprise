from enum import StrEnum

from ai_enterprise.domain.enums import JobType


class WorkerProfile(StrEnum):
    GENERAL = "general"
    INTEGRATION = "integration"
    RECOVERY = "recovery"


GENERAL_JOB_TYPES: frozenset[JobType] = frozenset(
    {
        JobType.ADVANCE_WORKFLOW,
        JobType.RUN_REQUIREMENTS_CREW,
        JobType.RUN_ARCHITECTURE_CREW,
        JobType.RUN_WORK_PACKAGE_DECOMPOSITION,
        JobType.PLAN_WORK_PACKAGE,
        JobType.EXECUTE_WORK_PACKAGE,
        JobType.REVIEW_CANDIDATE_PATCH,
    }
)
INTEGRATION_JOB_TYPES: frozenset[JobType] = frozenset({JobType.INTEGRATE_APPROVED_PATCH})
RECOVERY_JOB_TYPES: frozenset[JobType] = frozenset({JobType.RECOVER_INTEGRATION})


def allowed_job_types(profile: WorkerProfile) -> frozenset[JobType]:
    if profile is WorkerProfile.INTEGRATION:
        return INTEGRATION_JOB_TYPES
    if profile is WorkerProfile.RECOVERY:
        return RECOVERY_JOB_TYPES
    return GENERAL_JOB_TYPES
