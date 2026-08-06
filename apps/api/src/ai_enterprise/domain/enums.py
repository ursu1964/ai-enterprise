from enum import StrEnum


class ProjectStatus(StrEnum):
    CREATED = "created"

    REQUIREMENTS_QUEUED = "requirements_queued"
    REQUIREMENTS_RUNNING = "requirements_running"
    REQUIREMENTS_FAILED = "requirements_failed"
    AWAITING_REQUIREMENTS_APPROVAL = "awaiting_requirements_approval"
    REQUIREMENTS_APPROVED = "requirements_approved"
    REQUIREMENTS_REJECTED = "requirements_rejected"

    ARCHITECTURE_QUEUED = "architecture_queued"
    ARCHITECTURE_RUNNING = "architecture_running"
    ARCHITECTURE_FAILED = "architecture_failed"
    AWAITING_ARCHITECTURE_APPROVAL = "awaiting_architecture_approval"
    ARCHITECTURE_APPROVED = "architecture_approved"
    ARCHITECTURE_REJECTED = "architecture_rejected"

    WORK_PACKAGE_QUEUED = "work_package_queued"
    WORK_PACKAGE_PLANNING = "work_package_planning"
    WORK_PACKAGE_FAILED = "work_package_failed"
    AWAITING_WORK_PACKAGE_APPROVAL = "awaiting_work_package_approval"
    WORK_PACKAGE_APPROVED = "work_package_approved"
    WORK_PACKAGE_REJECTED = "work_package_rejected"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class JobStatus(StrEnum):
    QUEUED = "queued"
    LEASED = "leased"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"
    RETRY_WAIT = "retry_wait"


class JobType(StrEnum):
    ADVANCE_WORKFLOW = "advance_workflow"
    RUN_REQUIREMENTS_CREW = "run_requirements_crew"
    RUN_ARCHITECTURE_CREW = "run_architecture_crew"
    RUN_WORK_PACKAGE_DECOMPOSITION = "run_work_package_decomposition"
    PLAN_WORK_PACKAGE = "plan_work_package"
    EXECUTE_WORK_PACKAGE = "execute_work_package"
    REVIEW_CANDIDATE_PATCH = "review_candidate_patch"
    INTEGRATE_APPROVED_PATCH = "integrate_approved_patch"
    RECOVER_INTEGRATION = "recover_integration"


class ArtifactType(StrEnum):
    PROJECT_MANIFEST = "project_manifest"
    PROJECT_SNAPSHOT = "project_snapshot"
    PROJECT_BLUEPRINT = "project_blueprint"
    TRACEABILITY_MANIFEST = "traceability_manifest"
    CANONICAL_PROJECT_MODEL = "canonical_project_model"
    ARTIFACT_CONTRACTS = "artifact_contracts"
    ARTIFACT_VALIDATION_REPORT = "artifact_validation_report"
    PROJECT_BRIEF = "project_brief"
    SOLUTION_PROPOSAL = "solution_proposal"
    DELIVERY_PLAN = "delivery_plan"
    FORMATION_QUALITY_REVIEW = "formation_quality_review"
    FORMATION_APPROVAL_PACK = "formation_approval_pack"
    REQUIREMENTS_SPECIFICATION = "requirements_specification"
    ARCHITECTURE_SPECIFICATION = "architecture_specification"
    WORK_PACKAGE = "work_package"
    EXECUTION_LOG = "execution-log"
    TEST_STDOUT = "test-stdout"
    TEST_STDERR = "test-stderr"
    CANDIDATE_PATCH = "candidate-patch"
    PATCH_REVIEW_REPORT = "patch-review-report"
    REVIEW_CHECK_STDOUT = "review-check-stdout"
    REVIEW_CHECK_STDERR = "review-check-stderr"
    REVIEW_LOG = "review-log"


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class NetworkPolicy(StrEnum):
    NONE = "none"
    LOOPBACK_ONLY = "loopback_only"
    ALLOWLIST = "allowlist"


class WorkPackageStatus(StrEnum):
    DRAFT = "draft"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTION_QUEUED = "execution_queued"
    EXECUTING = "executing"
    EXECUTION_SUCCEEDED = "execution_succeeded"
    EXECUTION_FAILED = "execution_failed"
