from enum import StrEnum


class AuditAggregateType(StrEnum):
    PROJECT = "project"
    MANIFEST = "manifest"
    CREW_RUN = "crew_run"
    ARTIFACT = "artifact"
    APPROVAL = "approval"
    WORK_PACKAGE = "work_package"
    EXECUTION_RUN = "execution_run"
    PATCH_REVIEW_RUN = "patch_review_run"


class AuditActorType(StrEnum):
    USER = "user"
    SYSTEM = "system"
    AGENT = "agent"
    WORKER = "worker"
    API_CLIENT = "api_client"


class AuditExportStatus(StrEnum):
    PENDING = "pending"
    BUILDING = "building"
    COMPLETED = "completed"
    FAILED = "failed"
