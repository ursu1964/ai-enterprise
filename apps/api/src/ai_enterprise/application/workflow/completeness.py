from dataclasses import dataclass

from ai_enterprise.domain.workflow.context import WorkflowContext


@dataclass(frozen=True, slots=True)
class CompletenessResult:
    complete: bool
    missing: tuple[str, ...]


MANDATORY_ARTIFACTS = (
    "manifest",
    "requirements",
    "architecture",
    "work_package",
    "patch",
    "review",
)
MANDATORY_APPROVALS = ("requirements", "architecture", "work_package", "integration")


def verify_completeness(context: WorkflowContext) -> CompletenessResult:
    missing = [
        f"artifact:{name}" for name in MANDATORY_ARTIFACTS if name not in context.artifact_ids
    ]
    missing.extend(
        f"approval:{name}" for name in MANDATORY_APPROVALS if name not in context.approval_ids
    )
    if context.execution_id is None:
        missing.append("execution")
    if context.review_id is None:
        missing.append("review")
    if context.integration_attempt_id is None:
        missing.append("integration_attempt")
    if context.commit_id is None:
        missing.append("commit")
    return CompletenessResult(not missing, tuple(missing))
